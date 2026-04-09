"""
Shared pytest fixtures for SatsRemit test suite.

Uses an in-memory SQLite database so tests run without a real PostgreSQL
instance.  SQLite doesn't support all PostgreSQL-specific column types
(e.g. UUID, DECIMAL), so we override them to be compatible.
"""

import os
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

# ---------------------------------------------------------------------------
# Ensure env vars required by Settings are present before importing app code
# ---------------------------------------------------------------------------
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("LND_REST_URL", "https://localhost:8080")
os.environ.setdefault("LND_MACAROON_PATH", "/tmp/admin.macaroon")
os.environ.setdefault("LND_CERT_PATH", "/tmp/tls.cert")
os.environ.setdefault("WHATSAPP_BUSINESS_ACCOUNT_ID", "test-account")
os.environ.setdefault("WHATSAPP_BUSINESS_PHONE_NUMBER_ID", "test-phone-id")
os.environ.setdefault("WHATSAPP_BUSINESS_ACCESS_TOKEN", "test-token")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-at-least-32-chars-long!")
os.environ.setdefault("WEBHOOK_SECRET", "test-webhook-secret")

from src.models.models import Base, Agent, AgentStatus, Transfer, TransferState


# ---------------------------------------------------------------------------
# SQLite-compatible engine (SQLAlchemy 2.x, sync)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def engine():
    """Create a shared in-memory SQLite engine for the test session."""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        echo=False,
    )
    # UUID stored as string in SQLite
    @event.listens_for(eng, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine) -> Generator[Session, None, None]:
    """Provide a transactional DB session that rolls back after each test."""
    connection = engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = SessionLocal()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def make_agent(db: Session, **kwargs) -> Agent:
    """Create and persist a minimal Agent record."""
    from src.core.security import hash_password

    defaults = dict(
        id=uuid.uuid4(),
        phone="+27821234567",
        name="Test Agent",
        password_hash=hash_password("TestPassword123!"),
        location_code="ZWE_HRR",
        location_name="Harare",
        cash_balance_zar=Decimal("1000.00"),
        commission_balance_sats=0,
        status=AgentStatus.ACTIVE,
        is_admin=False,
        must_change_password=False,
        total_transfers=0,
    )
    defaults.update(kwargs)
    agent = Agent(**defaults)
    db.add(agent)
    db.commit()
    return agent


def make_transfer(db: Session, agent: Agent, **kwargs) -> Transfer:
    """Create and persist a minimal Transfer record."""
    defaults = dict(
        id=uuid.uuid4(),
        reference="250101120000abcd1234",
        sender_phone="+27831234567",
        receiver_phone="+263771234567",
        receiver_name="Jane Doe",
        receiver_location="ZWE_HRR",
        amount_zar=Decimal("200.00"),
        amount_sats=5000,
        rate_zar_per_btc=Decimal("1200000.00"),
        agent_id=agent.id,
        state=TransferState.INITIATED,
        receiver_phone_verified=False,
        agent_verified=False,
    )
    defaults.update(kwargs)
    transfer = Transfer(**defaults)
    db.add(transfer)
    db.commit()
    return transfer


@pytest.fixture
def agent(db: Session) -> Agent:
    return make_agent(db)


@pytest.fixture
def transfer(db: Session, agent: Agent) -> Transfer:
    return make_transfer(db, agent)


# ---------------------------------------------------------------------------
# Mock LND service
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_lnd():
    """Return a MagicMock that satisfies the LNDService interface."""
    lnd = MagicMock()
    lnd.create_hold_invoice = AsyncMock(return_value={
        "payment_hash": "a" * 64,
        "payment_request": "lnbc1test",
        "add_index": "1",
    })
    lnd.check_invoice_paid = AsyncMock(return_value=False)
    lnd.settle_invoice = AsyncMock(return_value={})
    lnd.get_invoice = AsyncMock(return_value={"state": "OPEN", "settled": False})
    return lnd
