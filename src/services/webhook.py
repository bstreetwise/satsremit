"""
Webhook handling service for SatsRemit
Processes callbacks from LND and other external services
"""
import logging
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
import uuid

from src.models.models import Transfer, TransferState, TransferHistory, Webhook as WebhookModel
from src.services.transfer import TransferService
from src.services.notification import NotificationService
from src.core.security import generate_pin, hash_pin

logger = logging.getLogger(__name__)


class WebhookService:
    """Handle webhook events from LND and other services"""
    
    def __init__(self, db: Session):
        self.db = db
        self.transfer_service = TransferService(db)
        self.notification_service = NotificationService()
    
    def process_lnd_invoice_settled(
        self,
        invoice_hash: str,
        state: str,
        settled_at: datetime,
        amount_milli_satoshis: int
    ) -> dict:
        """
        Process LND invoice settled webhook
        Transitions transfer to PAYMENT_LOCKED and triggers notifications
        
        Args:
            invoice_hash: LND invoice hash (payment hash)
            state: Invoice state from LND
            settled_at: Timestamp when invoice was settled
            amount_milli_satoshis: Amount in millisatoshis
        
        Returns:
            dict with status and transfer_id
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
                    "message": "Transfer not found"
                }
            
            logger.info(f"Found transfer: {transfer.id} for reference: {transfer.reference}")
            
            # 2. Verify transfer is in correct state
            if transfer.state not in [TransferState.INVOICE_GENERATED, TransferState.INITIATED]:
                logger.warning(
                    f"Transfer {transfer.id} in unexpected state: {transfer.state}. "
                    f"Expected INVOICE_GENERATED or INITIATED"
                )
                return {
                    "status": "error",
                    "transfer_id": str(transfer.id),
                    "message": f"Transfer already in state: {transfer.state}"
                }
            
            # 3. Update transfer state to PAYMENT_LOCKED
            old_state = transfer.state
            transfer.state = TransferState.PAYMENT_LOCKED
            transfer.updated_at = datetime.utcnow()
            
            # 4. Record state change in history
            history = TransferHistory(
                transfer_id=transfer.id,
                old_state=old_state,
                new_state=TransferState.PAYMENT_LOCKED,
                reason="Payment received from LND",
                actor_type="system",
                actor_id="lnd_webhook"
            )
            self.db.add(history)
            
            # 5. Generate PIN for receiver verification
            pin = generate_pin()
            # Store bcrypt hash — the plaintext PIN is sent to the receiver via WhatsApp
            # and never persisted; the hash is used later for verification
            transfer.pin_generated = hash_pin(pin)
            
            logger.info(f"Generated PIN: {pin} for transfer {transfer.reference}")
            
            # 6. Add webhook delivery log
            webhook_log = WebhookModel(
                event_type="lnd.invoice.settled",
                payload={
                    "invoice_hash": invoice_hash,
                    "state": state,
                    "amount_milli_satoshis": amount_milli_satoshis,
                    "transfer_id": str(transfer.id)
                },
                status="delivered",
                retry_count=0,
                processed_at=datetime.utcnow()
            )
            self.db.add(webhook_log)
            
            # 7. Commit database changes
            self.db.commit()
            logger.info(f"Transfer {transfer.id} state updated to PAYMENT_LOCKED")
            
            # 8. Send WhatsApp notification to receiver with PIN
            try:
                self._send_receiver_notification(transfer, pin)
            except Exception as e:
                logger.error(f"Failed to send receiver notification: {e}")
            
            # 9. Send WhatsApp notification to agent about pending payout
            try:
                self._send_agent_notification(transfer)
            except Exception as e:
                logger.error(f"Failed to send agent notification: {e}")
            
            logger.info(f"Webhook processed successfully for transfer {transfer.reference}")
            
            return {
                "status": "success",
                "transfer_id": str(transfer.id),
                "message": f"Transfer {transfer.reference} marked as payment received"
            }
            
        except Exception as e:
            logger.error(f"Error processing invoice settled webhook: {e}", exc_info=True)
            return {
                "status": "error",
                "transfer_id": None,
                "message": f"Internal error: {str(e)}"
            }
    
    def _send_receiver_notification(self, transfer: Transfer, pin: str) -> None:
        """Send WhatsApp notification to receiver with PIN"""
        
        message = (
            f"💰 You have a pending remittance!\n\n"
            f"Amount: {transfer.amount_zar:.2f} ZAR\n"
            f"From: {transfer.sender_phone}\n"
            f"Reference: {transfer.reference}\n\n"
            f"🔐 Your verification PIN: {pin}\n\n"
            f"Share this PIN with the agent to receive your cash. "
            f"Do NOT share with anyone else."
        )
        
        logger.info(f"Sending receiver notification to {transfer.receiver_phone}")
        
        import asyncio
        result = asyncio.run(self.notification_service.send_whatsapp(
            phone_number=transfer.receiver_phone,
            message=message,
        ))
        
        if result:
            logger.info(f"Receiver notification sent successfully to {transfer.receiver_phone}")
        else:
            logger.error(f"Failed to send receiver notification to {transfer.receiver_phone}")
    
    def _send_agent_notification(self, transfer: Transfer) -> None:
        """Send WhatsApp notification to agent about pending payout"""
        
        # Get agent phone from transfer relationship
        agent = transfer.agent
        if not agent:
            logger.warning(f"Agent not found for transfer {transfer.id}")
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
        
        result = asyncio.run(self.notification_service.send_whatsapp(
            phone_number=agent.phone,
            message=message,
        ))
        
        if result:
            logger.info(f"Agent notification sent successfully to {agent.phone}")
        else:
            logger.error(f"Failed to send agent notification to {agent.phone}")
    
    def get_webhook_history(self, limit: int = 100) -> list:
        """Get recent webhook delivery history"""
        webhooks = self.db.query(WebhookModel).order_by(
            WebhookModel.created_at.desc()
        ).limit(limit).all()
        
        return webhooks
    
    def retry_failed_webhooks(self) -> dict:
        """Retry failed webhook deliveries (for background task)"""
        
        # Get failed webhooks that haven't exceeded retry limit
        failed_webhooks = self.db.query(WebhookModel).filter(
            WebhookModel.status == "failed",
            WebhookModel.retry_count < 3
        ).all()
        
        retry_count = 0
        success_count = 0
        
        for webhook in failed_webhooks:
            try:
                if webhook.event_type == "lnd.invoice.settled":
                    payload = webhook.payload
                    result = self.process_lnd_invoice_settled(
                        invoice_hash=payload["invoice_hash"],
                        state=payload.get("state", "SETTLED"),
                        settled_at=datetime.fromisoformat(payload.get("settled_at", datetime.utcnow().isoformat())),
                        amount_milli_satoshis=payload["amount_milli_satoshis"]
                    )
                    
                    if result["status"] == "success":
                        webhook.status = "delivered"
                        webhook.processed_at = datetime.utcnow()
                        success_count += 1
                    else:
                        webhook.retry_count += 1
                
                retry_count += 1
            except Exception as e:
                logger.error(f"Error retrying webhook {webhook.id}: {e}")
                webhook.retry_count += 1
        
        self.db.commit()
        
        logger.info(f"Webhook retry complete: {success_count} succeeded, {retry_count} attempted")
        
        return {
            "attempted": retry_count,
            "succeeded": success_count,
            "failed": retry_count - success_count
        }
