"""
Tests for src/services/webhook.py — specifically the async refactor.

Key invariants verified:
1. process_lnd_invoice_settled is async and can be awaited without error.
2. No asyncio.run() call exists inside WebhookService methods.
3. run_async() raises RuntimeError when called from inside a running loop.
4. run_async() works correctly from a sync context (no running loop).
5. Notification failures do NOT roll back the DB state transition.
6. Duplicate webhook (idempotency) returns error without changing state.
7. Unknown invoice hash returns error without raising.
8. retry_failed_webhooks is async and awaitable.
"""

import asyncio
import hashlib
import hmac
import inspect
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.models import Transfer, TransferState, TransferHistory, Webhook as WebhookModel
from src.services.webhook import WebhookService, run_async
from tests.conftest import make_agent, make_transfer


# ---------------------------------------------------------------------------
# Structural tests — verify method signatures before any runtime behaviour
# ---------------------------------------------------------------------------

class TestWebhookServiceStructure:
    def test_process_lnd_invoice_settled_is_coroutine_function(self):
        """The method must be async def so FastAPI can await it directly."""
        assert inspect.iscoroutinefunction(
            WebhookService.process_lnd_invoice_settled
        ), "process_lnd_invoice_settled must be async def"

    def test_send_receiver_notification_is_coroutine_function(self):
        assert inspect.iscoroutinefunction(
            WebhookService._send_receiver_notification
        ), "_send_receiver_notification must be async def"

    def test_send_agent_notification_is_coroutine_function(self):
        assert inspect.iscoroutinefunction(
            WebhookService._send_agent_notification
        ), "_send_agent_notification must be async def"

    def test_retry_failed_webhooks_is_coroutine_function(self):
        assert inspect.iscoroutinefunction(
            WebhookService.retry_failed_webhooks
        ), "retry_failed_webhooks must be async def"

    def test_no_asyncio_run_in_service_methods(self):
        """
        asyncio.run() must never appear inside WebhookService method bodies.
        The only permitted location is the run_async() module-level helper.
        """
        import ast, textwrap
        import src.services.webhook as mod
        import importlib
        source = inspect.getsource(mod)
        tree = ast.parse(source)

        # Collect all Call nodes that are asyncio.run(...)
        violations = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            # asyncio.run(...)
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "run"
                and isinstance(func.value, ast.Name)
                and func.value.id == "asyncio"
            ):
                # Find which function this call is inside
                for parent in ast.walk(tree):
                    if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if parent.name == "run_async":
                            break  # allowed inside run_async
                        for child in ast.walk(parent):
                            if child is node:
                                violations.append(
                                    f"{parent.name}:line {node.lineno}"
                                )
                                break

        assert violations == [], (
            f"asyncio.run() found inside WebhookService methods: {violations}. "
            "Use 'await' instead."
        )


# ---------------------------------------------------------------------------
# run_async helper behaviour
# ---------------------------------------------------------------------------

class TestRunAsync:
    def test_run_async_executes_coroutine_from_sync_context(self):
        """run_async should return the coroutine result in a sync context."""
        async def _coro():
            return 42

        result = run_async(_coro())
        assert result == 42

    def test_run_async_raises_inside_running_loop(self):
        """
        Calling run_async from inside an already-running event loop must raise
        RuntimeError — this is the guard that prevents accidental misuse.
        """
        async def _call_from_loop():
            async def _inner():
                pass
            run_async(_inner())   # should raise

        with pytest.raises(RuntimeError, match="running event loop"):
            asyncio.run(_call_from_loop())


# ---------------------------------------------------------------------------
# process_lnd_invoice_settled — happy path and edge cases
# ---------------------------------------------------------------------------

