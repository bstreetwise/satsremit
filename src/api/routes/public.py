"""
Public API Routes - No authentication required
"""

import logging
import uuid
from fastapi import APIRouter, HTTPException, Query, Depends, status
from decimal import Decimal
from typing import List

from src.api.schemas import (
    TransferCreateRequest,
    TransferInitiateResponse,
    TransferDetailResponse,
    TransferStatusResponse,
    TransferQuoteResponse,
    ErrorResponse,
)
from src.core.dependencies import get_db, get_transfer_service, get_rate_service
from src.services import TransferService, RateService
from src.models.models import Transfer, Agent

logger = logging.getLogger(__name__)

router = APIRouter()


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

@router.post("/transfers/quote")
async def quote_transfer(
    amount_zar: Decimal,
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

        return TransferQuoteResponse(
            amount_zar=fees["amount_zar"],
            amount_sats=validation["amount_sats"],
            platform_fee_zar=fees["platform_fee_zar"],
            agent_commission_zar=fees["agent_commission_zar"],
            total_fees_zar=fees["total_fees_zar"],
            receiver_gets_zar=fees["receiver_gets_zar"],
            rate_zar_per_btc=validation["rate_zar_per_btc"],
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
            Agent.status.value == "ACTIVE"
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
            Agent.status.value == "ACTIVE"
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


@router.get("/transfers/{transfer_id}/status", response_model=dict)
async def quick_status(
    transfer_id: str,
    db: Session = Depends(get_db),
):
    """
    Quick status check (minimal response)
    """
    # TODO: Implement quick status
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/agent/locations", response_model=List[AgentLocationResponse])
async def get_agent_locations(
    db: Session = Depends(get_db),
):
    """
    Get list of available agent locations
    """
    # TODO: Implement location listing
    raise HTTPException(status_code=501, detail="Not implemented")
