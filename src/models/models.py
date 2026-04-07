"""
SQLAlchemy ORM Models for SatsRemit
"""
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Enum, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID, DECIMAL
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import uuid
import enum

Base = declarative_base()


class TransferState(str, enum.Enum):
    """Transfer state machine states"""
    INITIATED = "INITIATED"
    INVOICE_GENERATED = "INVOICE_GENERATED"
    PAYMENT_LOCKED = "PAYMENT_LOCKED"
    RECEIVER_VERIFIED = "RECEIVER_VERIFIED"
    PAYOUT_EXECUTED = "PAYOUT_EXECUTED"
    SETTLED = "SETTLED"
    FINAL = "FINAL"
    REFUNDED = "REFUNDED"


class AgentStatus(str, enum.Enum):
    """Agent status"""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"


class SettlementStatus(str, enum.Enum):
    """Settlement status"""
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"


class Transfer(Base):
    """Main transfer record"""
    __tablename__ = "transfers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reference = Column(String(20), unique=True, nullable=False, index=True)
    
    # Participants
    sender_phone = Column(String(20), nullable=False, index=True)
    receiver_phone = Column(String(20), nullable=False, index=True)
    receiver_name = Column(String(100), nullable=False)
    receiver_location = Column(String(50), nullable=True)
    
    # Agent
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False, index=True)
    agent = relationship("Agent", back_populates="transfers")
    
    # Amounts
    amount_zar = Column(DECIMAL(15, 2), nullable=False)
    amount_sats = Column(Integer, nullable=False)  # in satoshis
    rate_zar_per_btc = Column(DECIMAL(15, 2), nullable=False)  # rate at time of transfer
    
    # LND Invoice
    invoice_hash = Column(String(66), unique=True, nullable=True, index=True)
    payment_request = Column(String(2048), nullable=True)  # LND bech32 invoice
    invoice_expiry_at = Column(DateTime, nullable=True)
    
    # State Machine
    state = Column(Enum(TransferState), default=TransferState.INITIATED, nullable=False, index=True)
    
    # Verification
    receiver_phone_verified = Column(Boolean, default=False)
    agent_verified = Column(Boolean, default=False)
    verified_at = Column(DateTime, nullable=True)
    
    # Payout
    payout_at = Column(DateTime, nullable=True)
    
    # Settlement
    settled_at = Column(DateTime, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Additional
    pin_generated = Column(String(4), nullable=True)  # Store hashed PIN
    notes = Column(String(500), nullable=True)


class Agent(Base):
    """Agent record (cash payout operators)"""
    __tablename__ = "agents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(120), unique=True, nullable=True)
    
    # Security
    password_hash = Column(String(255), nullable=False)
    
    # Location
    location_code = Column(String(10), nullable=False)  # e.g., "ZWE_HRR"
    location_name = Column(String(100), nullable=False)
    
    # Financial
    cash_balance_zar = Column(DECIMAL(15, 2), default=0, nullable=False)
    commission_balance_sats = Column(Integer, default=0, nullable=False)  # in satoshis
    
    # Status
    status = Column(Enum(AgentStatus), default=AgentStatus.ACTIVE, nullable=False)
    rating = Column(Float, nullable=True)  # avg rating out of 5
    total_transfers = Column(Integer, default=0, nullable=False)
    
    # Relationships
    transfers = relationship("Transfer", back_populates="agent")
    settlements = relationship("Settlement", back_populates="agent")
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)


class Settlement(Base):
    """Weekly settlement record"""
    __tablename__ = "settlements"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False, index=True)
    agent = relationship("Agent", back_populates="settlements")
    
    # Period
    period_start = Column(DateTime, nullable=False)  # Monday
    period_end = Column(DateTime, nullable=False)    # Sunday
    
    # Financial
    amount_zar_owed = Column(DECIMAL(15, 2), nullable=False)  # Total cash agent paid out
    amount_zar_paid = Column(DECIMAL(15, 2), default=0, nullable=False)  # Actual payment
    commission_sats_earned = Column(Integer, default=0, nullable=False)  # in satoshis
    
    # Settlement Details
    payment_method = Column(String(50), nullable=True)  # bank_transfer, mobile_money, etc.
    payment_reference = Column(String(100), nullable=True)  # Bank ref, transaction ID, etc.
    status = Column(Enum(SettlementStatus), default=SettlementStatus.PENDING)
    
    # Timestamps
    confirmed_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class InvoiceHold(Base):
    """Hold invoice secrets management"""
    __tablename__ = "invoice_holds"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_hash = Column(String(66), unique=True, nullable=False, index=True)
    transfer_id = Column(UUID(as_uuid=True), ForeignKey("transfers.id"), nullable=False, unique=True)
    
    # Preimage (ENCRYPTED in database)
    preimage = Column(String(128), nullable=False)  # Encrypted preimage
    
    # Expiry
    expires_at = Column(DateTime, nullable=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class TransferHistory(Base):
    """Audit trail for transfers (immutable log)"""
    __tablename__ = "transfer_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transfer_id = Column(UUID(as_uuid=True), ForeignKey("transfers.id"), nullable=False, index=True)
    
    # State change
    old_state = Column(Enum(TransferState), nullable=True)
    new_state = Column(Enum(TransferState), nullable=False)
    reason = Column(String(500), nullable=True)
    
    # Actor
    actor_type = Column(String(20), nullable=False)  # "system", "sender", "agent", "admin"
    actor_id = Column(String(50), nullable=True)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class RateCache(Base):
    """Exchange rate cache to avoid excessive API calls"""
    __tablename__ = "rate_cache"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pair = Column(String(10), unique=True, nullable=False, index=True)  # e.g., "ZAR_BTC"
    rate = Column(DECIMAL(20, 8), nullable=False)
    source = Column(String(50), nullable=False)  # "coingecko", "kraken", etc.
    
    cached_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Webhook(Base):
    """Webhook delivery log (for LND callbacks, etc.)"""
    __tablename__ = "webhooks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(50), nullable=False, index=True)  # "lnd.invoice.settled"
    payload = Column(JSON, nullable=False)
    
    status = Column(String(20), nullable=False)  # "pending", "delivered", "failed"
    retry_count = Column(Integer, default=0)
    error_message = Column(String(500), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    processed_at = Column(DateTime, nullable=True)
