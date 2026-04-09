# API Integration & Testing Guide

## Quick Start

### 1. Start the Application

```bash
# Navigate to project
cd /home/satsinaction/satsremit

# Install dependencies (if needed)
pip install -r requirements.txt

# Run application
python -m uvicorn src.main:create_app --host 0.0.0.0 --port 8000 --reload
```

App will be available at: `http://localhost:8000`
OpenAPI docs: `http://localhost:8000/api/docs`
ReDoc: `http://localhost:8000/api/redoc`

---

## API Testing Workflow

### Phase 1: Health Check
```bash
# Check system is running
curl http://localhost:8000/health

# Response should be:
# {
#   "status": "healthy",
#   "bitcoind_synced": true,
#   "lnd_active": true,
#   "db_connected": true,
#   "redis_connected": true
# }
```

### Phase 2: Exchange Rates
```bash
# Get current ZAR/BTC rate
curl http://localhost:8000/api/rates/zar-btc

# Response: { "pair": "ZAR_BTC", "rate": "120000.00", "source": "coingecko" }
```

### Phase 3: Quote & Validation
```bash
# Get quote for 250 ZAR transfer
curl -X POST http://localhost:8000/api/transfers/quote \
  -H "Content-Type: application/json" \
  -d '{
    "amount_zar": 250.00
  }'

# Response:
# {
#   "amount_zar": 250.00,
#   "amount_sats": 208333,
#   "platform_fee_zar": 1.25,
#   "agent_commission_zar": 1.25,
#   "total_fees_zar": 2.50,
#   "receiver_gets_zar": 247.50,
#   "rate_zar_per_btc": 120000.00
# }
```

### Phase 4: Create Transfer
```bash
# Create a new transfer (generates invoice)
curl -X POST http://localhost:8000/api/transfers \
  -H "Content-Type: application/json" \
  -d '{
    "sender_phone": "+27712345678",
    "receiver_phone": "+263782123456",
    "receiver_name": "John Receiver",
    "receiver_location": "ZWE_HRR",
    "amount_zar": 250.00
  }'

# Response:
# {
#   "transfer_id": "550e8400-e29b-41d4-a716-446655440000",
#   "reference": "20260409141530A1B2C3D4E5",
#   "invoice_hash": "abc1def2...",
#   "invoice_request": "lnbc2500000n1p0abcdxpp5...",
#   "amount_sats": 208333,
#   "amount_zar": 250.00,
#   "expires_at": "2026-04-10T14:15:30Z",
#   "agent_name": "John Agent",
#   "agent_location": "Harare",
#   "status_url": "/api/transfers/550e8400-e29b-41d4-a716-446655440000/status"
# }

# Save transfer_id and reference for next steps
TRANSFER_ID="550e8400-e29b-41d4-a716-446655440000"
REFERENCE="20260409141530A1B2C3D4E5"
```

### Phase 5: Display QR Code to Sender
```bash
# The invoice_request from Phase 4 can be displayed as QR code
# Libraries: qrcode (Python), qr-code (JS), etc.

# For testing, just copy the invoice_request and scan with Lightning wallet
# Or pay manually: /api/transfers/{transfer_id}/status to check
```

### Phase 6: Poll Payment Status
```bash
# Agency or platform polls until payment received
curl http://localhost:8000/api/transfers/$TRANSFER_ID/status

# Polling response (while waiting):
# {
#   "reference": "20260409141530A1B2C3D4E5",
#   "state": "INVOICE_GENERATED",
#   "receiver_phone_verified": false,
#   "agent_verified": false,
#   "receiver_received": false,
#   "settlement_date": null
# }

# After payment received:
# {
#   "reference": "20260409141530A1B2C3D4E5",
#   "state": "PAYMENT_LOCKED",
#   "receiver_phone_verified": false,
#   "agent_verified": false,
#   "receiver_received": false,
#   "settlement_date": null
# }
```

---

## Agent Flow Testing

### Step 1: Agent Login
```bash
# Agent authenticates
curl -X POST http://localhost:8000/api/agent/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "+263784000001",
    "password": "SecurePassword123!"
  }'

# Response:
# {
#   "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
#   "token_type": "bearer",
#   "expires_in": 86400,
#   "agent_id": "550e8400-e29b-41d4-a716-446655440001",
#   "agent_name": "John Agent",
#   "agent_phone": "+263784000001"
# }

# Save token for subsequent requests
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### Step 2: Check Agent Balance
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/agent/balance

# Response:
# {
#   "cash_balance_zar": 5000.00,
#   "commission_balance_sats": 10000,
#   "total_commission_zar": 12.00,
#   "pending_settlement_zar": 0.00,
#   "payout_date": "Sunday"
# }
```

### Step 3: Get Pending Transfers
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/agent/transfers

