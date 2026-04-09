"""
Unit tests for the transfer state machine (src/services/transfer.py).

Uses an in-memory SQLite DB via the shared `db` fixture from conftest.py.
LNDService is patched so no real Lightning node is required.
"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from src.models.models import Transfer, TransferState, TransferHistory
from src.services.transfer import TransferService
from tests.conftest import make_agent, make_transfer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_svc(db, mock_lnd=None):
    svc = TransferService(db)
    if mock_lnd:
        svc.lnd = mock_lnd
    return svc


# ---------------------------------------------------------------------------
# initiate_transfer
# ---------------------------------------------------------------------------

class TestInitiateTransfer:
    @pytest.mark.asyncio
    async def test_creates_transfer_in_initiated_state(self, db, agent):
        svc = _make_svc(db)
        transfer = await svc.initiate_transfer(
            sender_phone="+27831234567",
            receiver_phone="+263771234567",
            receiver_name="Jane Doe",
            receiver_location="ZWE_HRR",
            amount_zar=Decimal("200.00"),
            amount_sats=5000,
            rate_zar_per_btc=Decimal("1200000.00"),
            agent_id=agent.id,
        )
        assert transfer.state == TransferState.INITIATED
        assert transfer.reference is not None
        assert len(transfer.reference) == 20

    @pytest.mark.asyncio
    async def test_logs_initiated_state_in_history(self, db, agent):
        svc = _make_svc(db)
        transfer = await svc.initiate_transfer(
            sender_phone="+27831234567",
            receiver_phone="+263771234567",
            receiver_name="Jane Doe",
            receiver_location="ZWE_HRR",
            amount_zar=Decimal("100.00"),
            amount_sats=2500,
            rate_zar_per_btc=Decimal("1200000.00"),
            agent_id=agent.id,
        )
        history = db.query(TransferHistory).filter(
            TransferHistory.transfer_id == transfer.id
        ).all()
        assert len(history) >= 1
        assert history[0].new_state == TransferState.INITIATED

    @pytest.mark.asyncio
    async def test_raises_if_agent_not_found(self, db):
        svc = _make_svc(db)
        with pytest.raises(ValueError, match="not found"):
            await svc.initiate_transfer(
                sender_phone="+27831234567",
                receiver_phone="+263771234567",
                receiver_name="Jane Doe",
                receiver_location="ZWE_HRR",
                amount_zar=Decimal("100.00"),
                amount_sats=2500,
                rate_zar_per_btc=Decimal("1200000.00"),
                agent_id=uuid.uuid4(),  # non-existent
            )


# ---------------------------------------------------------------------------
# generate_invoice
# ---------------------------------------------------------------------------

class TestGenerateInvoice:
    @pytest.mark.asyncio
    async def test_transitions_to_invoice_generated(self, db, agent, mock_lnd):
        svc = _make_svc(db, mock_lnd)
        transfer = await svc.initiate_transfer(
            sender_phone="+27831234567",
            receiver_phone="+263771234567",
            receiver_name="Jane Doe",
            receiver_location="ZWE_HRR",
            amount_zar=Decimal("200.00"),
            amount_sats=5000,
            rate_zar_per_btc=Decimal("1200000.00"),
            agent_id=agent.id,
        )
        await svc.generate_invoice(transfer.id)
        db.refresh(transfer)
        assert transfer.state == TransferState.INVOICE_GENERATED
        assert transfer.invoice_hash is not None
        assert transfer.payment_request is not None

    @pytest.mark.asyncio
    async def test_raises_for_wrong_state(self, db, agent):
        transfer = make_transfer(db, agent, state=TransferState.SETTLED)
        svc = _make_svc(db)
        with pytest.raises(ValueError, match="Cannot generate invoice"):
            await svc.generate_invoice(transfer.id)


# ---------------------------------------------------------------------------
# refund_transfer — old_state capture bug fix
# ---------------------------------------------------------------------------

class TestRefundTransfer:
    @pytest.mark.asyncio
    async def test_refund_records_correct_old_state(self, db, agent):
        """
        Before the fix, refund_transfer captured old_state AFTER mutating
        transfer.state, so the audit log always showed REFUNDED → REFUNDED.
        This test verifies the correct old_state is recorded.
        """
        transfer = make_transfer(db, agent, state=TransferState.PAYMENT_LOCKED)
        svc = _make_svc(db)
        await svc.refund_transfer(transfer.id, reason="test refund")

        db.refresh(transfer)
        assert transfer.state == TransferState.REFUNDED

        history = db.query(TransferHistory).filter(
            TransferHistory.transfer_id == transfer.id,
            TransferHistory.new_state == TransferState.REFUNDED,
        ).first()
        assert history is not None
        # old_state must be PAYMENT_LOCKED, not REFUNDED
        assert history.old_state == TransferState.PAYMENT_LOCKED

    @pytest.mark.asyncio
    async def test_refund_from_invoice_generated_records_correct_old_state(self, db, agent):
        transfer = make_transfer(db, agent, state=TransferState.INVOICE_GENERATED)
        svc = _make_svc(db)
        await svc.refund_transfer(transfer.id, reason="expired")

        history = db.query(TransferHistory).filter(
            TransferHistory.transfer_id == transfer.id,
            TransferHistory.new_state == TransferState.REFUNDED,
        ).first()
        assert history.old_state == TransferState.INVOICE_GENERATED

    @pytest.mark.asyncio
    async def test_cannot_refund_already_settled_transfer(self, db, agent):
        transfer = make_transfer(db, agent, state=TransferState.SETTLED)
        svc = _make_svc(db)
        with pytest.raises(ValueError, match="Cannot refund"):
            await svc.refund_transfer(transfer.id)

    @pytest.mark.asyncio
    async def test_cannot_refund_final_transfer(self, db, agent):
        transfer = make_transfer(db, agent, state=TransferState.FINAL)
        svc = _make_svc(db)
        with pytest.raises(ValueError, match="Cannot refund"):
            await svc.refund_transfer(transfer.id)


# ---------------------------------------------------------------------------
# verify_receiver / verify_agent — dual verification gate
# ---------------------------------------------------------------------------

class TestDualVerification:
    @pytest.mark.asyncio
    async def test_state_transitions_only_when_both_verified(self, db, agent):
        transfer = make_transfer(db, agent, state=TransferState.PAYMENT_LOCKED)
        svc = _make_svc(db)

        # Only receiver verified — must NOT transition yet
        await svc.verify_receiver(transfer.id, verified=True)
        db.refresh(transfer)
        assert transfer.state == TransferState.PAYMENT_LOCKED

        # Now agent also verified — MUST transition
        await svc.verify_agent(transfer.id, verified=True)
        db.refresh(transfer)
        assert transfer.state == TransferState.RECEIVER_VERIFIED

    @pytest.mark.asyncio
    async def test_state_transitions_when_agent_verified_first(self, db, agent):
        transfer = make_transfer(db, agent, state=TransferState.PAYMENT_LOCKED)
        svc = _make_svc(db)

        await svc.verify_agent(transfer.id, verified=True)
        db.refresh(transfer)
        assert transfer.state == TransferState.PAYMENT_LOCKED  # not yet

        await svc.verify_receiver(transfer.id, verified=True)
        db.refresh(transfer)
        assert transfer.state == TransferState.RECEIVER_VERIFIED