class TestProcessLndInvoiceSettled:
    @pytest.mark.asyncio
    async def test_transitions_to_payment_locked(self, db, agent):
        """Happy path: INVOICE_GENERATED → PAYMENT_LOCKED."""
        transfer = make_transfer(
            db, agent,
            state=TransferState.INVOICE_GENERATED,
            invoice_hash="a" * 64,
        )

        svc = WebhookService(db)
        # Patch notifications so no real HTTP calls are made
        svc.notification_service.send_whatsapp = AsyncMock(return_value={"id": "ok"})

        result = await svc.process_lnd_invoice_settled(
            invoice_hash="a" * 64,
            state="SETTLED",
            settled_at=datetime.utcnow(),
            amount_milli_satoshis=5_000_000,
        )

        assert result["status"] == "success"
        assert result["transfer_id"] == str(transfer.id)

        db.refresh(transfer)
        assert transfer.state == TransferState.PAYMENT_LOCKED
        assert transfer.pin_generated is not None  # bcrypt hash stored

    @pytest.mark.asyncio
    async def test_also_accepts_initiated_state(self, db, agent):
        """INITIATED is also a valid starting state (edge case)."""
        transfer = make_transfer(
            db, agent,
            state=TransferState.INITIATED,
            invoice_hash="b" * 64,
        )
        svc = WebhookService(db)
        svc.notification_service.send_whatsapp = AsyncMock(return_value=None)

        result = await svc.process_lnd_invoice_settled(
            invoice_hash="b" * 64,
            state="SETTLED",
            settled_at=datetime.utcnow(),
            amount_milli_satoshis=1_000_000,
        )

        assert result["status"] == "success"
        db.refresh(transfer)
        assert transfer.state == TransferState.PAYMENT_LOCKED

    @pytest.mark.asyncio
    async def test_unknown_invoice_hash_returns_error(self, db):
        """No transfer found → return error dict, do not raise."""
        svc = WebhookService(db)
        result = await svc.process_lnd_invoice_settled(
            invoice_hash="0" * 64,
            state="SETTLED",
            settled_at=datetime.utcnow(),
            amount_milli_satoshis=1_000_000,
        )
        assert result["status"] == "error"
        assert "not found" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_idempotency_already_locked(self, db, agent):
        """Duplicate webhook on already-PAYMENT_LOCKED transfer is rejected."""
        transfer = make_transfer(
            db, agent,
            state=TransferState.PAYMENT_LOCKED,
            invoice_hash="c" * 64,
        )
        svc = WebhookService(db)
        svc.notification_service.send_whatsapp = AsyncMock(return_value=None)

        result = await svc.process_lnd_invoice_settled(
            invoice_hash="c" * 64,
            state="SETTLED",
            settled_at=datetime.utcnow(),
            amount_milli_satoshis=1_000_000,
        )

        assert result["status"] == "error"
        assert "already in state" in result["message"].lower()

        # State must remain unchanged
        db.refresh(transfer)
        assert transfer.state == TransferState.PAYMENT_LOCKED

    @pytest.mark.asyncio
    async def test_notification_failure_does_not_rollback_state(self, db, agent):
        """
        DB commit happens BEFORE notifications.  A notification crash must not
        roll back the PAYMENT_LOCKED transition.
        """
        transfer = make_transfer(
            db, agent,
            state=TransferState.INVOICE_GENERATED,
            invoice_hash="d" * 64,
        )

        svc = WebhookService(db)
        # Make WhatsApp always fail
        svc.notification_service.send_whatsapp = AsyncMock(
            side_effect=Exception("WhatsApp down")
        )

        result = await svc.process_lnd_invoice_settled(
            invoice_hash="d" * 64,
            state="SETTLED",
            settled_at=datetime.utcnow(),
            amount_milli_satoshis=2_000_000,
        )

        # Despite notification failure, DB state must be PAYMENT_LOCKED
        assert result["status"] == "success"
        db.refresh(transfer)
        assert transfer.state == TransferState.PAYMENT_LOCKED

    @pytest.mark.asyncio
    async def test_audit_history_row_created(self, db, agent):
        """A TransferHistory row must be written for the state transition."""
        transfer = make_transfer(
            db, agent,
            state=TransferState.INVOICE_GENERATED,
            invoice_hash="e" * 64,
        )

        svc = WebhookService(db)
        svc.notification_service.send_whatsapp = AsyncMock(return_value={"id": "ok"})

        await svc.process_lnd_invoice_settled(
            invoice_hash="e" * 64,
            state="SETTLED",
            settled_at=datetime.utcnow(),
            amount_milli_satoshis=3_000_000,
        )

        history = (
            db.query(TransferHistory)
            .filter(TransferHistory.transfer_id == transfer.id)
            .first()
        )
        assert history is not None
        assert history.old_state == TransferState.INVOICE_GENERATED
        assert history.new_state == TransferState.PAYMENT_LOCKED

    @pytest.mark.asyncio
    async def test_webhook_log_row_created(self, db, agent):
        """A Webhook delivery log row must be written."""
        transfer = make_transfer(
            db, agent,
            state=TransferState.INVOICE_GENERATED,
            invoice_hash="f" * 64,
        )

        svc = WebhookService(db)
        svc.notification_service.send_whatsapp = AsyncMock(return_value={"id": "ok"})

        await svc.process_lnd_invoice_settled(
            invoice_hash="f" * 64,
            state="SETTLED",
            settled_at=datetime.utcnow(),
            amount_milli_satoshis=3_000_000,
        )

        log = (
            db.query(WebhookModel)
            .filter(WebhookModel.event_type == "lnd.invoice.settled")
            .first()
        )
        assert log is not None
        assert log.status == "delivered"
        assert log.payload["invoice_hash"] == "f" * 64

    @pytest.mark.asyncio
    async def test_notifications_awaited_not_run_with_asyncio_run(self, db, agent):
        """
        The notification calls must be awaited coroutines, not asyncio.run()
        calls.  We verify this by running the whole method inside an already-
        running event loop (the pytest-asyncio loop) — if asyncio.run() were
        still present it would raise RuntimeError here.
        """
        transfer = make_transfer(
            db, agent,
            state=TransferState.INVOICE_GENERATED,
            invoice_hash="9" * 64,
        )

        svc = WebhookService(db)
        svc.notification_service.send_whatsapp = AsyncMock(return_value={"id": "ok"})

        # If asyncio.run() is still present, this will raise RuntimeError.
        result = await svc.process_lnd_invoice_settled(
            invoice_hash="9" * 64,
            state="SETTLED",
            settled_at=datetime.utcnow(),
            amount_milli_satoshis=5_000_000,
        )
        assert result["status"] == "success"