# Response (list of PAYMENT_LOCKED transfers):
# [
#   {
#     "transfer_id": "550e8400-...",
#     "reference": "20260409141530A1B2C3D4E5",
#     "receiver_name": "John Receiver",
#     "receiver_phone": "+263782123456",
#     "receiver_location": "Harare",
#     "amount_zar": 250.00,
#     "amount_sats": 208333,
#     "created_at": "2026-04-09T14:15:30Z",
#     "expires_at": "2026-04-10T14:15:30Z"
#   }
# ]
```

### Step 4: Verify Receiver (with PIN)
```bash
# Sender/receiver gets PIN via WhatsApp
# Agent enters PIN + confirms phone match

curl -X POST http://localhost:8000/api/agent/transfers/$TRANSFER_ID/verify \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "pin": "1234",
    "phone_verified": true
  }'

# Response:
# {
#   "verified": true,
#   "instruction": "Proceed with cash payout to receiver",
#   "message": "Ready to pay John Receiver 250.00 ZAR"
# }
```

### Step 5: Confirm Payout (Agent Paid Cash)
```bash
# Agent confirms they paid the cash

curl -X POST http://localhost:8000/api/agent/transfers/$TRANSFER_ID/confirm-payout \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "confirmation_note": "Paid in cash, ref: TX123456"
  }'

# Response:
# {
#   "status": "payout_confirmed",
#   "message": "Payout of 250.00 ZAR confirmed",
#   "settlement_pending": true
# }

# At this point:
# - Invoice is settled to platform
# - Receiver gets 250 ZAR - 2.50 ZAR (fees) = 247.50 ZAR
# - Agent commission (0.5%) = 1.25 ZAR in sats
# - Platform fee (0.5%) = 1.25 ZAR in sats
```

### Step 6: Check Settlement
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/agent/settlements

# Response (list of weekly settlements):
# [
#   {
#     "settlement_id": "550e8400-...",
#     "period_start": "2026-04-07T00:00:00Z",
#     "period_end": "2026-04-13T23:59:59Z",
#     "amount_zar": 5250.00,
#     "amount_sats": 250000,
#     "status": "PENDING",
#     "due_date": "2026-04-14T00:00:00Z"
#   }
# ]
```

### Step 7: Confirm Settlement Received
```bash
SETTLEMENT_ID="550e8400-..."

curl -X POST http://localhost:8000/api/agent/settlements/$SETTLEMENT_ID/confirm \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "payment_method": "bank_transfer",
    "reference_number": "ZIM-BANK-12345-67890",
    "note": "Payment received to Econet account"
  }'

# Response:
# {
#   "confirmed": true,
#   "settlement_id": "550e8400-...",
#   "next_payment_due": "2026-04-21T00:00:00Z"
# }
```

---

## Admin API Testing

### Step 1: Create Agent (Admin)
```bash
# Admin creates new agent
curl -X POST http://localhost:8000/api/admin/agents \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "+263783000001",
    "name": "New Agent",
    "location_code": "ZWE_HRR",
    "initial_cash_zar": 10000.00
  }'

# Response:
# {
#   "agent_id": "550e8400-...",
#   "phone": "+263783000001",
#   "name": "New Agent",
#   "status": "ACTIVE",
#   "cash_balance_zar": 10000.00
# }
```

### Step 2: Record Cash Advance
```bash
AGENT_ID="550e8400-..."

# Admin records cash advance or correction
curl -X POST http://localhost:8000/api/admin/agents/$AGENT_ID/advance \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "zar_amount": 5000.00,
    "note": "Emergency cash advance for high volume day"
  }'

# Response:
# {
#   "agent_id": "550e8400-...",
#   "new_balance_zar": 15000.00,
#   "transaction_id": "ADV-A1B2C3D4"
# }
```

### Step 3: View Transfer Audit
```bash
# View all transfers (with filtering)
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  "http://localhost:8000/api/admin/transfers?state=SETTLED&limit=10"

# Response:
# [
#   {
#     "transfer_id": "550e8400-...",
#     "reference": "20260409141530A1B2C3D4E5",
#     "amount_zar": 250.00,
#     "amount_sats": 208333,
#     "state": "SETTLED",
#     "agent_name": "John Agent",
#     "created_at": "2026-04-09T14:15:30Z",
#     "settled_at": "2026-04-09T14:18:00Z"
#   }
# ]
```

### Step 4: View Analytics
```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/api/admin/volume

# Response:
# {
#   "daily_volume_zar": 5000.00,
#   "daily_transfers": 20,
#   "weekly_volume_zar": 35000.00,
#   "weekly_transfers": 140,
#   "monthly_volume_zar": 150000.00,
#   "monthly_transfers": 600,
#   "total_fees_collected_sats": 12500,
#   "platform_earn_sats": 6250,
#   "agent_earn_sats": 6250
# }
```

