"""
Public API Routes - No authentication required
"""

import logging
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Depends, status, Request, Body
from pydantic import BaseModel
from decimal import Decimal
from typing import List

from src.api.schemas import (
    TransferCreateRequest,
    TransferInitiateResponse,
    TransferDetailResponse,
    TransferStatusResponse,
    TransferQuoteResponse,
    ErrorResponse,
    ReceiverVerifyPINRequest,
    ReceiverVerifyPINResponse,
    ReceiverTransferStatusResponse,
    ReceiverResendPINRequest,
    ReceiverResendPINResponse,
)
from src.core.config import get_settings
from src.core.dependencies import get_db, get_transfer_service, get_rate_service
from src.core.security import verify_pin, track_failed_pin_attempt, reset_pin_attempts
from src.services import TransferService, RateService
from src.models.models import Transfer, Agent, AgentStatus

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()


# ===== RATE LIMITING =====

def check_rate_limit(client_ip: str, sender_phone: str, max_requests: int = 5, window_minutes: int = 15) -> tuple:
    """
    Check if client has exceeded rate limit
    
    Args:
        client_ip: Client IP address
        sender_phone: Sender phone number
        max_requests: Max requests per window
        window_minutes: Time window in minutes
    
    Returns:
        Tuple of (allowed: bool, error_message: str)
    """
    # TODO: Implement proper rate limiting with Redis
    # For now, allow all requests (rate limiting managed at LND/blockchain level)
    return True, None


# ===== HEALTH CHECK =====

@router.get("/health")
async def health_check():
    """
    Health check endpoint - verify all dependencies
    """
    try:
        # TODO: Check Bitcoin, LND, DB, Redis
        return {
            "status": "healthy",
            "bitcoind_synced": True,
            "lnd_active": True,
            "db_connected": True,
            "redis_connected": True,
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unhealthy"
        )


# ===== TRANSFERS: Quote =====

class QuoteRequest(BaseModel):
    amount_zar: Decimal

@router.post("/transfers/quote")
async def quote_transfer(
    amount_zar: Decimal = Body(..., embed=True),
    db = Depends(get_db),
):
    """
    Get transfer quote without creating transfer

    Args:
        amount_zar: Amount in ZAR

    Returns:
        Quote with fees and exchange rate
    """
    try:
        rate_svc = get_rate_service(db)

        # Validate amount
        validation = await rate_svc.validate_transfer_amount(amount_zar)
        if not validation["valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=validation["error"]
            )

        # Get fee breakdown
        fees = await rate_svc.get_fee_breakdown(amount_zar)
        
        # Get USD to ZAR rate (aggregated from SA + Zimbabwe markets)
        rate_usd_per_zar = await rate_svc.get_usd_per_zar()

        return TransferQuoteResponse(
            amount_zar=fees["amount_zar"],
            amount_sats=validation["amount_sats"],
            platform_fee_zar=fees["platform_fee_zar"],
            agent_commission_zar=fees["agent_commission_zar"],
            total_fees_zar=fees["total_fees_zar"],
            receiver_gets_zar=fees["receiver_gets_zar"],
            rate_zar_per_btc=validation["rate_zar_per_btc"],
            rate_usd_per_zar=rate_usd_per_zar,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Quote failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ===== TRANSFERS: Create =====

@router.post("/transfers", status_code=status.HTTP_201_CREATED)
async def create_transfer(
    request_obj: Request,
    request: TransferCreateRequest,
    db = Depends(get_db),
):
    """
    Create a new transfer and generate LND invoice

    Args:
        request: Transfer details

    Returns:
        Invoice for sender to pay
    """
    try:
        # Rate limit: IP + sender phone composite key
        client_ip = request_obj.client.host if request_obj.client else "unknown"
        allowed, error_msg = check_rate_limit(
            client_ip=client_ip,
            sender_phone=request.sender_phone,
            max_requests=settings.rate_limit_requests,
            window_minutes=settings.rate_limit_window_minutes
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error_msg
            )
        
        transfer_svc = get_transfer_service(db)
        rate_svc = get_rate_service(db)

        # Validate amount
        validation = await rate_svc.validate_transfer_amount(request.amount_zar)
        if not validation["valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=validation["error"]
            )

        # Find agent for location
        agent = db.query(Agent).filter(
            Agent.location_code == request.receiver_location,
            Agent.status == AgentStatus.ACTIVE
        ).first()

        if not agent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No active agent in {request.receiver_location}"
            )

        # Check agent has sufficient cash
        if agent.cash_balance_zar < request.amount_zar:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agent insufficient cash - try again later"
            )

        # Create transfer
        transfer = await transfer_svc.initiate_transfer(
            sender_phone=request.sender_phone,
            receiver_phone=request.receiver_phone,
            receiver_name=request.receiver_name,
            receiver_location=request.receiver_location,
            amount_zar=request.amount_zar,
            amount_sats=validation["amount_sats"],
            rate_zar_per_btc=validation["rate_zar_per_btc"],
            agent_id=agent.id,
        )

        # Generate invoice
        invoice = await transfer_svc.generate_invoice(transfer.id)

        logger.info(f"Transfer created: {transfer.reference}")

        return TransferInitiateResponse(
            transfer_id=str(transfer.id),
            reference=transfer.reference,
            invoice_hash=invoice["payment_hash"],
            invoice_request=invoice["payment_request"],
            amount_sats=transfer.amount_sats,
            amount_zar=transfer.amount_zar,
            expires_at=invoice["invoice_expiry_at"],
            agent_name=agent.name,
            agent_location=agent.location_name,
            status_url=f"/api/transfers/{transfer.id}/status",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transfer creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create transfer"
        )