# ---------------------------------------------------------------------------
# retry_failed_webhooks
# ---------------------------------------------------------------------------

class TestRetryFailedWebhooks:
    @pytest.mark.asyncio
    async def test_is_awaitable(self, db):
        """retry_failed_webhooks must be awaitable from an async context."""
        svc = WebhookService(db)
        result = await svc.retry_failed_webhooks()
        assert "attempted" in result
        assert "succeeded" in result
        assert "failed" in result

    @pytest.mark.asyncio
    async def test_retries_failed_invoice_webhook(self, db, agent):
        """A FAILED webhook record with retry_count < 3 should be re-processed."""
        transfer = make_transfer(
            db, agent,
            state=TransferState.INVOICE_GENERATED,
            invoice_hash="aa" * 32,
        )

        # Create a failed webhook log
        failed_log = WebhookModel(
            event_type="lnd.invoice.settled",
            payload={
                "invoice_hash": "aa" * 32,
                "state": "SETTLED",
                "amount_milli_satoshis": 1_000_000,
                "transfer_id": str(transfer.id),
            },
            status="failed",
            retry_count=0,
        )
        db.add(failed_log)
        db.commit()

        svc = WebhookService(db)
        svc.notification_service.send_whatsapp = AsyncMock(return_value={"id": "ok"})

        result = await svc.retry_failed_webhooks()

        assert result["attempted"] == 1
        assert result["succeeded"] == 1

        db.refresh(transfer)
        assert transfer.state == TransferState.PAYMENT_LOCKED
