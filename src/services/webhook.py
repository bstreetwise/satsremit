"""
Webhook handling service for SatsRemit.

All public methods are ``async def`` so they can be directly awaited from
FastAPI route handlers without wrapping in ``asyncio.run()``.  The service
must never call ``asyncio.run()`` itself — that would raise
``RuntimeError: This event loop is already running`` inside an ASGI context.

For Celery tasks (sync context) that need to trigger notifications, use the
``run_async`` helper defined at the bottom of this module.
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from src.models.models import Transfer, TransferState, TransferHistory, Webhook as WebhookModel
from src.services.transfer import TransferService
from src.services.notification import NotificationService
from src.core.security import generate_pin, hash_pin

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Safe async runner for sync (Celery) contexts
# ---------------------------------------------------------------------------

def run_async(coro):
    """
    Run an async coroutine from a synchronous context (e.g. a Celery task).

    This is intentionally NOT used inside WebhookService — the service is
    always called from an async FastAPI handler and uses plain ``await``.
    This helper exists for Celery tasks that need to fire a notification
    without an already-running event loop.

    Raises ``RuntimeError`` if called from inside a running event loop;
    callers in that situation should ``await`` the coroutine directly.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        raise RuntimeError(
            "run_async() called from inside a running event loop. "
            "Use 'await' instead."
        )
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# WebhookService
# ---------------------------------------------------------------------------

