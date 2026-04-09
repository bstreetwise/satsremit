"""
Admin API Routes - Admin-only operations
"""

import logging
import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List

from src.api.schemas import (
    AdminAgentCreateRequest,
    AdminAgentCreateResponse,
    AdminAgentBalanceResponse,
    AdminAgentAdvanceRequest,
    AdminAgentAdvanceResponse,
    AdminTransferListResponse,
    AdminVolumeResponse,
)
from src.core.dependencies import get_db
from src.core.security import hash_password, get_current_agent
from src.models.models import (
    Agent,
    AgentStatus,
    Transfer,
    Settlement,
    TransferState,
)
from decimal import Decimal

logger = logging.getLogger(__name__)

router = APIRouter()


# ===== AGENTS =====

@router.post("/agents", response_model=AdminAgentCreateResponse)
async def create_agent(
    request: AdminAgentCreateRequest,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_agent),  # TODO: Implement admin check
):
    """
    Create new agent

    Admin creates new agent with initial cash balance.
    """
    try:
        # Check phone not already registered
        existing = db.query(Agent).filter(Agent.phone == request.phone).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agent phone already registered"
            )

        # Create agent
        agent = Agent(
            id=uuid.uuid4(),
            phone=request.phone,
            name=request.name,
            email=None,
            password_hash=hash_password("TempPassword123!"),  # Temp, agent should change
            location_code=request.location_code,
            location_name=request.location_code,  # TODO: Map to name
            cash_balance_zar=request.initial_cash_zar or Decimal("0.00"),
            commission_balance_sats=0,
            status=AgentStatus.ACTIVE,
            rating=None,
            total_transfers=0,
        )

        db.add(agent)
        db.commit()

        logger.info(f"Agent created: {agent.phone}")

        return AdminAgentCreateResponse(
            agent_id=str(agent.id),
            phone=agent.phone,
            name=agent.name,
            status=agent.status.value,
            cash_balance_zar=agent.cash_balance_zar,
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Agent creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create agent"
        )


@router.get("/agents/{agent_id}/balance", response_model=AdminAgentBalanceResponse)
async def get_agent_balance_admin(
    agent_id: str,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_agent),  # TODO: Implement admin check
):
    """
    Get agent financial status - admin view

    Real-time balance including pending settlements.
    """
    try:
        agent = db.query(Agent).filter(Agent.id == uuid.UUID(agent_id)).first()

        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )

        # Calculate pending
        pending = db.query(Settlement).filter(
            Settlement.agent_id == agent.id,
            Settlement.status == "PENDING"
        ).first()

        pending_zar = pending.amount_zar_owed if pending else Decimal("0.00")

        # Commission in ZAR (approx)
        # TODO: Get actual historical rate
        commission_zar = Decimal(agent.commission_balance_sats) / Decimal("100000000") * Decimal("120000")

        return AdminAgentBalanceResponse(
            agent_id=str(agent.id),
            agent_name=agent.name,
            cash_owed_zar=pending_zar,
            sats_earned=agent.commission_balance_sats,
            commission_zar=commission_zar,
            settlements_pending=1 if pending else 0,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Balance check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get balance"
        )


@router.post("/agents/{agent_id}/advance", response_model=AdminAgentAdvanceResponse)
async def record_agent_advance(
    agent_id: str,
    request: AdminAgentAdvanceRequest,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_agent),  # TODO: Implement admin check
):
    """
    Record cash advance or corrective entry

    Admin records manual balance adjustment (e.g., cash advance, correction).
    """
    try:
        agent = db.query(Agent).filter(Agent.id == uuid.UUID(agent_id)).first()

        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )

        # Update balance
        agent.cash_balance_zar += request.zar_amount
        db.commit()

        logger.info(f"Agent advance recorded: {agent.phone} {request.zar_amount} ZAR - {request.note}")

        return AdminAgentAdvanceResponse(
            agent_id=str(agent.id),
            new_balance_zar=agent.cash_balance_zar,
            transaction_id=f"ADV-{uuid.uuid4().hex[:8].upper()}",
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Advance recording failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record advance"
        )


# ===== TRANSFERS =====

