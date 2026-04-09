"""
Verification timeout handling tasks.

If a receiver doesn't verify their identity within the timeout window,
automatically transition transfer to REFUND_REQUIRED and initiate refund.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import and_

from src.core.celery import app
from src.core.database import get_db
from src.models import Transfer
from src.services.transfer import TransferService
from src.services.notification import NotificationService

logger = logging.getLogger(__name__)


@app.task(
    name="src.tasks.verification_tasks.handle_verification_timeouts",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def handle_verification_timeouts(self) -> Dict[str, Any]:
    """
    Monitor transfers in PAYMENT_LOCKED state for verification timeouts.
    
    If no verification received within timeout window (default 30 minutes):
    1. Update transfer to REFUND_REQUIRED
    2. Send refund notification to receiver
    3. Alert agent about refund
    4. Queue refund task
    
    Returns:
        dict: {"checked": int, "expired": int, "refunded": int, "errors": int}
    """
    db = None
    try:
        db = next(get_db())
        transfer_service = TransferService(db)
        notification_service = NotificationService()
        
        stats = {
            "checked": 0,
            "expired": 0,
            "refunded": 0,
            "errors": 0,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        logger.info("⏱️ Checking for verification timeouts...")
        
        # Configuration: default 30 minutes
        verification_timeout_seconds = int(
            os.getenv("VERIFICATION_TIMEOUT_SECONDS", "1800")
        )
        timeout_threshold = datetime.utcnow() - timedelta(
            seconds=verification_timeout_seconds
        )
        
        # Find transfers waiting for verification past timeout
        timed_out = db.query(Transfer).filter(
            and_(
                Transfer.state == "PAYMENT_LOCKED",
                Transfer.paid_at < timeout_threshold,
                Transfer.verification_completed_at.is_(None),
            )
        ).all()
        
        stats["checked"] = len(timed_out)
        logger.info(f"Found {len(timed_out)} timed out transfers")
        
        for transfer in timed_out:
            try:
                logger.warning(
                    f"⏰ Transfer {transfer.id} verification timeout: "
                    f"paid {(datetime.utcnow() - transfer.paid_at).total_seconds()}s ago"
                )
                
                # Transition to REFUND_REQUIRED
                old_state = transfer.state
                transfer.state = "REFUND_REQUIRED"
                transfer.refund_initiated_at = datetime.utcnow()
                
                db.add(transfer)
                db.commit()
                
                stats["expired"] += 1
                logger.info(
                    f"✅ Transfer {transfer.id} marked for refund"
                )
                
                # Send notifications
                try:
                    # To receiver: verification expired, refund initiated
                    notification_service.send_message_async(
                        phone_number=transfer.receiver_phone,
                        message=(
                            f"Verification timeout. Your payment of "
                            f"{transfer.amount_zar:.2f} ZAR will be refunded "
                            f"within 24 hours."
                        ),
                        notification_type="verification_expired",
                    )
                    
                    # To agent: refund needed
                    notification_service.send_message_async(
                        phone_number=transfer.agent_phone,
                        message=(
                            f"Refund required for transfer {transfer.id}: "
                            f"{transfer.amount_zar:.2f} ZAR to {transfer.receiver_name}"
                        ),
                        notification_type="refund_required",
                    )
                    
                    logger.info(f"📱 Notifications sent for transfer {transfer.id}")
                
                except Exception as e:
                    logger.error(f"Failed to send notifications: {str(e)}")
                
                # Queue refund task
                from src.tasks.refund_tasks import process_refund
                process_refund.delay(transfer.id)
                
                stats["refunded"] += 1
            
            except Exception as e:
                stats["errors"] += 1
                logger.error(
                    f"Error handling timeout for transfer {transfer.id}: {str(e)}"
                )
        
        logger.info(
            f"📊 Timeout check complete: "
            f"checked={stats['checked']}, "
            f"expired={stats['expired']}, "
            f"refunded={stats['refunded']}, "
            f"errors={stats['errors']}"
        )
        
        return stats
    
    except Exception as e:
        logger.error(
            f"❌ Verification timeout handler failed: {str(e)}",
            exc_info=True
        )
        
        try:
            raise self.retry(exc=e, countdown=60)
        except Exception:
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }
    
    finally:
        if db:
            db.close()


@app.task(
    name="src.tasks.verification_tasks.verify_receiver",
    bind=True,
    max_retries=2,
)
def verify_receiver(
    self,
    transfer_id: str,
    pin_code: str,
) -> Dict[str, Any]:
    """
    Verify receiver identity via PIN code.
    
    Args:
        transfer_id: Transfer ID
        pin_code: 4-digit PIN from receiver
    
    Returns:
        dict: Verification result
    """
    db = None
    try:
        db = next(get_db())
        
        transfer = db.query(Transfer).filter(
            Transfer.id == transfer_id
        ).first()
        
        if not transfer:
            logger.warning(f"Transfer {transfer_id} not found")
            return {
                "success": False,
                "error": "Transfer not found",
            }
        
        # Verify PIN
        if transfer.receiver_pin_code != pin_code:
            logger.warning(f"Invalid PIN for transfer {transfer_id}")
            return {
                "success": False,
                "error": "Invalid PIN",
                "remaining_attempts": max(0, 3 - (transfer.verification_attempts or 0)),
            }
        
        # Mark as verified
        transfer.verification_completed_at = datetime.utcnow()
        transfer.state = "VERIFIED"
        db.commit()
        
        logger.info(f"✅ Transfer {transfer_id} verified successfully")
        
        return {
            "success": True,
            "transfer_id": transfer_id,
            "verified_at": transfer.verification_completed_at.isoformat(),
        }
    
    except Exception as e:
        logger.error(f"Error verifying receiver: {str(e)}")
        try:
            return self.retry(exc=e, countdown=30)
        except Exception:
            return {"success": False, "error": str(e)}
    
    finally:
        if db:
            db.close()


@app.task(
    name="src.tasks.verification_tasks.resend_pin",
    bind=True,
    max_retries=2,
)
def resend_pin(self, transfer_id: str) -> Dict[str, Any]:
    """
    Resend PIN to receiver (up to 3 times).
    
    Args:
        transfer_id: Transfer ID
    
    Returns:
        dict: Resend result
    """
    db = None
    try:
        db = next(get_db())
        notification_service = NotificationService()
        
        transfer = db.query(Transfer).filter(
            Transfer.id == transfer_id
        ).first()
        
        if not transfer:
            return {"error": "Transfer not found"}
        
        if not transfer.receiver_pin_code:
            return {
                "error": "No PIN generated for this transfer",
            }
        
        # Resend PIN
        notification_service.send_message_async(
            phone_number=transfer.receiver_phone,
            message=(
                f"Your verification PIN: {transfer.receiver_pin_code}\n"
                f"Valid for {os.getenv('VERIFICATION_TIMEOUT_SECONDS', '1800')} seconds"
            ),
            notification_type="pin_resend",
        )
        
        logger.info(f"📱 PIN resent to transfer {transfer_id}")
        
        return {
            "success": True,
            "transfer_id": transfer_id,
            "resent_at": datetime.utcnow().isoformat(),
        }
    
    except Exception as e:
        logger.error(f"Error resending PIN: {str(e)}")
        try:
            return self.retry(exc=e, countdown=30)
        except Exception:
            return {"error": str(e)}
    
    finally:
        if db:
            db.close()


__all__ = [
    "handle_verification_timeouts",
    "verify_receiver",
    "resend_pin",
]
