"""
API Response Schemas - Request/Response validation

Enums and the HealthCheckResponse/ErrorResponse types are imported from
``src.models.schemas`` (the canonical schema module) to avoid duplication.
"""

from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, List
from decimal import Decimal

# Import canonical enums and shared response types from the models schema module
from src.models.schemas import (
    TransferStateSchema as TransferStateEnum,
    AgentStatusSchema as AgentStatusEnum,
    HealthCheckResponse,
    ErrorResponse,
)


# ===== TRANSFER SCHEMAS =====

class TransferCreateRequest(BaseModel):
    sender_phone: str = Field(..., min_length=10, max_length=20, description="Sender phone (E.164 format)")
    receiver_phone: str = Field(..., min_length=10, max_length=20)
    receiver_name: str = Field(..., min_length=2, max_length=100)
    receiver_location: str = Field(..., description="Location code (e.g., ZWE_HRR)")
    amount_zar: Decimal = Field(..., gt=0, decimal_places=2)

    @field_validator('sender_phone', 'receiver_phone')
    def validate_phone(cls, v):
        if not v.replace('+', '').replace('-', '').replace(' ', '').isdigit():
            raise ValueError('Invalid phone format')
        return v


class TransferQuoteResponse(BaseModel):
    amount_zar: Decimal
    amount_sats: int
    platform_fee_zar: Decimal
    agent_commission_zar: Decimal
    total_fees_zar: Decimal
    receiver_gets_zar: Decimal
    rate_zar_per_btc: Decimal


class TransferInitiateResponse(BaseModel):
    transfer_id: str
    reference: str
    invoice_hash: str
    invoice_request: str
    amount_sats: int
    amount_zar: Decimal
    expires_at: datetime
    agent_name: str
    agent_location: str
    status_url: str


class TransferDetailResponse(BaseModel):
    transfer_id: str
    reference: str
    state: TransferStateEnum
    sender_phone: str
    receiver_phone: str
    receiver_name: str
    amount_zar: Decimal
    amount_sats: int
    rate_zar_per_btc: Decimal
    created_at: datetime
    invoice_expiry_at: Optional[datetime]
    payout_at: Optional[datetime]
    settled_at: Optional[datetime]


class TransferStatusResponse(BaseModel):
    reference: str
    state: TransferStateEnum
    receiver_phone_verified: bool
    agent_verified: bool
    receiver_received: bool
    settlement_date: Optional[datetime]


# ===== AGENT SCHEMAS =====

class AgentLoginRequest(BaseModel):
    phone: str = Field(..., min_length=10, max_length=20)
    password: str = Field(..., min_length=8)


class AgentLoginResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    expires_in: int
    agent_id: str
    agent_name: str
    agent_phone: str


class AgentBalanceResponse(BaseModel):
    cash_balance_zar: Decimal
    commission_balance_sats: int
    total_commission_zar: Decimal
    pending_settlement_zar: Decimal
    payout_date: str


class AgentTransferResponse(BaseModel):
    transfer_id: str
    reference: str
    receiver_name: str
    receiver_phone: str
    receiver_location: str
    amount_zar: Decimal
    amount_sats: int
    created_at: datetime
    expires_at: datetime


class AgentVerifyRequest(BaseModel):
    pin: str = Field(..., min_length=4, max_length=4, description="4-digit PIN")
    phone_verified: bool = Field(default=True)


class AgentVerifyResponse(BaseModel):
    verified: bool
    instruction: str
    message: str


class AgentConfirmPayoutRequest(BaseModel):
    confirmation_note: Optional[str] = None


class AgentConfirmPayoutResponse(BaseModel):
    status: str
    message: str
    settlement_pending: bool


# ===== SETTLEMENT SCHEMAS =====

class SettlementResponse(BaseModel):
    settlement_id: str
    period_start: datetime
    period_end: datetime
    amount_zar: Decimal
    amount_sats: int
    status: str
    due_date: datetime


class SettlementConfirmRequest(BaseModel):
    payment_method: str = Field(..., description="bank_transfer, mobile_money, etc.")
    reference_number: str
    note: Optional[str] = None


class SettlementConfirmResponse(BaseModel):
    confirmed: bool
    settlement_id: str
    next_payment_due: Optional[datetime]


# ===== ADMIN SCHEMAS =====

class AdminAgentCreateRequest(BaseModel):
    phone: str = Field(..., min_length=10, max_length=20)
    name: str = Field(..., min_length=2, max_length=100)
    location_code: str
    initial_cash_zar: Decimal = Field(default=Decimal("0.00"))


class AdminAgentCreateResponse(BaseModel):
    agent_id: str
    phone: str
    name: str
    status: str
    cash_balance_zar: Decimal


class AdminAgentBalanceResponse(BaseModel):
    agent_id: str
    agent_name: str
    cash_owed_zar: Decimal
    sats_earned: int
    commission_zar: Decimal
    settlements_pending: int


class AdminAgentAdvanceRequest(BaseModel):
    zar_amount: Decimal
    note: str


class AdminAgentAdvanceResponse(BaseModel):
    agent_id: str
    new_balance_zar: Decimal
    transaction_id: str


class AdminTransferListResponse(BaseModel):
    transfer_id: str
    reference: str
    amount_zar: Decimal
    amount_sats: int
    state: TransferStateEnum
    agent_name: str
    created_at: datetime
    settled_at: Optional[datetime]


class AdminVolumeResponse(BaseModel):
    daily_volume_zar: Decimal
    daily_transfers: int
    weekly_volume_zar: Decimal
    weekly_transfers: int
    monthly_volume_zar: Decimal
    monthly_transfers: int
    total_fees_collected_sats: int
    platform_earn_sats: int
    agent_earn_sats: int


# ===== WEBHOOK SCHEMAS =====

class LNDInvoiceSettledWebhook(BaseModel):
    invoice_hash: str
    state: str
    settled_at: datetime
    amount_milli_satoshis: int


class LNDInvoiceSettledResponse(BaseModel):
    status: str
    transfer_id: Optional[str]
    message: str


# ErrorResponse is imported from src.models.schemas above
