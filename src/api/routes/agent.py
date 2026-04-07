"""
Agent API routes (authenticated)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import logging

from src.db.database import get_db
from src.models.schemas import (
    AgentLoginRequest,
    AgentLoginResponse,
    AgentBalanceResponse,
    AgentVerifyRequest,
    AgentVerifyResponse,
    AgentTransferResponse,
    ConfirmPayoutRequest,
    ConfirmPayoutResponse,
    AgentSettlementsResponse,
    SettlementConfirmRequest,
    SettlementConfirmResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agent", tags=["agent"])


# ========== AUTHENTICATION ==========

@router.post("/auth/login", response_model=AgentLoginResponse)
async def agent_login(
    request: AgentLoginRequest,
    db: Session = Depends(get_db),
):
    """
    Agent login (phone + password)
    
    Returns JWT token for subsequent authenticated requests
    """
    # TODO: Implement agent authentication
    raise HTTPException(status_code=501, detail="Not implemented")


# ========== ACCOUNT ==========

@router.get("/balance", response_model=AgentBalanceResponse)
async def get_agent_balance(
    db: Session = Depends(get_db),
    # token: str = Depends(get_agent_token),
):
    """
    Get agent's current balance
    
    - Cash balance (ZAR)
    - Commission balance (sats)
    - Pending transfers
    """
    # TODO: Implement balance retrieval
    raise HTTPException(status_code=501, detail="Not implemented")


# ========== TRANSFERS ==========

@router.get("/transfers", response_model=List[AgentTransferResponse])
async def get_pending_transfers(
    db: Session = Depends(get_db),
    # token: str = Depends(get_agent_token),
):
    """
    Get list of pending transfers for verification
    
    Returns transfers in PAYMENT_LOCKED state
    """
    # TODO: Implement pending transfers listing
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/transfers/{transfer_id}/verify", response_model=AgentVerifyResponse)
async def verify_transfer(
    transfer_id: str,
    request: AgentVerifyRequest,
    db: Session = Depends(get_db),
    # token: str = Depends(get_agent_token),
):
    """
    Verify receiver (PIN + phone dual verification)
    
    - Validates PIN
    - Confirms phone number
    - Transitions transfer to RECEIVER_VERIFIED
    """
    # TODO: Implement transfer verification
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/transfers/{transfer_id}/confirm-payout", response_model=ConfirmPayoutResponse)
async def confirm_payout(
    transfer_id: str,
    request: ConfirmPayoutRequest,
    db: Session = Depends(get_db),
    # token: str = Depends(get_agent_token),
):
    """
    Agent confirms that cash has been paid to receiver
    
    - Marks transfer as PAYOUT_EXECUTED
    - Triggers async settlement logic
    """
    # TODO: Implement payout confirmation
    raise HTTPException(status_code=501, detail="Not implemented")


# ========== SETTLEMENTS ==========

@router.get("/settlements", response_model=List[AgentSettlementsResponse])
async def get_settlements(
    db: Session = Depends(get_db),
    # token: str = Depends(get_agent_token),
):
    """
    Get list of weekly settlements
    """
    # TODO: Implement settlements listing
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/settlement/{settlement_id}/confirm", response_model=SettlementConfirmResponse)
async def confirm_settlement(
    settlement_id: str,
    request: SettlementConfirmRequest,
    db: Session = Depends(get_db),
    # token: str = Depends(get_agent_token),
):
    """
    Agent confirms settlement payment (ZAR transferred to platform)
    
    - Validates payment details
    - Marks settlement CONFIRMED
    - Prepares for account reconciliation
    """
    # TODO: Implement settlement confirmation
    raise HTTPException(status_code=501, detail="Not implemented")
