# Lightning Network Services Architecture

## Overview

Three core service layers manage the Lightning Network remittance flow:

1. **LNDService** - Low-level LND REST API operations
2. **TransferService** - Business logic & state machine
3. **RateService** - Exchange rate management

These services work together to orchestrate end-to-end transfers while Bitcoin syncs in the background.

---

## 1. LNDService (`src/services/lnd.py`)

**Purpose**: Direct LND REST API wrapper for Lightning operations

### Key Methods

#### Invoice Management
```python
# Create a hold invoice (user pays us)
invoice = await lnd.create_hold_invoice(
    amount_sats=100000,
    memo="SatsRemit: TRF123456789AB"
)
# Returns: {payment_hash, payment_request, add_index}

# Check if payment received
is_paid = await lnd.check_invoice_paid(payment_hash)

# Settle invoice with preimage (release funds to receiver)
result = await lnd.settle_invoice(preimage)
```

#### Wallet Operations
```python
# Get wallet balance
balance = await lnd.get_wallet_balance()
# Returns: {total_balance, confirmed_balance, unconfirmed_balance}

# Generate on-chain address (for funding)
address = await lnd.new_address()
```

#### Channel Management
```python
# List open channels
channels = await lnd.list_channels(active_only=True)

# Send payment (if we need to pay out via Lightning)
result = await lnd.send_payment(payment_request)
```

#### Node Info
```python
# Get node details
info = await lnd.get_node_info()
# Returns: {identity_pubkey, alias, num_peers, num_active_channels, ...}
```

### Configuration
- **REST URL**: From `config.lnd_rest_url` (e.g., `https://localhost:8080`)
- **Macaroon Path**: From `config.lnd_macaroon_path` (admin.macaroon)
- **Cert Path**: From `config.lnd_cert_path` (tls.cert)
- **Hold Invoice TTL**: From `config.lnd_hold_invoice_expiry_minutes` (default: 5760 = 4 days)

### Error Handling
- All methods have comprehensive logging
- Network errors returned or raised with context
- Async/await support for non-blocking operations

---

## 2. TransferService (`src/services/transfer.py`)

**Purpose**: Manage transfer lifecycle and state machine

### Transfer State Machine

```
INITIATED
   ↓
INVOICE_GENERATED (hold invoice created)
   ↓
PAYMENT_LOCKED (payment received + locked)
   ↓
RECEIVER_VERIFIED (phone verified + agent verified)
   ↓
PAYOUT_EXECUTED (cash payout completed, invoice settled)
   ↓
SETTLED (receiver confirmed receipt)
```

Alternative terminal states:
- `REFUNDED` - Transfer cancelled, payment reversed
- `FINAL` - Permanent completion state

### Core Methods

#### 1. Initiate Transfer
```python
transfer = await transfer_service.initiate_transfer(
    sender_phone="+263912345678",
    receiver_phone="+263987654321",
    receiver_name="John Doe",
    receiver_location="ZWE_HRR",  # Harare
    amount_zar=Decimal("2500.00"),
    amount_sats=100000,
    rate_zar_per_btc=Decimal("120000.00"),
    agent_id=uuid.UUID("...")
)
# Creates: Transfer record in INITIATED state
# Validates: Agent exists and is ACTIVE
# Returns: Transfer object
# Logs: State change to TransferHistory
```

#### 2. Generate Invoice
```python
invoice = await transfer_service.generate_invoice(transfer_id)
# Generates: Hold invoice via LND
# Creates: Invoice record on transfer
# Transitions: INITIATED → INVOICE_GENERATED
# Returns: {payment_hash, payment_request, invoice_expiry_at}
```

#### 3. Monitor Payment
```python
is_paid = await transfer_service.check_payment_received(transfer_id)
if is_paid:
    # Automatically transitions: INVOICE_GENERATED → PAYMENT_LOCKED
    # Logs state change
```

#### 4. Verify Receiver
```python
transfer = await transfer_service.verify_receiver(transfer_id, verified=True)
# Marks: receiver_phone_verified = True
# Checks: If both receiver + agent verified
# Transitions: (if both verified) PAYMENT_LOCKED → RECEIVER_VERIFIED
```

#### 5. Verify Agent
```python
transfer = await transfer_service.verify_agent(transfer_id, verified=True)
# Marks: agent_verified = True
# Checks: If both receiver + agent verified
# Transitions: (if both verified) PAYMENT_LOCKED → RECEIVER_VERIFIED
```

#### 6. Execute Payout
```python
transfer = await transfer_service.execute_payout(transfer_id)
# Requires: State must be RECEIVER_VERIFIED
# Generates: Random preimage (32 bytes)
# Stores: InvoiceHold record with encrypted preimage
# Calls: LND settle_invoice(preimage)
# Transitions: RECEIVER_VERIFIED → PAYOUT_EXECUTED
# Logs: Everything to TransferHistory
```

#### 7. Mark Settled
```python
transfer = await transfer_service.mark_settled(transfer_id)
# Transitions: PAYOUT_EXECUTED → SETTLED
# Records: settled_at timestamp
```

