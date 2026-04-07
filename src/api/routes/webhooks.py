"""
Webhook routes for LND and external callbacks
"""
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
import logging

from src.db.database import get_db
from src.core.config import get_settings
from src.models.schemas import LNDInvoiceSettledWebhook

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


def verify_webhook_signature(
    x_signature: str = Header(None),
    settings: any = Depends(get_settings),
):
    """
    Verify webhook request signature
    
    HmacSha256(payload, webhook_secret) must match x_signature
    """
    if not x_signature:
        raise HTTPException(status_code=401, detail="Missing signature")
    
    # TODO: Implement signature verification
    return True


@router.post("/lnd/invoice-settled")
async def lnd_invoice_settled(
    request: LNDInvoiceSettledWebhook,
    db: Session = Depends(get_db),
    verified: bool = Depends(verify_webhook_signature),
):
    """
    LND webhook: Invoice settled callback
    
    Triggered when an invoice receives payment:
    1. Find transfer by invoice_hash
    2. Verify amount matches
    3. Transition to PAYMENT_LOCKED
    4. Notify receiver (send PIN)
    5. Notify agent (alert)
    
    Idempotent: Safe to retry
    """
    # TODO: Implement invoice settlement handling
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/lnd/invoice-expired")
async def lnd_invoice_expired(
    invoice_hash: str,
    db: Session = Depends(get_db),
    verified: bool = Depends(verify_webhook_signature),
):
    """
    LND webhook: Invoice expired callback
    
    Triggered when hold invoice expires without payment:
    1. Find transfer by invoice_hash
    2. Transition to REFUNDED
    3. Notify sender
    """
    # TODO: Implement invoice expiry handling
    raise HTTPException(status_code=501, detail="Not implemented")