class WebhookService:
    """Handle webhook events from LND and other services.

    All methods are async so that callers (FastAPI route handlers) can
    ``await`` them directly without blocking the event loop.
    """

    def __init__(self, db: Session):
        self.db = db
        self.transfer_service = TransferService(db)
        self.notification_service = NotificationService()

    # ------------------------------------------------------------------
    # Primary webhook handler
    # ------------------------------------------------------------------

    async def process_lnd_invoice_settled(
        self,
        invoice_hash: str,
        state: str,
        settled_at: datetime,
        amount_milli_satoshis: int,
    ) -> dict:
        """
        Process an LND invoice-settled webhook.

        Transitions the matching transfer to ``PAYMENT_LOCKED``, generates a
        bcrypt-hashed receiver PIN, persists the audit trail, and dispatches
        WhatsApp notifications — all in the same async context.

        DB writes are committed **before** notifications are sent.  A
        notification failure therefore never rolls back the state transition.

        Args:
            invoice_hash: LND payment hash (hex, 64 chars).
            state: Invoice state string from LND (e.g. ``"SETTLED"``).
            settled_at: Timestamp reported by LND.
            amount_milli_satoshis: Paid amount in milli-satoshis.

        Returns:
            ``{"status": "success"|"error", "transfer_id": str|None, "message": str}``
        """
        try:
            logger.info(f"Processing invoice settled webhook: {invoice_hash}")

            # 1. Find transfer by invoice hash
            transfer = self.db.query(Transfer).filter_by(
                invoice_hash=invoice_hash
            ).first()

            if not transfer:
                logger.warning(f"Transfer not found for invoice: {invoice_hash}")
                return {
                    "status": "error",
                    "transfer_id": None,
                    "message": "Transfer not found",
                }

            logger.info(
                f"Found transfer {transfer.id} (ref={transfer.reference}) "
                f"for invoice {invoice_hash}"
            )

            # 2. Idempotency guard — ignore if already past PAYMENT_LOCKED
            if transfer.state not in [
                TransferState.INVOICE_GENERATED,
                TransferState.INITIATED,
            ]:
                logger.warning(
                    f"Transfer {transfer.id} already in state {transfer.state!r}; "
                    "skipping duplicate webhook"
                )
                return {
                    "status": "error",
                    "transfer_id": str(transfer.id),
                    "message": f"Transfer already in state: {transfer.state}",
                }

            # 3. Transition state
            old_state = transfer.state
            transfer.state = TransferState.PAYMENT_LOCKED
            transfer.updated_at = datetime.utcnow()

            # 4. Audit history
            history = TransferHistory(
                transfer_id=transfer.id,
                old_state=old_state,
                new_state=TransferState.PAYMENT_LOCKED,
                reason="Payment received from LND",
                actor_type="system",
                actor_id="lnd_webhook",
            )
            self.db.add(history)

            # 5. Generate PIN — store hash, keep plaintext in memory for delivery
            pin = generate_pin()
            transfer.pin_generated = hash_pin(pin)

            # 6. Webhook delivery log
            webhook_log = WebhookModel(
                event_type="lnd.invoice.settled",
                payload={
                    "invoice_hash": invoice_hash,
                    "state": state,
                    "amount_milli_satoshis": amount_milli_satoshis,
                    "transfer_id": str(transfer.id),
                },
                status="delivered",
                retry_count=0,
                processed_at=datetime.utcnow(),
            )
            self.db.add(webhook_log)

            # 7. Commit — DB is consistent before any network I/O
            self.db.commit()
            logger.info(f"Transfer {transfer.id} transitioned to PAYMENT_LOCKED")

            # 8. Notify receiver (PIN) — awaited directly, no asyncio.run()
            try:
                await self._send_receiver_notification(transfer, pin)
            except Exception as exc:
                logger.error(
                    f"Receiver notification failed for transfer {transfer.id}: {exc}"
                )

            # 9. Notify agent — awaited directly
            try:
                await self._send_agent_notification(transfer)
            except Exception as exc:
                logger.error(
                    f"Agent notification failed for transfer {transfer.id}: {exc}"
                )

            logger.info(
                f"Webhook processed successfully for transfer {transfer.reference}"
            )
            return {
                "status": "success",
                "transfer_id": str(transfer.id),
                "message": f"Transfer {transfer.reference} marked as payment received",
            }

        except Exception as exc:
            logger.error(
                f"Error processing invoice-settled webhook: {exc}", exc_info=True
            )
            return {
                "status": "error",
                "transfer_id": None,
                "message": f"Internal error: {exc}",
            }

    # ------------------------------------------------------------------
    # Notification helpers (async — awaited by process_lnd_invoice_settled)
    # ------------------------------------------------------------------

    async def _send_receiver_notification(
        self, transfer: Transfer, pin: str
    ) -> None:
        """Send WhatsApp notification to the receiver containing their PIN."""
        message = (
            f"💰 You have a pending remittance!\n\n"
            f"Amount: {transfer.amount_zar:.2f} ZAR\n"
            f"From: {transfer.sender_phone}\n"
            f"Reference: {transfer.reference}\n\n"
            f"🔐 Your verification PIN: {pin}\n\n"
            f"Share this PIN with the agent to receive your cash. "
            f"Do NOT share with anyone else."
        )

        logger.info(
            f"Sending receiver notification to {transfer.receiver_phone}"
        )
        result = await self.notification_service.send_whatsapp(
            phone_number=transfer.receiver_phone,
            message=message,
        )
        if result:
            logger.info(
                f"Receiver notification sent to {transfer.receiver_phone}"
            )
        else:
            logger.error(
                f"Failed to send receiver notification to {transfer.receiver_phone}"
            )

    async def _send_agent_notification(self, transfer: Transfer) -> None:
        """Send WhatsApp notification to the agent about the pending payout."""
        agent = transfer.agent
        if not agent:
            logger.warning(
                f"No agent relationship on transfer {transfer.id}; "
                "skipping agent notification"
            )
            return

        message = (
            f"📍 New payout pending!\n\n"
            f"Reference: {transfer.reference}\n"
            f"Receiver: {transfer.receiver_name}\n"
            f"Receiver Phone: {transfer.receiver_phone}\n"
            f"Amount: {transfer.amount_zar:.2f} ZAR\n\n"
            f"Receiver needs to provide PIN to verify. "
            f"Log in to SatsRemit app to confirm payout."
        )

        logger.info(f"Sending agent notification to {agent.phone}")
        result = await self.notification_service.send_whatsapp(
            phone_number=agent.phone,
            message=message,
        )
        if result:
            logger.info(f"Agent notification sent to {agent.phone}")
        else:
            logger.error(f"Failed to send agent notification to {agent.phone}")

    # ------------------------------------------------------------------
    # Utility methods (async for consistency; called from async routes)
    # ------------------------------------------------------------------

    def get_webhook_history(self, limit: int = 100) -> list:
        """Return recent webhook delivery records (synchronous DB read)."""
        return (
            self.db.query(WebhookModel)
            .order_by(WebhookModel.created_at.desc())
            .limit(limit)
            .all()
        )

    async def retry_failed_webhooks(self) -> dict:
        """
        Re-process failed webhook records.

        Called from an async FastAPI route (``POST /webhooks/retry-failed``),
        so this method is ``async def`` and awaits
        ``process_lnd_invoice_settled`` for each failed record.
        """
        failed = (
            self.db.query(WebhookModel)
            .filter(
                WebhookModel.status == "failed",
                WebhookModel.retry_count < 3,
            )
            .all()
        )

        attempted = 0
        succeeded = 0

        for webhook in failed:
            try:
                if webhook.event_type == "lnd.invoice.settled":
                    payload = webhook.payload
                    result = await self.process_lnd_invoice_settled(
                        invoice_hash=payload["invoice_hash"],
                        state=payload.get("state", "SETTLED"),
                        settled_at=datetime.fromisoformat(
                            payload.get(
                                "settled_at", datetime.utcnow().isoformat()
                            )
                        ),
                        amount_milli_satoshis=payload["amount_milli_satoshis"],
                    )

                    if result["status"] == "success":
                        webhook.status = "delivered"
                        webhook.processed_at = datetime.utcnow()
                        succeeded += 1
                    else:
                        webhook.retry_count += 1

                attempted += 1

            except Exception as exc:
                logger.error(f"Error retrying webhook {webhook.id}: {exc}")
                webhook.retry_count += 1

        self.db.commit()
        logger.info(
            f"Webhook retry complete: {succeeded} succeeded, {attempted} attempted"
        )
        return {
            "attempted": attempted,
            "succeeded": succeeded,
            "failed": attempted - succeeded,
        }
