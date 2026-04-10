"""
Agent API Routes - Authenticated agent operations
"""

import logging
import uuid
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from typing import List

from src.api.schemas import (
    AgentLoginRequest,
    AgentLoginResponse,
    AgentBalanceResponse,
    AgentTransferResponse,
    AgentVerifyRequest,
    AgentVerifyResponse,
    AgentConfirmPayoutRequest,
    AgentConfirmPayoutResponse,
    SettlementResponse,
    SettlementConfirmRequest,
    SettlementConfirmResponse,
)
from pydantic import BaseModel, Field
from src.core.dependencies import get_db, get_transfer_service, get_rate_service
from src.core.security import (
    track_failed_pin_attempt,
    reset_pin_attempts,
    hash_password,
    verify_password,
    create_token,
    get_current_agent,
    verify_pin,
)
from src.models.models import Agent, Transfer, TransferState, Settlement
from src.services import NotificationService
from decimal import Decimal

logger = logging.getLogger(__name__)

router = APIRouter()


# ===== AUTHENTICATION =====

@router.post("/auth/login", response_model=AgentLoginResponse)
async def agent_login(
    request: AgentLoginRequest,
    db: Session = Depends(get_db),
):
    """
    Agent login - phone + password

    Returns:
        JWT token for authenticated requests
    """
    try:
        agent = db.query(Agent).filter(Agent.phone == request.phone).first()

        if not agent:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

        if not verify_password(request.password, agent.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

        if agent.status.value != "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Agent account is not active"
            )

        # Block login until the agent sets their own password
        if agent.must_change_password:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Password change required before first use",
                headers={"X-Change-Password-URL": "/api/agent/auth/change-password"},
            )

        # Create token — embed is_admin so admin endpoints can gate on it
        token = create_token(
            subject=f"agent:{agent.id}",
            agent_id=str(agent.id),
            is_admin=agent.is_admin,
        )

        logger.info(f"Agent logged in: {agent.phone}")

        return AgentLoginResponse(
            token=token,
            token_type="bearer",
            expires_in=86400,  # 24 hours
            agent_id=str(agent.id),
            agent_name=agent.name,
            agent_phone=agent.phone,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


# ===== CHANGE PASSWORD =====

class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=12)


@router.post("/auth/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    request: ChangePasswordRequest,
    db: Session = Depends(get_db),
):
    """
    Change agent password.

    Used on first login (when ``must_change_password`` is True) and for
    voluntary password resets.  The current password must be supplied to
    prevent unauthorised resets via a stolen session.
    """
    try:
        # Accept the temporary password as the "current" credential so the
        # agent can change it without first logging in normally.
        agent = db.query(Agent).filter(
            Agent.phone.isnot(None)  # placeholder — phone comes from request body
        ).first()

        # For security, require phone + current password in the body
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Supply phone, current_password, and new_password"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password change failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password"
        )


class ChangePasswordWithPhoneRequest(BaseModel):
    phone: str = Field(..., min_length=10, max_length=20)
    current_password: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=12)


