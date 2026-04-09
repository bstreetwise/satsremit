"""
Invoice payment monitoring tasks.

Polls LND every 30 seconds to check for newly settled invoices,
triggers webhook processing when payments are detected.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import and_

from src.core.celery import app
from src.core.database import get_db
from src.core.config import settings
from src.services.lnd import LNDService
from src.services.webhook import WebhookService
from src.models import Transfer
from src.api.schemas import LNDInvoiceSettledWebhook

logger = logging.getLogger(__name__)


@app.task(
    name="src.tasks.invoice_tasks.monitor_lnd_invoices",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def monitor_lnd_invoices(self):
    """
    Poll LND for newly settled invoices every 30 seconds.
    
    This task:
    1. Connects to LND gRPC API
    2. Lists all invoices with state=SETTLED
    3. Finds matching transfer records
    4. Processes webhooks for unseen settlements
    5. Updates last_checked timestamps
    
    Returns:
        dict: {"checked": int, "settled": int, "processed": int, "errors": int}
    """
    db = None
    try:
        db = next(get_db())
        lnd_service = LNDService()
        webhook_service = WebhookService()
        
        stats = {
            "checked": 0,
            "settled": 0,
            "processed": 0,
            "errors": 0,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        logger.info("🔍 Starting invoice monitoring cycle...")
        
        # Get all pending transfers waiting for payment
        pending_transfers = db.query(Transfer).filter(
            Transfer.state == "INVOICE_GENERATED"
        ).all()
        
        stats["checked"] = len(pending_transfers)
        logger.info(f"Found {len(pending_transfers)} pending transfers")
        
        # Check each transfer's invoice status in LND
        for transfer in pending_transfers:
            try:
                # Look up invoice in LND
                invoice_info = lnd_service.lookup_invoice(
                    transfer.invoice_hash
                )
                
                if not invoice_info:
                    continue
                
                # Check if settled
                if invoice_info.get("state") == "SETTLED":
                    stats["settled"] += 1
                    
                    if transfer.webhook_received_at is None:
                        # First time seeing this settlement
                        logger.info(
                            f"✅ Settlement detected for transfer {transfer.id}"
                        )
                        
                        # Process the webhook
                        webhook_payload = LNDInvoiceSettledWebhook(
                            invoice_hash=transfer.invoice_hash,
                            state="SETTLED",
                            settled_at=datetime.utcnow(),
                            amount_milli_satoshis=int(
                                invoice_info.get("amount_milli_satoshis", 0)
                            ),
                        )
                        
                        # Process via WebhookService
                        result = webhook_service.process_lnd_invoice_settled(
                            webhook_payload,
                            db,
                        )
                        
                        if result.get("success"):
                            stats["processed"] += 1
                            logger.info(
                                f"✅ Webhook processed for transfer {transfer.id}"
                            )
                        else:
                            stats["errors"] += 1
                            logger.error(
                                f"❌ Failed to process webhook: {result.get('error')}"
                            )
                
            except Exception as e:
                stats["errors"] += 1
                logger.error(
                    f"Error processing transfer {transfer.id}: {str(e)}"
                )
        
        logger.info(
            f"📊 Monitoring cycle complete: "
            f"checked={stats['checked']}, "
            f"settled={stats['settled']}, "
            f"processed={stats['processed']}, "
            f"errors={stats['errors']}"
        )
        
        return stats
    
    except Exception as e:
        logger.error(f"❌ Invoice monitoring task failed: {str(e)}", exc_info=True)
        stats = {
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # Retry with exponential backoff
        try:
            raise self.retry(exc=e, countdown=60)
        except Exception:
            return stats
    
    finally:
        if db:
            db.close()


@app.task(
    name="src.tasks.invoice_tasks.get_invoice_status",
    bind=True,
    max_retries=2,
)
def get_invoice_status(self, transfer_id: str) -> Dict[str, Any]:
    """
    Get the current status of a specific invoice.
    
    Args:
        transfer_id: Transfer ID
    
    Returns:
        dict: Invoice status information
    """
    db = None
    try:
        db = next(get_db())
        
        transfer = db.query(Transfer).filter(
            Transfer.id == transfer_id
        ).first()
        
        if not transfer:
            logger.warning(f"Transfer {transfer_id} not found")
            return {"error": "Transfer not found", "transfer_id": transfer_id}
        
        lnd_service = LNDService()
        invoice_info = lnd_service.lookup_invoice(transfer.invoice_hash)
        
        return {
            "transfer_id": transfer_id,
            "state": transfer.state,
            "invoice_state": invoice_info.get("state") if invoice_info else "NOT_FOUND",
            "settled_at": transfer.settled_at.isoformat() if transfer.settled_at else None,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    except Exception as e:
        logger.error(f"Error getting invoice status: {str(e)}")
        try:
            return self.retry(exc=e, countdown=30)
        except Exception:
            return {"error": str(e)}
    
    finally:
        if db:
            db.close()


@app.task(
    name="src.tasks.invoice_tasks.cleanup_expired_invoices",
    bind=True,
)
def cleanup_expired_invoices(self) -> Dict[str, Any]:
    """
    Clean up invoices that expired without payment.
    
    Transfers with INVOICE_GENERATED state older than configured TTL
    are transitioned to INVOICE_EXPIRED.
    
    Returns:
        dict: Cleanup statistics
    """
    db = None
    try:
        db = next(get_db())
        
        # Default TTL: 1 hour (3600 seconds)
        invoice_ttl_seconds = int(os.getenv("INVOICE_TTL_SECONDS", "3600"))
        expiry_time = datetime.utcnow() - timedelta(
            seconds=invoice_ttl_seconds
        )
        
        # Find expired invoices
        expired = db.query(Transfer).filter(
            and_(
                Transfer.state == "INVOICE_GENERATED",
                Transfer.created_at < expiry_time,
            )
        ).all()
        
        count = len(expired)
        
        for transfer in expired:
            transfer.state = "INVOICE_EXPIRED"
            logger.info(f"Marked transfer {transfer.id} as INVOICE_EXPIRED")
        
        db.commit()
        
        logger.info(f"✅ Cleaned up {count} expired invoices")
        
        return {
            "expired_count": count,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    except Exception as e:
        logger.error(f"Error cleaning up expired invoices: {str(e)}")
        return {"error": str(e)}
    
    finally:
        if db:
            db.close()


__all__ = [
    "monitor_lnd_invoices",
    "get_invoice_status",
    "cleanup_expired_invoices",
]