# ===== TRANSFERS: Status =====

@router.get("/transfers/{transfer_id}/status")
async def get_transfer_status(
    transfer_id: str,
    db = Depends(get_db),
):
    """
    Get transfer status by ID

    Returns:
        Current state and progress
    """
    try:
        transfer = db.query(Transfer).filter(
            Transfer.id == uuid.UUID(transfer_id)
        ).first()

        if not transfer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transfer not found"
            )

        return TransferStatusResponse(
            reference=transfer.reference,
            state=transfer.state,
            receiver_phone_verified=transfer.receiver_phone_verified,
            agent_verified=transfer.agent_verified,
            receiver_received=transfer.state.value == "SETTLED",
            settlement_date=transfer.settled_at,
        )

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid transfer ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get status"
        )


# ===== TRANSFERS: Check Payment =====

@router.post("/transfers/{transfer_id}/check-payment")
async def check_transfer_payment(
    transfer_id: str,
    db = Depends(get_db),
):
    """
    Check if payment has been received for a transfer

    Returns:
        Updated transfer status
    """
    try:
        transfer = db.query(Transfer).filter(
            Transfer.id == uuid.UUID(transfer_id)
        ).first()

        if not transfer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transfer not found"
            )

        # Check if payment received via LND
        transfer_svc = get_transfer_service(db)
        is_paid = await transfer_svc.check_payment_received(transfer.id)

        return {
            "transfer_id": str(transfer.id),
            "reference": transfer.reference,
            "state": transfer.state,
            "payment_received": is_paid,
            "amount_sats": transfer.amount_sats,
            "receiver_phone_verified": transfer.receiver_phone_verified,
            "agent_verified": transfer.agent_verified,
        }

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid transfer ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Payment check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check payment status"
        )


# ===== TRANSFERS: By Reference =====

@router.get("/transfers/ref/{reference}")
async def get_transfer_by_reference(
    reference: str,
    db = Depends(get_db),
):
    """
    Get transfer by reference number

    Returns:
        Transfer details (non-sensitive)
    """
    try:
        transfer = db.query(Transfer).filter(
            Transfer.reference == reference.upper()
        ).first()

        if not transfer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transfer not found"
            )

        return TransferDetailResponse(
            transfer_id=str(transfer.id),
            reference=transfer.reference,
            state=transfer.state,
            sender_phone=transfer.sender_phone,
            receiver_phone=transfer.receiver_phone,
            receiver_name=transfer.receiver_name,
            amount_zar=transfer.amount_zar,
            amount_sats=transfer.amount_sats,
            rate_zar_per_btc=transfer.rate_zar_per_btc,
            created_at=transfer.created_at,
            invoice_expiry_at=transfer.invoice_expiry_at,
            payout_at=transfer.payout_at,
            settled_at=transfer.settled_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reference lookup failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get transfer"
        )