@router.get("/transfers", response_model=List[AdminTransferListResponse])
async def list_transfers_admin(
    state: str = Query(None, description="Filter by state"),
    agent_id: str = Query(None, description="Filter by agent"),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_agent),  # TODO: Implement admin check
):
    """
    List all transfers - admin full audit view

    Supports filtering by state, agent, date range.
    """
    try:
        query = db.query(Transfer)

        # Filters
        if state:
            query = query.filter(Transfer.state == TransferState[state.upper()])

        if agent_id:
            query = query.filter(Transfer.agent_id == uuid.UUID(agent_id))

        # Pagination
        transfers = query.order_by(Transfer.created_at.desc()).offset(offset).limit(limit).all()

        results = []
        for t in transfers:
            agent = db.query(Agent).filter(Agent.id == t.agent_id).first()
            results.append(AdminTransferListResponse(
                transfer_id=str(t.id),
                reference=t.reference,
                amount_zar=t.amount_zar,
                amount_sats=t.amount_sats,
                state=t.state,
                agent_name=agent.name if agent else "Unknown",
                created_at=t.created_at,
                settled_at=t.settled_at,
            ))

        return results

    except Exception as e:
        logger.error(f"Transfer listing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list transfers"
        )


# ===== ANALYTICS =====

@router.get("/volume", response_model=AdminVolumeResponse)
async def get_volume_analytics(
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_agent),  # TODO: Implement admin check
):
    """
    Get platform volume analytics

    Daily, weekly, monthly volumes and fees collected.
    """
    try:
        # Calculate time ranges
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())
        month_start = today_start.replace(day=1)

        # Daily volume
        daily = db.query(
            func.sum(Transfer.amount_zar).label('volume'),
            func.count(Transfer.id).label('count')
        ).filter(
            Transfer.created_at >= today_start,
            Transfer.state == TransferState.SETTLED,
        ).first()

        daily_volume = Decimal(daily.volume) if daily.volume else Decimal("0.00")
        daily_count = daily.count or 0

        # Weekly volume
        weekly = db.query(
            func.sum(Transfer.amount_zar).label('volume'),
            func.count(Transfer.id).label('count')
        ).filter(
            Transfer.created_at >= week_start,
            Transfer.state == TransferState.SETTLED,
        ).first()

        weekly_volume = Decimal(weekly.volume) if weekly.volume else Decimal("0.00")
        weekly_count = weekly.count or 0

        # Monthly volume
        monthly = db.query(
            func.sum(Transfer.amount_zar).label('volume'),
            func.count(Transfer.id).label('count')
        ).filter(
            Transfer.created_at >= month_start,
            Transfer.state == TransferState.SETTLED,
        ).first()

        monthly_volume = Decimal(monthly.volume) if monthly.volume else Decimal("0.00")
        monthly_count = monthly.count or 0

        # Calculate fees
        daily_fees_sats = int((daily_volume / Decimal("120000")) * Decimal("100000000") * Decimal("0.01"))
        weekly_fees_sats = int((weekly_volume / Decimal("120000")) * Decimal("100000000") * Decimal("0.01"))
        monthly_fees_sats = int((monthly_volume / Decimal("120000")) * Decimal("100000000") * Decimal("0.01"))

        return AdminVolumeResponse(
            daily_volume_zar=daily_volume,
            daily_transfers=daily_count,
            weekly_volume_zar=weekly_volume,
            weekly_transfers=weekly_count,
            monthly_volume_zar=monthly_volume,
            monthly_transfers=monthly_count,
            total_fees_collected_sats=monthly_fees_sats,
            platform_earn_sats=int(monthly_fees_sats * 0.5),  # Platform gets 50%
            agent_earn_sats=int(monthly_fees_sats * 0.5),     # Agents get 50%
        )

    except Exception as e:
        logger.error(f"Analytics failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get analytics"
        )


@router.get("/health")
async def admin_health(
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_agent),  # TODO: Implement admin check
):
    """
    Admin health check - system status

    Returns status of all critical systems.
    """
    try:
        # Count active agents
        active_agents = db.query(func.count(Agent.id)).filter(
            Agent.status == AgentStatus.ACTIVE
        ).scalar()

        # Count pending transfers
        pending_transfers = db.query(func.count(Transfer.id)).filter(
            Transfer.state == TransferState.PAYMENT_LOCKED
        ).scalar()

        # Total cash in system
        total_cash = db.query(func.sum(Agent.cash_balance_zar)).scalar()

        return {
            "status": "healthy",
            "active_agents": active_agents,
            "pending_transfers": pending_transfers,
            "total_cash_in_system": float(total_cash) if total_cash else 0.0,
            "timestamp": datetime.utcnow(),
        }

    except Exception as e:
        logger.error(f"Admin health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get status"
        )