@router.post("/auth/set-password", status_code=status.HTTP_200_OK)
async def set_password(
    request: ChangePasswordWithPhoneRequest,
    db: Session = Depends(get_db),
):
    """
    Set a new password (used for first-login password change).

    Does not require an existing JWT so that newly created agents can
    authenticate with their temporary password and immediately set a
    permanent one.
    """
    try:
        agent = db.query(Agent).filter(Agent.phone == request.phone).first()

        if not agent:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

        if not verify_password(request.current_password, agent.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

        agent.password_hash = hash_password(request.new_password)
        agent.must_change_password = False
        db.commit()

        logger.info(f"Password changed for agent: {agent.phone}")
        return {"detail": "Password updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password set failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set password"
        )


# ===== ACCOUNT =====

@router.get("/balance", response_model=AgentBalanceResponse)
async def get_agent_balance(
    db: Session = Depends(get_db),
    current_agent: dict = Depends(get_current_agent),
):
    """
    Get agent balance - cash, commissions, settlements

    Returns:
        Current balance information
    """
    try:
        agent_id = uuid.UUID(current_agent["agent_id"])
        agent = db.query(Agent).filter(Agent.id == agent_id).first()

        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )

        # Convert commission sats to ZAR using live exchange rate
        rate_svc = get_rate_service(db)
        live_rate = await rate_svc.get_zar_per_btc()
        commission_zar = Decimal(agent.commission_balance_sats) / Decimal("100000000") * live_rate

        # Get pending settlements
        pending = db.query(Settlement).filter(
            Settlement.agent_id == agent.id,
            Settlement.status == "PENDING"
        ).first()

        pending_zar = pending.amount_zar_owed if pending else Decimal("0.00")

        return AgentBalanceResponse(
            cash_balance_zar=agent.cash_balance_zar,
            commission_balance_sats=agent.commission_balance_sats,
            total_commission_zar=commission_zar,
            pending_settlement_zar=pending_zar,
            payout_date="Sunday",  # TODO: Calculate next payout date
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Balance fetch failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get balance"
        )


# ===== TRANSFERS =====

@router.get("/transfers", response_model=List[AgentTransferResponse])
async def get_pending_transfers(
    db: Session = Depends(get_db),
    current_agent: dict = Depends(get_current_agent),
):
    """
    Get pending transfers awaiting verification

    Returns:
        List of transfers in PAYMENT_LOCKED state
    """
    try:
        agent_id = uuid.UUID(current_agent["agent_id"])

        transfers = db.query(Transfer).filter(
            Transfer.agent_id == agent_id,
            Transfer.state == TransferState.PAYMENT_LOCKED,
        ).all()

        results = []
        for t in transfers:
            results.append(AgentTransferResponse(
                transfer_id=str(t.id),
                reference=t.reference,
                receiver_name=t.receiver_name,
                receiver_phone=t.receiver_phone,
                receiver_location=t.receiver_location,
                amount_zar=t.amount_zar,
                amount_sats=t.amount_sats,
                created_at=t.created_at,
                expires_at=t.invoice_expiry_at,
            ))

        return results

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get pending transfers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get transfers"
        )


@router.post("/transfers/{transfer_id}/verify", response_model=AgentVerifyResponse)
async def verify_transfer(
    transfer_id: str,
    request: AgentVerifyRequest,
    db: Session = Depends(get_db),
    current_agent: dict = Depends(get_current_agent),
):
    """
    Verify receiver - PIN + phone dual verification

    Validates PIN and confirms phone number.
    Transitions transfer to RECEIVER_VERIFIED.
    """
    try:
        agent_id = uuid.UUID(current_agent["agent_id"])
        xfer_id = uuid.UUID(transfer_id)

        transfer = db.query(Transfer).filter(
            Transfer.id == xfer_id,
            Transfer.agent_id == agent_id,
        ).first()

        if not transfer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transfer not found"
            )

        # Check for brute-force before verifying PIN
        allowed, error_msg = track_failed_pin_attempt(transfer_id)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error_msg
            )
        
        # Verify PIN against stored bcrypt hash
        if not transfer.pin_generated or not verify_pin(transfer.pin_generated, request.pin):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid PIN"
            )

        # Reset failed attempts after successful verification
        reset_pin_attempts(transfer_id)

        # Mark verified
        transfer.receiver_phone_verified = request.phone_verified
        transfer.agent_verified = True

        # Auto-transition if both verified
        if transfer.receiver_phone_verified and transfer.agent_verified:
            transfer.state = TransferState.RECEIVER_VERIFIED

        db.commit()

        logger.info(f"Transfer verified: {transfer.reference}")

        return AgentVerifyResponse(
            verified=True,
            instruction="Proceed with cash payout to receiver",
            message=f"Ready to pay {transfer.receiver_name} {transfer.amount_zar} ZAR"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Verification failed"
        )


