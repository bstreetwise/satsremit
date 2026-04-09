# LND Webhook Integration Guide

## Overview

SatsRemit uses **LND webhooks** to receive payment notifications when Lightning invoices are settled. This enables automatic transfer state transitions and real-time notifications to receivers and agents.

## What Webhooks Do

When a receiver pays a Lightning invoice:
1. LND detects payment settlement
2. LND sends webhook to SatsRemit `/api/webhooks/lnd/invoice-settled`
3. SatsRemit marks transfer as `PAYMENT_LOCKED`
4. SatsRemit generates 4-digit PIN for receiver
5. SatsRemit sends WhatsApp to receiver with PIN
6. SatsRemit sends WhatsApp to agent about pending payout
7. Agent verifies receiver & processes cash payout

## Architecture

```
┌──────────────────┐
│  Lightning User  │
│  (Sender pays)   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   LND Node       │ ← Detects payment
│                  │
└────────┬─────────┘
         │
         ▼ (Webhook POST)
┌──────────────────────────────────┐
│  SatsRemit Webhook Endpoint      │
│  /api/webhooks/lnd/invoice-settled│
└────────┬─────────────────────────┘
         │
         ▼
┌──────────────────────────────────┐
│  WebhookService                  │
│  ├─ Find transfer by invoice     │
│  ├─ Update state to PAYMENT_LOCKED
│  ├─ Generate PIN                 │
│  ├─ Send receiver WhatsApp       │
│  └─ Send agent WhatsApp          │
└──────────────────────────────────┘
```

## Setup Instructions

### Step 1: Update LND Configuration

Edit `/data/lnd/lnd.conf` (on VPS):

```ini
[Application Options]
# ... existing settings ...

# Enable keysend for testing
accept-keysend=true

# Optional: Configure webhook settings
# webhook-url=https://api.satsremit.com/api/webhooks/lnd/invoice-settled
```

### Step 2: Subscribe to Invoice Events

LND supports subscribing to invoice events via the gRPC API. SatsRemit uses this internally.

**Option A: Via LNCli (Manual Testing)**
```bash
# SSH into VPS
ssh ubuntu@vm-1327.lnvps.cloud

# Subscribe to all invoice events (runs continuously)
sudo -u bitcoin lncli --lnddir=/home/bitcoin/.lnd \
  subscribeinvoices

# This will print all invoice state changes
# CREATED, ACCEPTED, SETTLED, CANCELLED, etc.
```

**Option B: Via API (Automatic - Recommended)**

The SatsRemit backend can establish a gRPC stream to LND to receive invoice events.

Update `src/services/lnd.py`:
```python
async def subscribe_to_invoices(self):
    """Subscribe to LND invoice events (gRPC stream)"""
    async for invoice in self.stub.SubscribeInvoices(lnrpc.InvoiceSubscription()):
        if invoice.state == lnrpc.Invoice.SETTLED:
            # Send webhook internally
            await self.process_invoice_settled(invoice)
```

### Step 3: Configure SatsRemit Webhook Endpoint

The webhook is already configured in the API. Just ensure:

1. **API is running** and accessible
2. **Database is configured** (`DATABASE_URL`)
3. **WhatsApp credentials** are set (for notifications)

Webhook endpoint: `POST /api/webhooks/lnd/invoice-settled`

## Webhook Payload

SatsRemit expects the following payload from LND:

```json
{
    "invoice_hash": "abc123def456...",
    "state": "SETTLED",
    "settled_at": "2026-04-09T14:30:00Z",
    "amount_milli_satoshis": 208333000
}
```

**Field Descriptions:**
- `invoice_hash` (string): Hash of the invoice (payment hash)
- `state` (string): Invoice state ("SETTLED")
- `settled_at` (datetime): When payment was received
- `amount_milli_satoshis` (int): Amount in milli-satoshis

## Testing Webhooks

### Manual Test: Create Invoice and Send Webhook