### Step 5: System Health
```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/api/admin/health

# Response:
# {
#   "status": "healthy",
#   "active_agents": 5,
#   "pending_transfers": 3,
#   "total_cash_in_system": 50000.00,
#   "timestamp": "2026-04-09T14:30:00Z"
# }
```

---

## Error Testing

### Invalid Amount (Below Minimum)
```bash
curl -X POST http://localhost:8000/api/transfers/quote \
  -H "Content-Type: application/json" \
  -d '{"amount_zar": 50.00}'

# Response (400):
# {
#   "error": "Minimum transfer: ZAR 100",
#   "code": "VALIDATION_ERROR",
#   "timestamp": "2026-04-09T14:30:00Z"
# }
```

### Invalid Agent
```bash
curl -X POST http://localhost:8000/api/transfers \
  -H "Content-Type: application/json" \
  -d '{
    "sender_phone": "+27712345678",
    "receiver_phone": "+263782123456",
    "receiver_name": "John",
    "receiver_location": "INVALID_LOCATION",
    "amount_zar": 250.00
  }'

# Response (400):
# {
#   "error": "No active agent in INVALID_LOCATION",
#   "code": "NO_AGENT_AVAILABLE",
#   "timestamp": "2026-04-09T14:30:00Z"
# }
```

### Insufficient Agent Cash
```bash
# Same as above but agent has < 250 ZAR

# Response (400):
# {
#   "error": "Agent insufficient cash - try again later",
#   "code": "AGENT_INSUFFICIENT_FUNDS",
#   "timestamp": "2026-04-09T14:30:00Z"
# }
```

### Invalid Token
```bash
curl -H "Authorization: Bearer invalid.token.here" \
  http://localhost:8000/api/agent/balance

# Response (401):
# {
#   "error": "Invalid token",
#   "code": "UNAUTHORIZED",
#   "timestamp": "2026-04-09T14:30:00Z"
# }
```

---

## Integration Checklist

- [ ] Database initialized and populated
  - [ ] PostgreSQL running
  - [ ] Tables created
  - [ ] At least 1 agent record for testing

- [ ] LND connectivity verified
  - [ ] LND node running (testnet4)
  - [ ] Admin macaroon accessible
  - [ ] TLS certificate valid

- [ ] Redis cache running (optional, will work without)

- [ ] Application starts without errors
  - [ ] `python -m uvicorn src.main:create_app --reload`
  - [ ] Logs show successful init

- [ ] Public endpoints accessible
  - [ ] `GET /health` returns 200
  - [ ] `GET /rates/zar-btc` returns valid rate
  - [ ] `GET /locations` returns agent list

- [ ] JWT authentication working
  - [ ] Agent login returns token
  - [ ] Protected endpoints reject missing token
  - [ ] Protected endpoints reject invalid token
  - [ ] Protected endpoints allow valid token

- [ ] Full flow tested end-to-end
  - [ ] Create transfer → Get invoice
  - [ ] Agent verifies receiver
  - [ ] Agent confirms payout
  - [ ] Admin sees settled transfer

---

## Troubleshooting

### "Database connection failed"
```bash
# Check PostgreSQL running
psql -U postgres -c "SELECT 1"

# Check DATABASE_URL in .env
echo $DATABASE_URL
```

### "LND connection refused"
```bash
# Check LND running
lnd --version

# Check REST port accessible
curl -k https://localhost:8080/v1/getinfo
```

### "Module not found: src.xxx"
```bash
# Ensure in project root
cd /home/satsinaction/satsremit

# Reinstall dependencies
pip install -r requirements.txt

# Or run with python -m
python -m uvicorn src.main:create_app
```

### "JWT token invalid"
```bash
# Check JWT secret in .env
grep JWT_SECRET .env

# Generate new token and try again
```

---

## Performance Notes

- **Quote endpoint**: ~100-500ms (includes rate fetch/cache)
- **Create transfer**: ~200-500ms (LND invoice creation)
- **Verify transfer**: ~50-100ms (quick DB update)
- **Status check**: <10ms (cached DB query)

For production, enable:
- Database connection pooling
- Redis caching
- CloudFlare CDN
- Load balancing

---

## Next: Webhook Testing

After main API working, test LND callbacks:

```bash
# LND will POST to webhook endpoint
POST /api/webhooks/lnd/invoice-settled
Content-Type: application/json
Authorization: Bearer webhook-secret

{
  "invoice_hash": "abc123...",
  "state": "SETTLED",
  "settled_at": "2026-04-09T14:30:00Z",
  "amount_milli_satoshis": 208333000
}
```

This automatically transitions transfer to PAYMENT_LOCKED and notifies receiver.