#### 8. Refund Transfer
```python
transfer = await transfer_service.refund_transfer(
    transfer_id,
    reason="Receiver not available"
)
# Refunds: If in INVOICE_GENERATED, PAYMENT_LOCKED, or RECEIVER_VERIFIED
# Transitions: Any state → REFUNDED
# Note: In real implementation, trigger reverse payment to sender
```

### Audit Trail
Every state change is logged in `TransferHistory`:
- What changed: old_state → new_state
- Why: reason
- Who: actor_type (system, sender, agent, admin)
- When: created_at timestamp

### Database Requirements
- `transfers` table
- `transfer_history` table (audit log)
- `invoice_holds` table (preimage storage)

---

## 3. RateService (`src/services/rate.py`)

**Purpose**: Exchange rate management for ZAR ↔ SAT conversion

### Key Methods

#### Get Current Rate
```python
rate_zar_per_btc = await rate_service.get_zar_per_btc()
# Returns: Decimal (e.g., Decimal("120000.25"))
# Fetches: From configured source (CoinGecko, Kraken, Bitstamp)
# Caches: In memory + database for configured minutes
# Falls Back: To stale DB cache if fetch fails
```

#### Conversions
```python
# Satoshis → ZAR
zar_amount = await rate_service.get_zar_for_sats(sats=100000)
# Returns: Decimal("25.00")

# ZAR → Satoshis
sats = await rate_service.get_sats_for_zar(zar=250.00)
# Returns: int (400000)
```

#### Validation
```python
validation = await rate_service.validate_transfer_amount(
    amount_zar=Decimal("2500.00")
)
# Returns:
# {
#     "valid": True/False,
#     "amount_zar": Decimal("2500.00"),
#     "amount_sats": 20833333,
#     "rate_zar_per_btc": Decimal("120000.00"),
#     "error": None or error message
# }
# Checks: Min/max transfer limits
# Validates: Non-zero satoshi amounts
```

#### Fee Breakdown
```python
fees = await rate_service.get_fee_breakdown(
    amount_zar=Decimal("2500.00")
)
# Returns:
# {
#     "amount_zar": Decimal("2500.00"),
#     "platform_fee_zar": Decimal("12.50"),      # 0.5%
#     "agent_commission_zar": Decimal("12.50"),  # 0.5%
#     "total_fees_zar": Decimal("25.00"),
#     "receiver_gets_zar": Decimal("2475.00")
# }
```

### Rate Sources

#### CoinGecko (Free, Public)
- No authentication required
- API: `coingecko.com/api/v3/simple/price`
- Pair: `bitcoin` vs `zar`
- Good for non-critical applications

#### Kraken (Professional)
- Public ticker (no auth required for basic ticker)
- API: `api.kraken.com/0/public/Ticker`
- Pair: `XBTCZAR`
- More reliable for production

#### Bitstamp (Professional)
- Public ticker (no auth required)
- API: `bitstamp.net/api/v2/ticker/btczar/`
- Good secondary source

### Caching Strategy
1. **Memory Cache**: 5-minute TTL (configurable)
2. **Database Cache**: Persistent RateCache records
3. **Fallback**: Stale DB cache if fetch fails
4. **Smart Refresh**: Only fetches if cache expired

### Configuration
```python
# From config.py
rate_source: str = "coingecko"           # Primary source
rate_cache_minutes: int = 5              # Cache TTL

# From BaseSettings
min_transfer_zar: float = 100.0
max_transfer_zar: float = 500.0
platform_fee_percent: float = 0.5        # Platform takes 0.5%
agent_commission_percent: float = 0.5    # Agent takes 0.5%
```

---

## Service Integration Flow

### Complete Transfer Flow

```
1. INITIATE
   └─→ TransferService.initiate_transfer()
       ├─ Create Transfer (INITIATED state)
       ├─ Validate agent exists
       └─ Log to TransferHistory

2. QUOTE & VALIDATE
   └─→ RateService.validate_transfer_amount()
       ├─ Fetch ZAR/BTC rate (may cache/fetch/fallback)
       ├─ Convert ZAR → SAT
       ├─ Check min/max limits
       └─ Return fee breakdown

3. GENERATE INVOICE
   └─→ TransferService.generate_invoice()
       └─→ LNDService.create_hold_invoice()
           ├─ Create hold invoice via LND
           ├─ Store invoice_hash + payment_request
           └─ Transition to INVOICE_GENERATED

4. WAIT FOR PAYMENT
   └─→ TransferService.check_payment_received() [Poll/Webhook]
       └─→ LNDService.check_invoice_paid()
           ├─ Check if payment settled
           └─ Transition to PAYMENT_LOCKED

5. VERIFY PARTIES
   ├─→ TransferService.verify_receiver() [PIN check]
   ├─→ TransferService.verify_agent() [Agent confirms]
   └─→ Auto-transitions to RECEIVER_VERIFIED when both done

6. EXECUTE PAYOUT
   └─→ TransferService.execute_payout()
       ├─ Generate preimage
       ├─ Store in InvoiceHold (encrypted)
       └─→ LNDService.settle_invoice(preimage)
           ├─ Settle hold invoice
           └─ Release payment to receiver

7. CONFIRM SETTLED
   └─→ TransferService.mark_settled()
       ├─ Transition to SETTLED
       ├─ Record settled_at
       └─ Complete transfer

8. NOTIFY VIA WHATSAPP
   └─→ NotificationService.send_whatsapp()
       ├─ Send completion notification
       └─ Include reference, amount received
```

