"""
Public API routes (unauthenticated)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
import logging

from src.db.database import get_db
from src.models.schemas import (
    CreateTransferRequest,
    TransferResponse,
    TransferStatusResponse,
    AgentLocationResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["public"])


@router.post("/transfers", response_model=TransferResponse, status_code=201)
async def create_transfer(
    request: CreateTransferRequest,
    db: Session = Depends(get_db),
):
    """
    Create a new transfer (Lightning invoice generated)
    
    - Validates sender/receiver details
    - Checks agent liquidity
    - Generates hold invoice
    """
    # TODO: Implement transfer creation logic
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/transfers/{transfer_id}", response_model=TransferStatusResponse)
async def get_transfer_status(
    transfer_id: str,
    db: Session = Depends(get_db),
):
    """
    Get transfer status (public view)
    
    Returns non-sensitive fields only
    """
    # TODO: Implement status retrieval
    raise HTTPException(status_code=501, detail="Not implemented")


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