# ===== LOCATIONS: List Agents =====

@router.get("/locations")
async def list_agent_locations(db = Depends(get_db)):
    """
    List all agent service locations

    Returns:
        Available agents by location
    """
    try:
        agents = db.query(Agent).filter(
            Agent.status == AgentStatus.ACTIVE
        ).all()

        if not agents:
            return {
                "locations": [],
                "message": "No agents available"
            }

        locations = []
        for agent in agents:
            locations.append({
                "location_code": agent.location_code,
                "location_name": agent.location_name,
                "agent_name": agent.name,
                "agent_phone": agent.phone,
                "rating": float(agent.rating) if agent.rating else None,
                "total_transfers": agent.total_transfers,
            })

        return {
            "locations": locations,
            "count": len(locations),
        }

    except Exception as e:
        logger.error(f"Location listing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list locations"
        )


# ===== RATES: Current Rate =====

@router.get("/rates/zar-btc")
async def get_rate(db = Depends(get_db)):
    """
    Get current ZAR/BTC exchange rate

    Returns:
        Exchange rate and source
    """
    try:
        rate_svc = get_rate_service(db)
        rate = await rate_svc.get_zar_per_btc()

        return {
            "pair": "ZAR_BTC",
            "rate": str(rate),
            "source": "coingecko",
            "updated_at": "now",  # TODO: Get from cache
        }

    except Exception as e:
        logger.error(f"Rate fetch failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get exchange rate"
        )


# ===== RECEIVER: Verify PIN =====

@router.post("/receivers/verify-pin", response_model=ReceiverVerifyPINResponse)
async def receiver_verify_pin(
    request: ReceiverVerifyPINRequest,
    db = Depends(get_db),
):
    """
    Verify receiver with PIN to confirm transfer receipt
    
    Receiver receives PIN via WhatsApp after payment is locked.
    They use this endpoint to verify they received the transfer.
    
    Args:
        request: ReceiverVerifyPINRequest with reference, phone, and PIN
        
    Returns:
        Verification status
    """
    try:
        # Find transfer by reference
        transfer = db.query(Transfer).filter(
            Transfer.reference == request.reference.upper(),
            Transfer.receiver_phone == request.phone,
        ).first()

        if not transfer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transfer not found or phone mismatch"
            )

        # Check if already verified
        if transfer.receiver_phone_verified:
            return ReceiverVerifyPINResponse(
                verified=True,
                message="Transfer already verified",
                transfer_id=str(transfer.id),
                amount_zar=transfer.amount_zar,
                receiver_name=transfer.receiver_name,
            )

        # Check if transfer is in correct state (PAYMENT_LOCKED)
        if transfer.state != "PAYMENT_LOCKED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Transfer is in {transfer.state} state, cannot verify PIN now"
            )

        # Check brute-force protection
        failed_attempts = track_failed_pin_attempt(str(transfer.id))
        if failed_attempts is not None and failed_attempts > 5:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed attempts. Try again in 30 minutes."
            )

        # Verify PIN against bcrypt hash
        if not transfer.pin_generated or not verify_pin(transfer.pin_generated, request.pin):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid PIN"
            )

        # PIN verified - mark receiver as verified
        reset_pin_attempts(str(transfer.id))
        transfer.receiver_phone_verified = True
        transfer.verification_completed_at = datetime.utcnow()
        
        # If agent already verified, transition to RECEIVER_VERIFIED
        if transfer.agent_verified:
            transfer.state = "RECEIVER_VERIFIED"
        
        db.commit()

        logger.info(
            f"Receiver verified for transfer {transfer.reference}: "
            f"{transfer.receiver_phone}"
        )

        return ReceiverVerifyPINResponse(
            verified=True,
            message="Transfer verified successfully",
            transfer_id=str(transfer.id),
            amount_zar=transfer.amount_zar,
            receiver_name=transfer.receiver_name,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PIN verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify PIN"
        )


