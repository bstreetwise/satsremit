# Service Layer Quick Reference

## Common Usage Patterns

### 1. Create & Monitor a Transfer

```python
from src.services import TransferService, RateService, LNDService
from src.models.models import Transfer
from sqlalchemy.orm import Session
from decimal import Decimal
import uuid

async def handle_new_remittance(
    db: Session,
    sender_phone: str,
    receiver_phone: str,
    receiver_name: str,
    amount_zar: Decimal,
    agent_id: uuid.UUID,
):
    # Initialize services
    transfer_svc = TransferService(db)
    rate_svc = RateService(db)
    
    # Validate amount
    validation = await rate_svc.validate_transfer_amount(amount_zar)
    if not validation["valid"]:
        return {"error": validation["error"]}
    
    # Create transfer
    transfer = await transfer_svc.initiate_transfer(
        sender_phone=sender_phone,
        receiver_phone=receiver_phone,
        receiver_name=receiver_name,
        receiver_location="ZWE_HRR",  # TODO: from config
        amount_zar=amount_zar,
        amount_sats=validation["amount_sats"],
        rate_zar_per_btc=validation["rate_zar_per_btc"],
        agent_id=agent_id,
    )
    
    # Generate invoice
    invoice = await transfer_svc.generate_invoice(transfer.id)
    
    return {
        "transfer_id": str(transfer.id),
        "reference": transfer.reference,
        "amount_sats": transfer.amount_sats,
        "amount_zar": str(transfer.amount_zar),
        "payment_request": invoice["payment_request"],
        "expires_at": invoice["invoice_expiry_at"].isoformat(),
    }
```

### 2. Poll for Payment Reception

```python
async def check_and_process_payment(
    db: Session,
    transfer_id: uuid.UUID,
):
    transfer_svc = TransferService(db)
    
    # Check if payment received
    is_paid = await transfer_svc.check_payment_received(transfer_id)
    
    if is_paid:
        # Automatically transitions to PAYMENT_LOCKED
        transfer = await transfer_svc.get_transfer(transfer_id)
        
        # Notify sender
        from src.services import NotificationService
        notify = NotificationService()
        await notify.send_whatsapp(
            phone_number=transfer.sender_phone,
            message=f"Payment locked! Reference: {transfer.reference}"
        )
        
        return {"status": "payment_locked", "reference": transfer.reference}
    
    return {"status": "awaiting_payment"}
```

### 3. Verify Receiver & Execute Payout

```python
async def verify_and_payout(
    db: Session,
    transfer_id: uuid.UUID,
    receiver_pin_provided: str,
):
    transfer_svc = TransferService(db)
    
    # Get transfer
    transfer = await transfer_svc.get_transfer(transfer_id)
    if not transfer:
        raise Exception("Transfer not found")
    
    # Verify PIN (TODO: implement PIN logic)
    # if not verify_pin(transfer.pin_generated, receiver_pin_provided):
    #     raise Exception("Invalid PIN")
    
    # Mark receiver verified
    transfer = await transfer_svc.verify_receiver(transfer_id, verified=True)
    
    # Agent confirms receipt of verification
    transfer = await transfer_svc.verify_agent(transfer_id, verified=True)
    # ↓ This auto-transitions to RECEIVER_VERIFIED
    
    # Execute payout (agent pays cash to receiver)
    transfer = await transfer_svc.execute_payout(transfer_id)
    
    # At this point, invoice is settled and preimage stored
    return {
        "status": "payout_executed",
        "reference": transfer.reference,
        "state": transfer.state.value,
    }
```

### 4. Get Exchange Rate & Fee Breakdown

```python
from decimal import Decimal

async def get_quote(db: Session, amount_zar: Decimal):
    rate_svc = RateService(db)
    
    # Get current rate
    rate = await rate_svc.get_zar_per_btc()
    
    # Calculate fees
    fees = await rate_svc.get_fee_breakdown(amount_zar)
    
    return {
        "rate_zar_per_btc": str(rate),
        "sender_sends_zar": str(fees["amount_zar"]),
        "platform_fee_zar": str(fees["platform_fee_zar"]),
        "agent_commission_zar": str(fees["agent_commission_zar"]),
        "receiver_gets_zar": str(fees["receiver_gets_zar"]),
    }
```

### 5. Check Wallet Status

```python
async def check_wallet_health(db: Session):
    lnd = LNDService()
    
    # Get node info
    info = await lnd.get_node_info()
    
    # Get balance
    balance = await lnd.get_wallet_balance()
    
    # Get channels
    channels = await lnd.list_channels()
    
    return {
        "node_alias": info["alias"],
        "pubkey": info["identity_pubkey"],
        "peers": info["num_peers"],
        "active_channels": info["num_active_channels"],
        "wallet_balance_sats": balance["confirmed_balance"],
        "total_capacity_sats": sum(ch["capacity"] for ch in channels),
        "local_liquidity_sats": sum(ch["local_balance"] for ch in channels),
    }
```

---

## State Transitions to Know

