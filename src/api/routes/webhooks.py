"""
Webhook API Routes - Receive callbacks from LND and other services
"""
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session
from src.core.dependencies import get_db
from src.core.security import verify_webhook_hmac
from src.api.schemas import LNDInvoiceSettledWebhook, LNDInvoiceSettledResponse
from src.services.webhook import WebhookService
import logging
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/lnd/invoice-settled")
async def handle_lnd_invoice_settled(
    request: Request,
    webhook: LNDInvoiceSettledWebhook,
    db: Session = Depends(get_db),
    x_webhook_signature: Optional[str] = Header(None, alias="X-Webhook-Signature"),
) -> LNDInvoiceSettledResponse:
    """
    Webhook endpoint for LND invoice settled event
    
    Called by LND when an invoice is fully paid.
    Triggers transfer state transition and notifications.
    
    **Setup LND webhook:**
    ```bash
    # Update LND config to post to this endpoint
    lnd_config_file = /data/lnd/lnd.conf
    
    # Add to [Application Options]:
    accept-keysend=true
    
    # Subscribe to invoice events (via API):
    lncli subscribeinvoices
    ```
    
    **Payload Example:**
    ```json
    {
        "invoice_hash": "abc123...",
        "state": "SETTLED",
        "settled_at": "2026-04-09T14:30:00Z",
        "amount_milli_satoshis": 208333000
    }
    ```
    
    **Response:**
    ```json
    {
        "status": "success",
        "transfer_id": "550e8400-e29b-41d4-a716-446655440000",
        "message": "Transfer marked as payment received"
    }
    ```
    """
    
    try:
        # Verify HMAC-SHA256 signature from LND
        body = await request.body()
        if not verify_webhook_hmac(body, x_webhook_signature or ""):
            logger.warning("Webhook signature verification failed")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature",
            )

        logger.info(f"Received invoice settled webhook for: {webhook.invoice_hash}")

        # Create webhook service
        webhook_service = WebhookService(db)
        
        # Process the webhook
        result = webhook_service.process_lnd_invoice_settled(
            invoice_hash=webhook.invoice_hash,
            state=webhook.state,
            settled_at=webhook.settled_at,
            amount_milli_satoshis=webhook.amount_milli_satoshis
        )
        
        # Return response
        return LNDInvoiceSettledResponse(
            status=result["status"],
            transfer_id=result.get("transfer_id"),
            message=result["message"]
        )
        
    except Exception as e:
        logger.error(f"Error handling invoice settled webhook: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook"
        )


@router.get("/health")
async def webhook_health():
    """Health check for webhook service"""
    return {
        "status": "healthy",
        "service": "webhooks",
        "endpoints": [
            "POST /api/webhooks/lnd/invoice-settled"
        ]
    }


@router.get("/history")
async def get_webhook_history(
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get recent webhook delivery history
    Useful for debugging and monitoring webhook processing
    """
    try:
        webhook_service = WebhookService(db)
        webhooks = webhook_service.get_webhook_history(limit=limit)
        
        return {
            "count": len(webhooks),
            "webhooks": [
                {
                    "id": str(w.id),
                    "event_type": w.event_type,
                    "status": w.status,
                    "retry_count": w.retry_count,
                    "created_at": w.created_at,
                    "processed_at": w.processed_at,
                    "error": w.error_message
                }
                for w in webhooks
            ]
        }
    except Exception as e:
        logger.error(f"Error retrieving webhook history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve webhook history"
        )


@router.post("/retry-failed")
async def retry_failed_webhooks(
    db: Session = Depends(get_db)
):
    """
    Manually retry failed webhook deliveries
    Called by background tasks periodically
    """
    try:
        webhook_service = WebhookService(db)
        result = webhook_service.retry_failed_webhooks()
        
        return {
            "status": "success",
            "attempted": result["attempted"],
            "succeeded": result["succeeded"],
            "failed": result["failed"]
        }
    except Exception as e:
        logger.error(f"Error retrying webhooks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retry webhooks"
        )


@router.post("/lnd/invoice-expired")
async def lnd_invoice_expired(
    request: Request,
    invoice_hash: str,
    db: Session = Depends(get_db),
    x_webhook_signature: Optional[str] = Header(None, alias="X-Webhook-Signature"),
):
    """
    LND webhook: Invoice expired callback

    Triggered when a hold invoice expires without payment.
    Transitions the matching transfer to REFUNDED and notifies the sender.
    """
    body = await request.body()
    if not verify_webhook_hmac(body, x_webhook_signature or ""):
        logger.warning("Invoice-expired webhook signature verification failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    # TODO: Implement full invoice expiry handling
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented")
