"""
FastAPI dependency injection utilities
"""

from typing import AsyncGenerator
from sqlalchemy.orm import Session
import logging

from src.db.database import get_db as _get_db
from src.services import (
    LNDService,
    TransferService,
    RateService,
    NotificationService,
)

logger = logging.getLogger(__name__)


# Re-export get_db from database module
def get_db():
    """
    Database session dependency

    Usage:
        @app.get("/items")
        async def get_items(db: Session = Depends(get_db)):
            ...
    """
    return _get_db()


def get_lnd_service() -> LNDService:
    """
    LND Service dependency

    Usage:
        @app.get("/wallet/balance")
        async def get_balance(lnd: LNDService = Depends(get_lnd_service)):
            ...
    """
    return LNDService()


def get_transfer_service(db: Session) -> TransferService:
    """
    Transfer Service dependency

    Usage:
        @app.post("/transfers")
        async def create_transfer(
            db: Session = Depends(get_db),
            transfer_svc: TransferService = Depends(get_transfer_service),
        ):
            ...
    """
    return TransferService(db)


def get_rate_service(db: Session) -> RateService:
    """
    Rate Service dependency

    Usage:
        @app.get("/rates")
        async def get_rate(
            db: Session = Depends(get_db),
            rate_svc: RateService = Depends(get_rate_service),
        ):
            ...
    """
    return RateService(db)


def get_notification_service() -> NotificationService:
    """
    Notification Service dependency

    Usage:
        @app.post("/notify")
        async def notify(notify_svc: NotificationService = Depends(get_notification_service)):
            ...
    """
    return NotificationService()