```bash
# 1. Create a transfer (generates invoice)
curl -X POST http://localhost:8000/api/transfers \
  -H "Content-Type: application/json" \
  -d '{
    "sender_phone": "+27712345678",
    "receiver_phone": "+263782123456",
    "receiver_name": "John Receiver",
    "receiver_location": "ZWE_HRR",
    "amount_zar": 250.00
  }'

# Response includes:
# {
#   "transfer_id": "550e8400-e29b-41d4-a716-446655440000",
#   "invoice_hash": "abc123def456...",
#   "invoice_request": "lnbc2500000n1p0abcdx..."
# }

# 2. Simulate invoice settlement by sending webhook
curl -X POST http://localhost:8000/api/webhooks/lnd/invoice-settled \
  -H "Content-Type: application/json" \
  -d '{
    "invoice_hash": "abc123def456...",
    "state": "SETTLED",
    "settled_at": "2026-04-09T14:30:00Z",
    "amount_milli_satoshis": 208333000
  }'

# Response:
# {
#   "status": "success",
#   "transfer_id": "550e8400-e29b-41d4-a716-446655440000",
#   "message": "Transfer marked as payment received"
# }

# 3. Check transfer status (should be PAYMENT_LOCKED)
curl http://localhost:8000/api/transfers/550e8400-e29b-41d4-a716-446655440000/status
```

### Integration Test: Full Flow

```bash
#!/bin/bash

# 1. Create transfer
TRANSFER=$(curl -s -X POST http://localhost:8000/api/transfers \
  -H "Content-Type: application/json" \
  -d '{
    "sender_phone": "+27712345678",
    "receiver_phone": "+263782123456",
    "receiver_name": "John Receiver",
    "receiver_location": "ZWE_HRR",
    "amount_zar": 250.00
  }')

TRANSFER_ID=$(echo $TRANSFER | jq -r '.transfer_id')
INVOICE_HASH=$(echo $TRANSFER | jq -r '.invoice_hash')

echo "Created transfer: $TRANSFER_ID"
echo "Invoice hash: $INVOICE_HASH"

# 2. Verify status is INVOICE_GENERATED
STATUS=$(curl -s http://localhost:8000/api/transfers/$TRANSFER_ID/status)
echo "Initial status: $(echo $STATUS | jq -r '.state')"

# 3. Simulate webhook (payment received)
curl -s -X POST http://localhost:8000/api/webhooks/lnd/invoice-settled \
  -H "Content-Type: application/json" \
  -d "{
    \"invoice_hash\": \"$INVOICE_HASH\",
    \"state\": \"SETTLED\",
    \"settled_at\": \"$(date -u +'%Y-%m-%dT%H:%M:%SZ')\",
    \"amount_milli_satoshis\": 208333000
  }"

# 4. Check status is PAYMENT_LOCKED
sleep 1
STATUS=$(curl -s http://localhost:8000/api/transfers/$TRANSFER_ID/status)
echo "After payment: $(echo $STATUS | jq -r '.state')"

# 5. View webhook history
curl -s http://localhost:8000/api/webhooks/history | jq
```

## Webhook Response

SatsRemit webhook returns a standardized response:

**Success (200 OK):**
```json
{
    "status": "success",
    "transfer_id": "550e8400-e29b-41d4-a716-446655440000",
    "message": "Transfer marked as payment received"
}
```

**Error (400/500):**
```json
{
    "status": "error",
    "transfer_id": null,
    "message": "Transfer not found"
}
```

## Webhook Delivery Guarantees

### Idempotency
Webhooks are **idempotent** - safe to retry multiple times:
- If transfer already in `PAYMENT_LOCKED`, webhook returns success without side effects
- Same PIN generated if already set
- Notifications sent again (not ideal but safe)

### Reliability
- Webhook logs stored in `webhooks` table
- Failed webhooks have `retry_count` and `error_message`
- Manual retry via `POST /api/webhooks/retry-failed`
- Background tasks retry automatically (coming in Phase 4)

### Monitoring
```bash
# Check webhook delivery history
curl http://localhost:8000/api/webhooks/history | jq

# Response:
# {
#   "count": 5,
#   "webhooks": [
#     {
#       "id": "...",
#       "event_type": "lnd.invoice.settled",
#       "status": "delivered",
#       "retry_count": 0,
#       "created_at": "2026-04-09T14:30:00Z",
#       "processed_at": "2026-04-09T14:30:01Z",
#       "error": null
#     }
#   ]
# }

# Manually retry failed webhooks
curl -X POST http://localhost:8000/api/webhooks/retry-failed
```