---

## Error Handling & Recovery

### Payment Timeouts
```python
# If invoice not paid within TTL (default: 6.5 hours)
→ Background task detects expired invoice
→ Mark transfer as EXPIRED
→ Trigger refund flow
→ Notify sender
```

### Agent Verification Timeout
```python
# If agent doesn't verify within verification_timeout_minutes
→ Background task marks verification failed
→ Auto-refund transfer
→ Notify sender & agent
```

### Payout Execution Failure
```python
# If settle_invoice fails
→ PreimageStore remains locked
→ Log error with full context
→ Alert admin
→ Can manually retry with same preimage
```

### Network Errors
```python
# All HTTP/gRPC errors logged with:
- Timestamp
- Operation (method name)
- Context (payment_hash, transfer_id, etc.)
- Error details
- Retry recommendation
```

---

## Configuration Setup

### Required Environment Variables

```bash
# LND Configuration
LND_REST_URL=https://localhost:8080
LND_MACAROON_PATH=/home/bitcoin/.lnd/data/chain/bitcoin/testnet4/admin.macaroon
LND_CERT_PATH=/home/bitcoin/.lnd/tls.cert
LND_HOLD_INVOICE_EXPIRY_MINUTES=5760
LND_INVOICE_TIMEOUT_HOURS=6.5

# Rate Configuration
RATE_SOURCE=coingecko  # or kraken, bitstamp
RATE_CACHE_MINUTES=5

# Transfer Configuration
MIN_TRANSFER_ZAR=100.0
MAX_TRANSFER_ZAR=500.0
PLATFORM_FEE_PERCENT=0.5
AGENT_COMMISSION_PERCENT=0.5
```

### Database Models Required
- `Transfer` (8 columns + relationships)
- `Agent` (10+ columns)
- `TransferHistory` (audit trail)
- `InvoiceHold` (preimage storage)
- `RateCache` (rate persistence)

---

## Testing Strategy

### Unit Tests
```python
# test_lnd_service.py
- test_create_hold_invoice()
- test_check_invoice_paid()
- test_settle_invoice()
- test_get_wallet_balance()
- test_list_channels()

# test_transfer_service.py
- test_initiate_transfer()
- test_generate_invoice()
- test_payment_received()
- test_verify_receiver()
- test_verify_agent()
- test_execute_payout()
- test_state_transitions()
- test_audit_logging()

# test_rate_service.py
- test_get_rate_fresh_fetch()
- test_get_rate_from_cache()
- test_zar_to_sats_conversion()
- test_sats_to_zar_conversion()
- test_fee_calculation()
- test_validation_limits()
```

### Integration Tests
```python
# test_transfer_flow_e2e.py
- Test complete: INITIATED → SETTLED
- Test payment timeout & refund
- Test verification requirements
- Test rate caching
- Test error recovery
```

### Load Tests
```python
# test_concurrent_transfers.py
- 50 simultaneous transfers
- Rate limiting verification
- Database connection pooling
- Cache coherency under load
```

---

## Performance Notes

### LND Operations
- **Hold Invoice Creation**: ~100-200ms (network + blockchain IO)
- **Invoice Status Check**: ~50-100ms (cached in LND)
- **Settlement**: ~100-300ms (includes blockchain settlement)

### Rate Service
- **Fresh Fetch**: ~200-500ms (external API)
- **Cached Read**: <1ms (memory cache)
- **DB Cache**: ~5-10ms (database query)

### Recommendations
- Cache rates aggressively (5-15 min TTL)
- Check invoice status in background (not blocking API)
- Run settlement in async task (not synchronous)
- Pool database connections (min 5, max 20)

---

## Production Deployment Checklist

- [ ] Configure LND REST URL (production instance)
- [ ] Secure macaroon path (file permissions 0600)
- [ ] Enable TLS certificate validation
- [ ] Set up Redis for session management
- [ ] Configure primary + backup rate sources
- [ ] Enable database connection pooling
- [ ] Set up monitoring/alerting for state machines
- [ ] Configure background task workers (Celery/APScheduler)
- [ ] Enable audit logging to separate database
- [ ] Set up transaction rollback mechanisms
- [ ] Configure rate limiting per phone number
- [ ] Enable circuit breakers for external APIs
- [ ] Test recovery after LND restart
- [ ] Test rate source failover
- [ ] Load test with production volume estimates

---

## Next Steps

1. **Implement API Routes** (28 routes)
2. **Add Background Tasks** (invoice monitoring, timeout checks)
3. **Add Webhook Handlers** (LND payment notifications)
4. **Add Database Migrations** (SQLAlchemy)
5. **Add Integration Tests** 
6. **Deploy to Testnet4**
7. **Monitor & Optimize**