### Happy Path
```
INITIATED 
  → INVOICE_GENERATED (generate_invoice)
  → PAYMENT_LOCKED (check_payment_received)
  → RECEIVER_VERIFIED (verify_receiver + verify_agent)
  → PAYOUT_EXECUTED (execute_payout)
  → SETTLED (mark_settled)
```

### Error Path
```
Any State → REFUNDED (refund_transfer)
```

---

## Key Concepts

### Hold Invoices
- **What**: Lightning invoice that doesn't immediately settle
- **Why**: Allows us to verify receiver before releasing funds
- **How**: LND stores preimage separately, only settles when we call settle_invoice()

### Preimage
- **What**: 32-byte random secret, hash is the payment_hash
- **Why**: Proof of payment settlement
- **Storage**: InvoiceHold table (should be encrypted)

### State Machine
- **Why**: Ensures correct order of operations
- **Guards**: Each transition checks preconditions
- **Audit**: Every change logged to TransferHistory

### Rate Caching
- **Why**: Avoid excessive API calls
- **Strategy**: Memory (5min) → Database (persistent) → Fallback (stale)
- **Smart**: Only refreshes on expiry

---

## Common Errors & Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `Agent not found` | agent_id invalid | Verify agent exists & is ACTIVE |
| `Invoice not found` | LND didn't store it | Check LND logs, retry invoice creation |
| `Cannot settle: invoice not held` | Wrong state | Ensure invoice is held before settle |
| `Rate fetch failed` | External API down | Falls back to DB cache |
| `Payment timeout` | Sender didn't pay | Background task refunds after TTL |
| `Verification timeout` | Receiver didn't verify | Background task refunds after timeout |

---

## Integration with FastAPI

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.db import get_db

router = APIRouter(prefix="/api/v1/transfers")

@router.post("/initiate")
async def initiate(
    sender_phone: str,
    receiver_phone: str,
    receiver_name: str,
    amount_zar: float,
    agent_id: str,
    db: Session = Depends(get_db),
):
    from src.services import TransferService, RateService
    from decimal import Decimal
    import uuid
    
    transfer_svc = TransferService(db)
    rate_svc = RateService(db)
    
    # Validate
    validation = await rate_svc.validate_transfer_amount(Decimal(str(amount_zar)))
    if not validation["valid"]:
        raise HTTPException(status_code=400, detail=validation["error"])
    
    # Create
    transfer = await transfer_svc.initiate_transfer(
        sender_phone=sender_phone,
        receiver_phone=receiver_phone,
        receiver_name=receiver_name,
        receiver_location="ZWE_HRR",
        amount_zar=Decimal(str(amount_zar)),
        amount_sats=validation["amount_sats"],
        rate_zar_per_btc=validation["rate_zar_per_btc"],
        agent_id=uuid.UUID(agent_id),
    )
    
    invoice = await transfer_svc.generate_invoice(transfer.id)
    
    return {
        "transfer_id": str(transfer.id),
        "reference": transfer.reference,
        "payment_request": invoice["payment_request"],
        "expires_at": invoice["invoice_expiry_at"],
    }

@router.get("/{transfer_id}/status")
async def get_status(
    transfer_id: str,
    db: Session = Depends(get_db),
):
    from src.services import TransferService
    import uuid
    
    transfer_svc = TransferService(db)
    transfer = await transfer_svc.get_transfer(uuid.UUID(transfer_id))
    
    if not transfer:
        raise HTTPException(status_code=404)
    
    return {
        "reference": transfer.reference,
        "state": transfer.state.value,
        "amount_sats": transfer.amount_sats,
        "created_at": transfer.created_at,
    }
```

---

## Async/Await Patterns

All service methods are async and must be called with `await`:

```python
# ✅ Correct
is_paid = await transfer_svc.check_payment_received(transfer_id)

# ❌ Wrong
is_paid = transfer_svc.check_payment_received(transfer_id)  # Returns coroutine

# ✅ In FastAPI endpoint
@app.get("/check")
async def check():
    result = await service.method()
    return result
```

---

## Database Session Management

Services depend on SQLAlchemy Session:

```python
from sqlalchemy.orm import Session

# Single session per request (FastAPI)
async def endpoint(db: Session = Depends(get_db)):
    svc = TransferService(db)
    result = await svc.method()
    # Session auto-commits/rolls back after endpoint

# Multiple operations
try:
    result = await svc.operation1()
    result = await svc.operation2()
    db.commit()  # Commit batch
except Exception:
    db.rollback()
    raise
```

---

## Logging

All services log to Python logger:

```python
import logging

logger = logging.getLogger(__name__)

# View logs
logger.info("Transfer created")     # INFO level
logger.warning("Invoice expired")   # WARNING level
logger.error("Settlement failed")   # ERROR level
logger.debug("Rate cached")         # DEBUG level
```

Configure in FastAPI:

```python
logging.basicConfig(level=logging.DEBUG)
```

---

## Next: Implement API Routes

With these services ready, implement the 28 API endpoints:
- Transfer creation (1)
- Payment monitoring (2)
- Verification (3)
- Agent operations (8)
- Admin operations (5)
- Reporting (9+)

Reference: See [REFINED_PLAN.md](../REFINED_PLAN.md) for full endpoint list.