# ===== RECEIVER: Check Transfer Status =====

@router.get("/receivers/transfers/{reference}/status", response_model=ReceiverTransferStatusResponse)
async def receiver_get_transfer_status(
    reference: str,
    phone: str = Query(..., description="Receiver phone number"),
    db = Depends(get_db),
):
    """
    Get transfer status for receiver (public, no auth)
    
    Allows receiver to check transfer status by reference and phone.
    Used by receiver verification page to show transfer details.
    
    Args:
        reference: Transfer reference number
        phone: Receiver phone number (for verification)
        
    Returns:
        Transfer status visible to receiver
    """
    try:
        transfer = db.query(Transfer).filter(
            Transfer.reference == reference.upper(),
            Transfer.receiver_phone == phone,
        ).first()

        if not transfer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transfer not found"
            )

        return ReceiverTransferStatusResponse(
            reference=transfer.reference,
            transfer_id=str(transfer.id),
            receiver_name=transfer.receiver_name,
            amount_zar=transfer.amount_zar,
            state=transfer.state,
            receiver_phone_verified=transfer.receiver_phone_verified,
            agent_verified=transfer.agent_verified,
            created_at=transfer.created_at,
            expires_at=transfer.invoice_expiry_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Receiver status check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get transfer status"
        )


# ===== RECEIVER: Resend PIN =====

@router.post("/receivers/resend-pin", response_model=ReceiverResendPINResponse)
async def receiver_resend_pin(
    request: ReceiverResendPINRequest,
    db = Depends(get_db),
):
    """
    Request PIN resend via WhatsApp
    
    Receiver can request PIN to be resent if they didn't receive it.
    Rate limited to once per 5 minutes per transfer.
    
    Args:
        request: ReceiverResendPINRequest with reference and phone
        
    Returns:
        Resend status and next available time
    """
    try:
        from src.services.notification import NotificationService
        
        # Find transfer
        transfer = db.query(Transfer).filter(
            Transfer.reference == request.reference.upper(),
            Transfer.receiver_phone == request.phone,
        ).first()

        if not transfer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transfer not found"
            )

        # Check if already verified
        if transfer.receiver_phone_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transfer already verified"
            )

        # Check if transfer is in correct state
        if transfer.state != "PAYMENT_LOCKED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot resend PIN for transfer in {transfer.state} state"
            )

        # Check rate limiting (max 1 resend per 5 minutes)
        # Implementation: check if last_pin_resent_at exists and is < 5 minutes ago
        if transfer.last_pin_resent_at:
            minutes_since_last_resend = (
                (datetime.utcnow() - transfer.last_pin_resent_at).total_seconds() / 60
            )
            if minutes_since_last_resend < 5:
                next_resend_in = int(300 - (minutes_since_last_resend * 60))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Please wait before requesting another PIN"
                )

        # Note: We cannot resend the plain PIN since it's bcrypt-hashed
        # Instead, we generate a NEW PIN, hash it, and send it
        from src.core.security import generate_pin, hash_pin
        
        new_pin = generate_pin()
        new_pin_hash = hash_pin(new_pin)
        transfer.pin_generated = new_pin_hash
        transfer.last_pin_resent_at = datetime.utcnow()
        db.commit()

        # Send new PIN via WhatsApp
        notification_service = NotificationService()
        await notification_service.send_pin_to_receiver(
            phone_number=transfer.receiver_phone,
            pin=new_pin,
            transfer_reference=transfer.reference,
            amount_zar=float(transfer.amount_zar),
        )

        logger.info(
            f"PIN resent to receiver {transfer.receiver_phone} "
            f"for transfer {transfer.reference}"
        )

        return ReceiverResendPINResponse(
            success=True,
            message="PIN resent successfully",
            next_resend_in_seconds=300,  # 5 minutes
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PIN resend failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resend PIN"
        )