## Webhook Security

### Current Implementation
- No signature verification (for MVP)
- Assumes firewall/network security

### Future Enhancements
1. **HMAC Signature Verification**
   ```python
   # Verify X-Signature header
   import hmac
   import hashlib
   
   expected_sig = hmac.new(
       settings.webhook_secret.encode(),
       payload.encode(),
       hashlib.sha256
   ).hexdigest()
   
   if x_signature != expected_sig:
       raise HTTPException(status_code=401)
   ```

2. **Webhook Secret Configuration**
   ```bash
   # In .env
   WEBHOOK_SECRET=your-secret-key-here
   ```

3. **IP Whitelisting**
   - Only accept webhooks from LND node IP
   - Configure in firewall or middleware

## Troubleshooting

### Webhook Not Received

```bash
# 1. Check LND is running
sudo systemctl status lnd

# 2. Check LND logs for webhook attempts
sudo journalctl -u lnd -f | grep -i webhook

# 3. Check SatsRemit logs
sudo journalctl -u satsremit -f | grep -i webhook

# 4. Verify API is responding
curl http://localhost:8000/health

# 5. Test webhook endpoint directly
curl -X POST http://localhost:8000/api/webhooks/lnd/invoice-settled \
  -H "Content-Type: application/json" \
  -d '{"invoice_hash":"test","state":"SETTLED","settled_at":"2026-04-09T14:30:00Z","amount_milli_satoshis":1000}'
```

### Transfer Not Updating

```bash
# 1. Check webhook was received
curl http://localhost:8000/api/webhooks/history | jq

# 2. Check database directly
psql $DATABASE_URL -c "SELECT * FROM transfer_history WHERE created_at > now() - interval '5 minutes';"

# 3. Check transfer state
psql $DATABASE_URL -c "SELECT id, reference, state FROM transfers WHERE created_at > now() - interval '5 minutes';"
```

### WhatsApp Notification Not Sent

```bash
# 1. Check WhatsApp credentials in .env
grep WHATSAPP .env

# 2. Check notification logs
sudo journalctl -u satsremit -f | grep -i whatsapp

# 3. Verify phone number format (E.164)
# Should be: +263782123456
# Not: 263782123456 or 0782123456
```

## LND Command Reference

### Create Invoice
```bash
sudo -u bitcoin lncli --lnddir=/home/bitcoin/.lnd \
  addinvoice --memo="SatsRemit Transfer" --amt=50000
```

### Subscribe to Invoices (Manual)
```bash
sudo -u bitcoin lncli --lnddir=/home/bitcoin/.lnd \
  subscribeinvoices
```

### List Invoices
```bash
sudo -u bitcoin lncli --lnddir=/home/bitcoin/.lnd \
  listinvoices
```

### Lookup Invoice
```bash
sudo -u bitcoin lncli --lnddir=/home/bitcoin/.lnd \
  lookupinvoice --rhash=abc123...
```

## API Endpoints

### Webhook Endpoints

**POST** `/api/webhooks/lnd/invoice-settled`
- Receive LND invoice settlement callback
- Payload: `LNDInvoiceSettledWebhook`
- Returns: `LNDInvoiceSettledResponse`

**GET** `/api/webhooks/health`
- Health check for webhook service
- Returns: Service status and endpoint list

**GET** `/api/webhooks/history?limit=100`
- Get webhook delivery history
- Returns: List of recent webhooks with status

**POST** `/api/webhooks/retry-failed`
- Manually retry failed webhook deliveries
- Returns: Retry statistics (attempted, succeeded, failed)

## Next Steps

1. **Complete Option B** ✅
   - Webhook endpoint implemented
   - Service handles state transitions
   - Notifications configured

2. **Option C: Background Tasks** ⏳
   - Celery worker for async operations
   - Periodically check for stuck transfers
   - Auto-retry failed webhooks
   - Settlement processor

3. **Testing** ⏳
   - Full end-to-end flow testing
   - Load testing with multiple concurrent transfers

---

**Status**: ✅ Option B (Webhook Handlers) Complete  
**Implementation Date**: April 9, 2026  
**Ready for**: Option C (Background Tasks) or End-to-End Testing
