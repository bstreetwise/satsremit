"""
Pydantic schemas for API request/response validation
"""
from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from enum import Enum


# ========== ENUMS ==========

class TransferStateSchema(str, Enum):
    INITIATED = "INITIATED"
    INVOICE_GENERATED = "INVOICE_GENERATED"
    PAYMENT_LOCKED = "PAYMENT_LOCKED"
    RECEIVER_VERIFIED = "RECEIVER_VERIFIED"
    PAYOUT_EXECUTED = "PAYOUT_EXECUTED"
    SETTLED = "SETTLED"
    FINAL = "FINAL"
    REFUNDED = "REFUNDED"


class AgentStatusSchema(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"


class SettlementStatusSchema(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"


# ========== TRANSFER SCHEMAS ==========

class CreateTransferRequest(BaseModel):
    """Request to create a new transfer"""
    sender_phone: str = Field(..., min_length=10, max_length=20, description="Sender phone")
    receiver_phone: str = Field(..., min_length=10, max_length=20, description="Receiver phone")
    receiver_name: str = Field(..., min_length=2, max_length=100, description="Receiver name")
    amount_zar: Decimal = Field(..., gt=0, description="Amount in ZAR")
    location_code: str = Field(..., min_length=2, max_length=10, description="Agent location code")
    receiver_location: Optional[str] = Field(None, description="Receiver city/area")
    
    @validator("amount_zar")
    def validate_amount(cls, v):
        if v < 100 or v > 500:
            raise ValueError("Amount must be between 100-500 ZAR")
        return v


class TransferResponse(BaseModel):
    """Transfer response with invoice details"""
    transfer_id: str
    reference: str
    state: TransferStateSchema
    sender_phone: str
    receiver_phone: str
    receiver_name: str
    amount_zar: Decimal
    amount_sats: int
    rate_zar_per_btc: Decimal
    invoice_hash: Optional[str] = None
    payment_request: Optional[str] = None  # LND bech32 invoice
    invoice_expiry_at: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class TransferStatusResponse(BaseModel):
    """Transfer status for tracking"""
    transfer_id: str
    reference: str
    state: TransferStateSchema
    receiver_name: str
    amount_zar: Decimal
    receiver_received: bool = False
    created_at: datetime
    updated_at: datetime


class TransferListResponse(BaseModel):
    """Paginated transfer list"""
    items: List[TransferResponse]
    total: int
    page: int
    page_size: int
    has_next: bool


# ========== AGENT SCHEMAS ==========

class AgentLoginRequest(BaseModel):
    """Agent login credentials"""
    phone: str = Field(..., min_length=10, max_length=20)
    password: str = Field(..., min_length=8)


class AgentLoginResponse(BaseModel):
    """Agent login response with token"""
    access_token: str
    token_type: str = "bearer"
    agent_id: str
    agent_name: str
    expires_in: int  # seconds


class AgentBalanceResponse(BaseModel):
    """Agent current balance"""
    agent_id: str
    agent_name: str
    cash_balance_zar: Decimal
    commission_balance_sats: int
    pending_payouts: int
    next_settlement_date: datetime
    status: AgentStatusSchema


class AgentVerifyRequest(BaseModel):
    """Agent verification request"""
    pin: str = Field(..., min_length=4, max_length=4)
    phone_number_verified: str = Field(..., description="Receiver phone for verification")


class AgentVerifyResponse(BaseModel):
    """Agent verification response"""
    verified: bool
    transfer_id: str
    reference: str
    receiver_name: str
    amount_zar: Decimal
    instruction: str


class AgentTransferResponse(BaseModel):
    """Transfer pending agent payout"""
    transfer_id: str
    reference: str
    receiver_name: str
    receiver_phone: str
    amount_zar: Decimal
    receiver_location: Optional[str]
    sender_phone: str
    notification_sent_at: datetime


class ConfirmPayoutRequest(BaseModel):
    """Agent confirmation of payout"""
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ConfirmPayoutResponse(BaseModel):
    """Payout confirmation response"""
    status: str = "confirmed"
    settlement_pending: bool
    next_step: str


class AgentSettlementsResponse(BaseModel):
    """List of agent settlements"""
    settlement_id: str
    period_start: datetime
    period_end: datetime
    amount_zar_owed: Decimal
    amount_zar_paid: Decimal
    commission_sats_earned: int
    status: SettlementStatusSchema
    due_date: datetime


class SettlementConfirmRequest(BaseModel):
    """Confirm settlement payment"""
    payment_method: str = Field(..., description="bank_transfer, mobile_money, etc.")
    reference_number: str = Field(..., description="Bank/Mobile reference")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SettlementConfirmResponse(BaseModel):
    """Settlement confirmation"""
    confirmed: bool
    settlement_id: str
    next_payment_due: datetime


# ========== ADMIN SCHEMAS ==========

class CreateAgentRequest(BaseModel):
    """Admin: Create new agent"""
    phone: str = Field(..., min_length=10, max_length=20)
    name: str = Field(..., min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    password: str = Field(..., min_length=12)
    location_code: str = Field(..., min_length=2, max_length=10)
    location_name: str = Field(..., min_length=2, max_length=100)
    initial_cash_zar: Decimal = Field(default=0, ge=0)


class AgentBalanceCheckResponse(BaseModel):
    """Admin: Agent financial status"""
    agent_id: str
    agent_name: str
    phone: str
    location_code: str
    cash_owed_zar: Decimal
    sats_earned: int
    settlements_pending: int
    status: AgentStatusSchema
    last_settlement: Optional[datetime]


class CashAdvanceRequest(BaseModel):
    """Admin: Record cash advance for correction/setup"""
    zar_amount: Decimal = Field(..., gt=0)
    note: str = Field(..., min_length=5, max_length=500)
    reason: str = Field(default="manual_adjustment")


class VolumemeticsResponse(BaseModel):
    """Platform volume metrics"""
    daily_volume_zar: Decimal
    daily_transfer_count: int
    weekly_volume_zar: Decimal
    monthly_volume_zar: Decimal
    fee_collected_sats: int
    active_agents: int
    timestamp: datetime


# ========== WEBHOOK SCHEMAS ==========

class LNDInvoiceSettledWebhook(BaseModel):
    """LND webhook for settled invoices"""
    invoice_hash: str
    state: str  # "SETTLED", "EXPIRED", etc.
    settled_at: datetime
    amount_milli_satoshis: int
    preimage: Optional[str] = None


# ========== HEALTH CHECK ==========

class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str
    bitcoind_synced: bool
    lnd_active: bool
    db_connected: bool
    redis_connected: bool
    timestamp: datetime


# ========== LOCATION SCHEMAS ==========

class AgentLocationResponse(BaseModel):
    """Available agent location"""
    location_code: str
    location_name: str
    agent_name: str
    agent_phone: str
    status: AgentStatusSchema
    available: bool


# ========== ERROR RESPONSE ==========

class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str
    detail: str
    code: str
    timestamp: datetime
