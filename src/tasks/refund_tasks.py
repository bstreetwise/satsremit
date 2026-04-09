"""
Refund processing tasks.

Handles refunds for failed transfers (verification timeout, payment cancellation, etc.).
"""

import logging
from datetime import datetime
from typing import Dict, Any

from sqlalchemy.orm import Session

from src.core.celery import app
from src.core.database import get_db
from src.models import Transfer
from src.services.lnd import LNDService
from src.services.notification import NotificationService

logger = logging.getLogger(__name__)


@app.task(
    name="src.tasks.refund_tasks.process_refund",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def process_refund(self, transfer_id: str) -> Dict[str, Any]:
    """
    Process refund for a transfer (to sender's wallet).
    
    Handles:
    - Verification timeout refunds
    - Cancelled transfers
    - Failed settlements
    
    Args:
        transfer_id: Transfer ID
    
    Returns:
        dict: Refund processing result
    """
    db = None
    try:
        db = next(get_db())
        lnd_service = LNDService()
        notification_service = NotificationService()
        
        transfer = db.query(Transfer).filter(
            Transfer.id == transfer_id
        ).first()
        
        if not transfer:
            logger.warning(f"Transfer {transfer_id} not found")
            return {"error": "Transfer not found"}
        
        if transfer.state != "REFUND_REQUIRED":
            logger.warning(
                f"Transfer {transfer_id} not in REFUND_REQUIRED state "
                f"(current: {transfer.state})"
            )
            return {
                "error": f"Wrong state: {transfer.state}",
            }
        
        logger.info(f"💸 Processing refund for transfer {transfer_id}")
        
        # Update state
        transfer.state = "REFUND_IN_PROGRESS"
        transfer.refund_initiated_at = datetime.utcnow()
        db.commit()
        
        # Initiate refund via LND
        # This creates a payment back to sender's wallet
        try:
            refund_result = lnd_service.send_payment(
                destination_address=transfer.sender_wallet_address,
                amount_satoshis=transfer.paid_at_satoshis,
                memo=f"Refund for transfer {transfer_id}",
            )
            
            if refund_result.get("success"):
                # Update transfer
                transfer.state = "REFUNDED"
                transfer.refund_completed_at = datetime.utcnow()
                transfer.refund_txid = refund_result.get("payment_hash")
                db.commit()
                
                logger.info(
                    f"✅ Refund processed for transfer {transfer_id}: "
                    f"tx {refund_result.get('payment_hash')}"
                )
                
                # Notify sender
                notification_service.send_message_async(
                    phone_number=transfer.sender_phone,
                    message=(
                        f"Your transfer of {transfer.amount_zar:.2f} ZAR "
                        f"has been refunded. Check your wallet."
                    ),
                    notification_type="refund_completed",
                )
                
                return {
                    "success": True,
                    "transfer_id": transfer_id,
                    "refund_txid": refund_result.get("payment_hash"),
                }
            
            else:
                raise Exception(refund_result.get("error", "Refund failed"))
        
        except Exception as e:
            logger.error(f"Refund transaction failed: {str(e)}")
            transfer.state = "REFUND_FAILED"
            db.commit()
            
            try:
                raise self.retry(exc=e, countdown=300)
            except Exception:
                return {"error": f"Refund failed: {str(e)}"}
    
    except Exception as e:
        logger.error(f"Error processing refund: {str(e)}", exc_info=True)
        
        try:
            raise self.retry(exc=e, countdown=60)
        except Exception:
            return {"error": str(e)}
    
    finally:
        if db:
            db.close()


@app.task(
    name="src.tasks.refund_tasks.retry_failed_refund",
    bind=True,
    max_retries=5,
    default_retry_delay=300,
)
def retry_failed_refund(self, transfer_id: str) -> Dict[str, Any]:
    """
    Retry a failed refund.
    
    Args:
        transfer_id: Transfer ID
    
    Returns:
        dict: Retry result
    """
    db = None
    try:
        db = next(get_db())
        
        transfer = db.query(Transfer).filter(
            Transfer.id == transfer_id
        ).first()
        
        if not transfer:
            return {"error": "Transfer not found"}
        
        if transfer.state != "REFUND_FAILED":
            logger.info(f"Transfer {transfer_id} no longer in REFUND_FAILED state")
            return {
                "status": "skipped",
                "reason": f"Current state: {transfer.state}",
            }
        
        # Try refund again
        logger.info(f"🔄 Retrying refund for transfer {transfer_id}")
        
        return process_refund.delay(transfer_id).get()
    
    except Exception as e:
        logger.error(f"Error retrying refund: {str(e)}")
        try:
            return self.retry(exc=e, countdown=300)
        except Exception:
            return {"error": str(e)}
    
    finally:
        if db:
            db.close()


__all__ = [
    "process_refund",
    "retry_failed_refund",
]