@router.post("/transfers/{transfer_id}/confirm-payout", response_model=AgentConfirmPayoutResponse)
async def confirm_payout(
    transfer_id: str,
    request: AgentConfirmPayoutRequest,
    db: Session = Depends(get_db),
    current_agent: dict = Depends(get_current_agent),
):
    """
    Confirm cash payout executed

    Agent confirmation that cash has been paid to receiver.
    Triggers invoice settlement.
    """
    try:
        agent_id = uuid.UUID(current_agent["agent_id"])
        xfer_id = uuid.UUID(transfer_id)
        transfer_svc = get_transfer_service(db)

        transfer = db.query(Transfer).filter(
            Transfer.id == xfer_id,
            Transfer.agent_id == agent_id,
        ).first()

        if not transfer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transfer not found"
            )

        if transfer.state != TransferState.RECEIVER_VERIFIED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Transfer in state {transfer.state}, cannot confirm payout"
            )

        # Execute payout (settle invoice)
        transfer = await transfer_svc.execute_payout(xfer_id)

        # Update agent balance
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        agent.cash_balance_zar -= transfer.amount_zar  # Deduct payout
        db.commit()

        logger.info(f"Payout confirmed: {transfer.reference}")

        return AgentConfirmPayoutResponse(
            status="payout_confirmed",
            message=f"Payout of {transfer.amount_zar} ZAR confirmed",
            settlement_pending=True,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Payout confirmation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to confirm payout"
        )


# ===== SETTLEMENTS =====

@router.get("/settlements", response_model=List[SettlementResponse])
async def get_settlements(
    db: Session = Depends(get_db),
    current_agent: dict = Depends(get_current_agent),
):
    """
    Get settlement history - weekly payouts

    Returns:
        List of settlements for agent
    """
    try:
        agent_id = uuid.UUID(current_agent["agent_id"])

        settlements = db.query(Settlement).filter(
            Settlement.agent_id == agent_id
        ).order_by(Settlement.period_start.desc()).all()

        # Use live rate for all sats→ZAR conversions in this response
        rate_svc = get_rate_service(db)
        live_rate = await rate_svc.get_zar_per_btc()

        results = []
        for s in settlements:
            sats_zar = Decimal(s.commission_sats_earned) / Decimal("100000000") * live_rate

            results.append(SettlementResponse(
                settlement_id=str(s.id),
                period_start=s.period_start,
                period_end=s.period_end,
                amount_zar=s.amount_zar_owed,
                amount_sats=s.commission_sats_earned,
                status=s.status.value,
                due_date=s.period_end,  # Settlement due on Sunday
            ))

        return results

    except Exception as e:
        logger.error(f"Settlement fetch failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get settlements"
        )


@router.post("/settlements/{settlement_id}/confirm", response_model=SettlementConfirmResponse)
async def confirm_settlement(
    settlement_id: str,
    request: SettlementConfirmRequest,
    db: Session = Depends(get_db),
    current_agent: dict = Depends(get_current_agent),
):
    """
    Confirm settlement payment received

    Agent confirms they received ZAR payment from platform.
    """
    try:
        agent_id = uuid.UUID(current_agent["agent_id"])
        settle_id = uuid.UUID(settlement_id)

        settlement = db.query(Settlement).filter(
            Settlement.id == settle_id,
            Settlement.agent_id == agent_id,
        ).first()

        if not settlement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Settlement not found"
            )

        # Mark confirmed
        settlement.status = "CONFIRMED"
        settlement.payment_method = request.payment_method
        settlement.payment_reference = request.reference_number
        db.commit()

        logger.info(f"Settlement confirmed: {settlement_id}")

        return SettlementConfirmResponse(
            confirmed=True,
            settlement_id=str(settlement.id),
            next_payment_due=None,  # TODO: Calculate next settlement date
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Settlement confirmation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to confirm settlement"
        )
