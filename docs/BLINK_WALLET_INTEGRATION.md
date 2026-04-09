# Blink Wallet Integration Plan for SatsRemit

## Executive Summary

**Goal**: Enable Blink Wallet users in South Africa to send Lightning remittances to Zimbabwe using SatsRemit's API, with zero-fee Blink-to-Blink transfers and low-cost Lightning routing.

**Outcome**: Seamless SA → ZW remittance workflow without leaving Blink Wallet (redirect URI pattern)

---

## Part 1: Understanding the Integration Landscape

### Blink API Capabilities

| Feature | Support | Notes |
|---------|---------|-------|
| **Lightning Send** | ✅ Yes | Send via LNURL/Invoice |
| **Lightning Receive** | ✅ Yes | Generate invoices, webhook callbacks |
| **On-chain Send** | ✅ Yes | Bitcoin transactions |
| **USD/Stablesats** | ✅ Yes | 0.2% conversion spread |
| **BTC Native** | ✅ Yes | Bitcoin-only support |
| **Webhooks** | ✅ Yes | Payment event callbacks |
| **GraphQL API** | ✅ Yes | Full data access |
| **Blink-to-Blink Transfers** | ✅ Yes | **Zero fees** (key advantage) |

### SatsRemit API Capabilities (Current)

| Feature | Status | Endpoints |
|---------|--------|-----------|
| **Quote/Pricing** | ✅ Live | `/api/transfers/quote` |
| **Transfer Creation** | ✅ Live | `POST /api/transfers` |
| **Invoice Generation** | ✅ Live | Auto-generated in transfer response |
| **Status Tracking** | ✅ Live | `/api/transfers/{id}/status` |
| **Agent Verification** | ✅ Live | `POST /api/agent/transfers/{id}/verify` |
| **Webhook Reception** | 🟡 In Progress | `/api/webhooks/lnd/invoice-settled` |
| **Agent Auth** | ✅ Live | `POST /api/agent/auth/login` |

---

## Part 2: Integration Architecture

### Flow Diagram: Blink User → SatsRemit → Zimbabwe Agent

```
┌─────────────────────────────────────────────────────────────────────┐
│  BLINK WALLET (South Africa)                                        │
│  ├─ Open SatsRemit Widget/Deep Link                                 │
│  └─ Pre-fill sender phone from Blink account                        │
├─────────────────────────────────────────────────────────────────────┤
│  SATSREMIT API (Platform)                                           │
│  ├─ Get exchange rate (ZAR/BTC)                                    │
│  ├─ Calculate fees (0.5% platform + 0.5% agent)                   │
│  ├─ Generate Lightning Invoice (via LND)                           │
│  └─ Return invoice + transfer reference                            │
├─────────────────────────────────────────────────────────────────────┤
│  BLINK WALLET (Payment)                                             │
│  ├─ Pay Lightning Invoice via Blink                                │
│  └─ Confirmation → Callback to SatsRemit webhook                  │
├─────────────────────────────────────────────────────────────────────┤
│  SATSREMIT BACKEND                                                  │
│  ├─ Receive LND webhook (payment settled)                          │
│  ├─ Mark transfer as PAYMENT_LOCKED                               │
│  ├─ Generate PIN & send WhatsApp to receiver                      │
│  └─ Notify Zimbabwe agent of pending payout                       │
├─────────────────────────────────────────────────────────────────────┤
│  ZIMBABWE AGENT (Cash Payout)                                       │
│  ├─ Login to agent app                                              │
│  ├─ Get pending transfer with receiver details                     │
│  ├─ Verify receiver (phone + PIN)                                  │
│  ├─ Confirm cash payout (ZAR converted to USD/ZWL)               │
│  └─ System auto-settles weekly                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Technical Integration Points

```
BLINK WALLET                              SATSREMIT API
(Client-side)                             (Server-side)
     │                                         │
     ├─ 1. OpenURL("satsremit://...")        │
     │                                         │
     │◄─────────────────────────────────────►│
     │   2. GET /api/rates/zar-btc           │
     │                                         │
     │   3. Display Quote                     │
     │◄─────────────────────────────────────►│
     │   POST /api/transfers/quote           │
     │                                         │
     │   4. User confirms, clicks "Pay"      │
     │◄─────────────────────────────────────►│
     │   POST /api/transfers (get invoice)  │
     │                                         │
     │   5. Deep link back to Blink payment  │
     │   lightning://lnbc2500000n1p0abcdx...│
     │                                         │
     │   6. User scans/pays invoice in Blink │
     │                                         │
     │                                         ├─ LND receives payment
     │                                         ├─ Webhook triggered
     │                                         ├─ Sends PIN to receiver
     │                                         └─ Notifies agent
     │                                         
     │   7. Poll /api/transfers/{id}/status │
     │◄─────────────────────────────────────►│
     │                                         │
     │   8. Status: PAYMENT_LOCKED           │
     │       "Awaiting receiver verification"│
     │                                         │
     └─ Transfer now in agent's queue
```

---

## Part 3: Implementation Strategy

### Phase 1: Enable Standard Lightning Payments

**Timeframe**: Immediate (use existing APIs)

**What Blink Users Can Do Now**:
1. Get SatsRemit transfer quote
2. Create transfer → receive Lightning invoice
3. Pay invoice from Blink Wallet
4. Track payment status

**Implementation**:
```typescript
// Blink Wallet App (React Native/Web)

// 1. Fetch quote
const getQuote = async (amountZAR: number) => {
  const response = await fetch('https://api.satsremit.com/api/transfers/quote', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ amount_zar: amountZAR })
  });
  return response.json();
};

// 2. Create transfer
const createTransfer = async (receiver, amountZAR) => {
  const response = await fetch('https://api.satsremit.com/api/transfers', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      sender_phone: blinkUser.phone,  // Pre-filled from Blink
      receiver_phone: receiver.phone,
      receiver_name: receiver.name,
      receiver_location: receiver.location,
      amount_zar: amountZAR
    })
  });
  const transfer = await response.json();
  
  // 3. Present Lightning invoice to user
  return {
    invoice: transfer.invoice_request,  // BOLT11 invoice
    transferId: transfer.transfer_id,
    reference: transfer.reference
  };
};

// 4. Deep link to pay invoice in Blink
const payInvoice = (invoice: string) => {
  window.location.href = `lightning://${invoice}`;
  // Or for deep linking: blink://pay?invoice=${invoice}
};

// 5. Poll for status after payment
const pollStatus = async (transferId: string) => {
  while (true) {
    const response = await fetch(
      `https://api.satsremit.com/api/transfers/${transferId}/status`
    );
    const status = await response.json();
    
    if (status.state === 'PAYMENT_LOCKED') {
      showMessage('Payment received! Receiver will get cash soon.');
      break;
    }
    
    await new Promise(resolve => setTimeout(resolve, 5000));  // Poll every 5s
  }
};
```

### Phase 2: Blink-to-Blink Smart Routing (Zero Fees)

**Timeframe**: 2-3 weeks (requires Blink API integration)

**Advantage**: If both Blink Wallet user and SatsRemit operator use Blink, transfers are zero-fee

**Implementation Strategy**:

```graphql
# Blink GraphQL API - Check if recipient is Blink user

query GetBlinkUser($phoneNumber: String!) {
  user(phoneNumber: $phoneNumber) {
    id
    wallets {
      id
      currency
    }
  }
}

# If SatsRemit agent has Blink wallet:
# Send via Blink intraledger → Zero fees
# Otherwise: Use Lightning → Normal routing fees

mutation SendBlinkTransfer($recipientWalletId: String!, $amountSats: Int!) {
  mutationSendDefaultWallet {
    sendBtcWallet(
      walletId: $recipientWalletId
      amount: $amountSats
    ) {
      success
      transaction {
        id
        status
      }
    }
  }
}
```

**SatsRemit Changes Needed**:
```python
# src/services/lnd.py - add Blink routing option

async def send_payment_with_routing(amount_sats, recipient, prefer_blink=True):
    """
    Send payment with smart routing:
    1. Check if recipient has Blink wallet
    2. If yes: Use Blink API for zero-fee transfer
    3. If no: Use Lightning routing
    """
    
    # Check if agent has Blink wallet
    agent_blink_wallet = await check_blink_wallet(recipient.phone)
    
    if agent_blink_wallet and prefer_blink:
        # Use Blink API (zero fees)
        return await blink_api.send_intraledger(
            wallet_id=agent_blink_wallet.id,
            amount_sats=amount_sats,
            memo="SatsRemit Settlement"
        )
    else:
        # Use Lightning (routing fees apply)
        return await send_lightning_payment(amount_sats, recipient)
```

### Phase 3: Embedded Payment Widget in Blink App

**Timeframe**: 4-6 weeks (requires Blink partnership)

**Concept**: "Send Money to Zimbabwe" feature native in Blink Wallet

**Implementation**:
```typescript
// React component for Blink App

import SatsRemitWidget from 'satsremit-sdk';

export const SendToZimbabweTab = () => {
  const { blinkUser } = useBlinkAuth();

  return (
    <SatsRemitWidget
      senderPhone={blinkUser.phone}
      senderCurrency="ZAR"  // Auto-detect from Blink account
      receiverCountry="ZW"
      onInvoiceGenerated={(invoice) => {
        // Show Blink payment screen
        return <BlinkPaymentModal invoice={invoice} />;
      }}
      onSettled={() => {
        navigate('/transfers/settled');
      }}
    />
  );
};
```

### Phase 4: Webhook Integration (Payment Confirmation)

**Timeframe**: 1-2 weeks (in progress)

**Current Status**: 🟡 Partially implemented

**What's Needed**:
```python
# src/api/routes/webhooks.py - LND invoice settled webhook

@router.post("/webhooks/lnd/invoice-settled")
async def handle_invoice_settled(
    event: LNDInvoiceSettledWebhook,
    db: Session = Depends(get_db),
    transfer_service: TransferService = Depends(get_transfer_service),
    notification_service: NotificationService = Depends(get_notification_service)
):
    """
    Handle LND webhook when invoice is fully paid
    This is called by LND when: rtl-config: "POST https://api.satsremit.com/api/webhooks/lnd/invoice-settled"
    """
    
    # 1. Find transfer by invoice hash
    transfer = await transfer_service.get_transfer_by_invoice(event.invoice_hash)
    
    if not transfer:
        return {"error": "Transfer not found"}
    
    # 2. Update transfer state: INVOICE_GENERATED → PAYMENT_LOCKED
    await transfer_service.mark_payment_locked(transfer.id, event.settled_at)
    
    # 3. Generate 4-digit PIN for receiver verification
    pin = generate_pin()
    await transfer_service.set_receiver_pin(transfer.id, pin)
    
    # 4. Send WhatsApp notification to receiver
    await notification_service.send_message(
        phone=transfer.receiver_phone,
        message=f"💰 Incoming remittance! Your PIN: {pin}. Amount: {transfer.amount_zar} ZAR"
    )
    
    # 5. Notify agent of pending payout
    await notification_service.notify_agent_payout_pending(
        agent_id=transfer.agent_id,
        transfer=transfer
    )
    
    # 6. Return acknowledgment to LND
    return {
        "status": "processed",
        "transfer_id": transfer.id,
        "state_changed_to": "PAYMENT_LOCKED"
    }
```

**Blink Webhook Support** (for future):
```python
# If Blink processes payment, they send webhook to SatsRemit

@router.post("/webhooks/blink/payment-settled")
async def handle_blink_payment(
    event: BlinkPaymentWebhook,  # From Blink API
    db: Session = Depends(get_db)
):
    """
    Blink sends webhook when payment routed through Lightning
    Allows real-time payment confirmation
    """
    
    # Find transfer by Blink transaction ID or invoice hash
    transfer = await transfer_service.get_transfer_by_invoice(event.invoice_hash)
    
    # Same process as LND webhook
    return await mark_payment_received(transfer)
```

---

## Part 4: Current API Endpoints (Production Ready)

### Public Endpoints (No Auth)

```bash
# 1. Get exchange rate
GET /api/rates/zar-btc
Response: { "pair": "ZAR_BTC", "rate": "120000.00" }

# 2. Get quote (no commitment)
POST /api/transfers/quote
Body: { "amount_zar": 250.00 }
Response: { 
  "amount_sats": 208333,
  "platform_fee_zar": 1.25,
  "agent_commission_zar": 1.25,
  "receiver_gets_zar": 247.50
}

# 3. Create transfer (generates invoice)
POST /api/transfers
Body: {
  "sender_phone": "+27712345678",
  "receiver_phone": "+263782123456",
  "receiver_name": "John Receiver",
  "receiver_location": "ZWE_HRR",
  "amount_zar": 250.00
}
Response: {
  "transfer_id": "550e8400-e29b-41d4-a716-446655440000",
  "invoice_request": "lnbc2500000n1p0abcdx...",
  "reference": "20260409141530A1B2C3D4E5"
}

# 4. Check transfer status
GET /api/transfers/{transfer_id}/status
Response: {
  "state": "INVOICE_GENERATED",
  "receiver_phone_verified": false,
  "agent_verified": false
}

# 5. List agent locations
GET /api/locations
Response: [
  { "code": "ZWE_HRR", "name": "Harare", "agent_name": "John Agent" }
]
```

---

## Part 5: Blink-Specific Integration Endpoints

### New Endpoints Needed (To Be Implemented)

```bash
# 1. Check Blink-to-Blink routing eligibility
GET /api/integrations/blink/check-route?sender_id={blink_user_id}&amount_zar={amount}

Response: {
  "can_use_blink_routing": true,
  "blink_wallet_id": "agent-blink-wallet-123",
  "fees": {
    "blink_to_blink": 0,           # Zero fees
    "lightning_routing": 0.02,      # Only charged if not available
    "platform_fee": 1.25,           # Still applies
    "total_zar": 1.25
  }
}

# 2. Create transfer with Blink sender ID (optional, for tracking)
POST /api/transfers/with-blink-sender
Body: {
  "blink_wallet_id": "wallet-123",
  "blink_user_id": "user-123",
  "receiver_phone": "+263782123456",
  "receiver_name": "John",
  "receiver_location": "ZWE_HRR",
  "amount_zar": 250.00
}

# 3. Blink payment webhook (from Blink server)
POST /api/webhooks/blink/payment-settled
Headers: { "X-Blink-Signature": "..." }
Body: {
  "event": "payment.settled",
  "invoice_hash": "abc123...",
  "transaction_id": "blink-tx-123",
  "timestamp": "2026-04-09T14:30:00Z",
  "amount_sats": 208333
}
```

---

## Part 6: Blink Wallet User Journey

### Happy Path: SA User → ZW Agent → Cash Payout

```
Step 1: DISCOVERY
  User opens Blink Wallet
  → Taps "Send Money" 
  → Sees "Remit to Zimbabwe" option
  → Clicks to view SatsRemit

Step 2: QUOTE
  SatsRemit widget shows:
  - Send: 250 ZAR
  - Fees: 2.50 ZAR (platform + agent)
  - Receiver gets: 247.50 ZAR
  - Rate: 1 BTC = 120,000 ZAR
  - Equivalent: 206,250 sats

Step 3: DETAILS
  User enters:
  - Receiver phone: +263782123456
  - Receiver name: John Receiver
  - Receiver location: Harare (auto-matched to agent)

Step 4: PAYMENT
  SatsRemit generates Lightning invoice
  → Shows LNURL/QR code
  → User clicks "Pay from Blink"
  → Deep link: lightning://lnbc2500000n1p0abcdx...
  → Blink payment screen opens
  → User confirms payment
  → Blink sends payment through Lightning

Step 5: CONFIRMATION
  LND receives payment ✅
  → SatsRemit webhook triggered
  → Transfer marked PAYMENT_LOCKED
  → PIN generated: 1234
  → WhatsApp to receiver: "PIN: 1234"
  → WhatsApp to agent: "Pending payout: 250 ZAR to John"

Step 6: AGENT VERIFICATION
  Zimbabwe agent:
  - Logs into SatsRemit agent app
  - Sees pending payout
  - Contacts receiver via phone
  - Verifies phone number
  - Receives PIN (1234) from user
  - Enters PIN in app ✅
  - App confirms: "Ready to pay"

Step 7: CASH PAYOUT
  Agent counts cash: 250 ZAR
  Hands to receiver
  Types confirmation note: "Handed to John, confirmed 3pm"
  Confirms in app ✅

Step 8: SETTLEMENT
  Weekly settlement runs (Sunday):
  - Agent balance: 250 ZAR deducted
  - Agent commission: 1.25 ZAR (in sats) credited
  - Settlement due: Monday
  
  Agent receives payment:
  - Via Blink: Zero fees, instant
  - Via bank: Standard bank fees
  - User confirms settlement received in app

Step 9: COMPLETE
  User sees in Blink Wallet:
  - "Remit to Jacob - SETTLED"
  - Amount: 206,250 sats
  - Date: April 9, 2026
  - Status: ✅ Complete
```

---

## Part 7: Implementation Roadmap

### Timeline & Priorities

| Phase | Task | Effort | Timeline | Status |
|-------|------|--------|----------|--------|
| **P0** | Webhook implementation (LND) | 4 hrs | This week | 🟡 In progress |
| **P0** | Blink deep linking support | 2 hrs | This week | ⏳ Not started |
| **P1** | Admin login endpoint | 2 hrs | Next week | ⏳ Not started |
| **P1** | Background task workers | 6 hrs | Next 2 wks | ⏳ Not started |
| **P2** | Blink routing check endpoint | 4 hrs | 2-3 wks | ⏳ Not started |
| **P2** | Blink wallet detection | 4 hrs | 2-3 wks | ⏳ Not started |
| **P3** | Embedded widget (Blink partnership) | 20 hrs | 4-6 wks | ⏳ Not started |
| **P3** | Blink-to-Blink routing via API | 8 hrs | 4-6 wks | ⏳ Not started |

### Implementation Checklist

- [ ] **Week 1**: Webhooks + Deep linking
  - [ ] Complete LND webhook handler (`src/api/routes/webhooks.py`)
  - [ ] Add Lightning URI support (lnbc://, lightning://)
  - [ ] Test with Blink payment flow

- [ ] **Week 2**: Admin features + Background tasks
  - [ ] Admin login endpoint
  - [ ] Celery workers (verification timeout, settlement)
  - [ ] Database migrations (Alembic)

- [ ] **Week 3-4**: Blink smart routing
  - [ ] Add Blink API check endpoints
  - [ ] Implement wallet detection
  - [ ] Smart routing logic (Blink vs Lightning)

- [ ] **Week 5-6**: Blink partnership
  - [ ] Negotiate integration with Blink
  - [ ] Build embedded widget
  - [ ] UAT testing with Blink team

---

## Part 8: Code Examples for Blink Developers

### TypeScript/React Integration

```typescript
// blink-wallet/src/components/RemitToZimbabwe.tsx

import React, { useState } from 'react';
import { useBlinkAuth } from '@blink/auth';
import { openURL } from '@blink/utils';

export const RemitToZimbabwe = () => {
  const { user } = useBlinkAuth();
  const [amount, setAmount] = useState('250');
  const [receiver, setReceiver] = useState('');
  const [status, setStatus] = useState<'idle' | 'loading' | 'paying' | 'confirming'>('idle');

  const handleRemit = async () => {
    setStatus('loading');

    // 1. Get quote
    const quoteRes = await fetch('https://api.satsremit.com/api/transfers/quote', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ amount_zar: parseFloat(amount) })
    });
    const quote = await quoteRes.json();

    // 2. Create transfer
    const transferRes = await fetch('https://api.satsremit.com/api/transfers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sender_phone: user.phone,
        receiver_phone: receiver,
        receiver_name: receiver.split(' ')[0],
        receiver_location: 'ZWE_HRR',
        amount_zar: parseFloat(amount)
      })
    });
    const transfer = await transferRes.json();

    // 3. Redirect to Blink payment
    setStatus('paying');
    openURL(`lightning://${transfer.invoice_request}`);

    // 4. Poll for payment confirmation
    const pollInterval = setInterval(async () => {
      const statusRes = await fetch(
        `https://api.satsremit.com/api/transfers/${transfer.transfer_id}/status`
      );
      const statusData = await statusRes.json();

      if (statusData.state === 'PAYMENT_LOCKED') {
        clearInterval(pollInterval);
        setStatus('confirming');
        setTimeout(() => {
          setStatus('idle');
          alert('✅ Payment sent! Receiver will get cash soon.');
        }, 2000);
      }
    }, 5000);
  };

  return (
    <div className="remit-form">
      <h2>Send Money to Zimbabwe</h2>
      <input
        type="number"
        placeholder="Amount (ZAR)"
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
      />
      <input
        type="tel"
        placeholder="Receiver phone (+263...)"
        value={receiver}
        onChange={(e) => setReceiver(e.target.value)}
      />
      <button onClick={handleRemit} disabled={status !== 'idle'}>
        {status === 'idle' ? 'Send via Lightning' : `${status}...`}
      </button>
    </div>
  );
};
```

### Python/FastAPI Integration

```python
# satsremit-api/src/integrations/blink.py

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from src.core.dependencies import get_db
import httpx

router = APIRouter(prefix="/integrations/blink", tags=["blink"])

BLINK_API_BASE = "https://api.blink.sv/graphql"

async def check_blink_wallet(phone: str, blink_api_key: str) -> dict:
    """
    Query Blink API to check if phone number has a wallet
    """
    query = """
    query GetUserByPhone($phone: String!) {
      user(phone: $phone) {
        id
        wallets {
          id
          currency
          balance
        }
      }
    }
    """
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            BLINK_API_BASE,
            json={"query": query, "variables": {"phone": phone}},
            headers={"Authorization": f"Bearer {blink_api_key}"}
        )
    
    return response.json()

@router.get("/check-route")
async def check_blink_routing(
    amount_zar: float,
    db: Session = Depends(get_db)
):
    """
    Check if transfer can use Blink's zero-fee routing
    """
    from src.services.rate import RateService
    
    rate_service = RateService(db)
    rate = rate_service.get_rate()
    amount_sats = int(amount_zar / float(rate.zar_per_btc) * 1_0000_000)
    
    # Dummy check - real implementation would check agent's Blink wallet
    agent_has_blink = True
    
    return {
        "can_use_blink_routing": agent_has_blink,
        "blink_wallet_id": "agent-wallet-123" if agent_has_blink else None,
        "fees": {
            "blink_to_blink": 0 if agent_has_blink else None,
            "lightning_routing": 0.02 if not agent_has_blink else None,
            "platform_fee": amount_zar * 0.005
        }
    }

@router.post("/send-via-blink")
async def send_payment_via_blink(
    recipient_blink_id: str,
    amount_sats: int,
    memo: str = "SatsRemit Settlement"
):
    """
    Send payment directly via Blink (zero fees for Blink-to-Blink)
    """
    mutation = """
    mutation SendBitcoin($walletId: String!, $amount: Int!, $memo: String) {
      mutationSendBitcoin(walletId: $walletId, amount: $amount, memo: $memo) {
        status
        transaction { id }
      }
    }
    """
    
    # Call Blink API (requires API key)
    async with httpx.AsyncClient() as client:
        response = await client.post(
            BLINK_API_BASE,
            json={
                "query": mutation,
                "variables": {
                    "walletId": recipient_blink_id,
                    "amount": amount_sats,
                    "memo": memo
                }
            }
        )
    
    return response.json()
```

---

## Part 9: Challenges & Solutions

### Challenge 1: Lightning Invoice Expiry

**Problem**: Lightning invoices expire (typically 1 hour)  
**Solution**:
- Set longer expiry in LND config (e.g., 10 hours for remittances)
- If Blink user doesn't pay within 1 hour, regenerate new invoice
- Store invoice hash in database for payment tracking

```python
# src/services/lnd.py

async def create_invoice(amount_sats, memo, expiry_seconds=36000):  # 10 hours
    """Create LND invoice with longer expiry for remittances"""
    response = stub.AddInvoice(
        lnrpc.Invoice(
            value_msat=amount_sats * 1000,
            memo=memo,
            expiry=expiry_seconds,  # 10 hours instead of default 1 hour
            private=True  # Require private channels for privacy
        ),
        timeout=10
    )
    return response
```

### Challenge 2: Cross-Border Regulatory Compliance

**Problem**: Remittances are regulated; must track sender/receiver KYC  
**Solution**:
- Implement KYC verification for senders >threshold (e.g., >5,000 ZAR)
- Store encrypted sender/receiver data per regulation
- Document transaction chain for audit

```python
# src/models/transfer.py

class Transfer(Base):
    __tablename__ = "transfers"
    
    # KYC fields
    sender_phone = Column(String, nullable=False, index=True)
    receiver_phone = Column(String, nullable=False, index=True)
    receiver_name = Column(String, nullable=False)
    
    # Compliance
    kyc_verified = Column(Boolean, default=False)
    kyc_check_date = Column(DateTime, nullable=True)
    compliance_notes = Column(String, nullable=True)
    
    # Audit trail
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    settled_at = Column(DateTime, nullable=True)
```

### Challenge 3: Exchange Rate Fluctuations

**Problem**: BTC price volatile; quoted rate may change before payment  
**Solution**:
- Lock rate when invoice issued (not when quoted)
- Add 0.5% buffer to absorb small fluctuations
- Refund difference if sender overpays

```python
# src/services/transfer.py

async def create_transfer(
    sender_phone: str,
    receiver_phone: str,
    amount_zar_requested: float,
    db: Session
) -> Transfer:
    """
    Create transfer with rate locking
    """
    # Get current rate
    current_rate = await self.rate_service.get_rate()
    
    # Lock rate with 0.5% buffer
    locked_rate = current_rate * 1.005  # Add 0.5% safety
    
    # Calculate exact amount in sats
    amount_sats = int((amount_zar_requested / locked_rate) * 1_0000_000)
    
    transfer = Transfer(
        sender_phone=sender_phone,
        receiver_phone=receiver_phone,
        amount_zar=amount_zar_requested,
        amount_sats=amount_sats,
        rate_zar_per_btc=locked_rate,
        state="INITIATED"
    )
    
    db.add(transfer)
    db.commit()
    
    return transfer
```

### Challenge 4: Blink Wallet Deep Linking

**Problem**: Different OSes handle deep links differently  
**Solution**:
- Use universal links (iOS) + app links (Android)
- Fallback to web view if app not installed
- Store invoice in SatsRemit session if link fails

```typescript
// blink-wallet/src/utils/deeplinking.ts

export const payWithBlink = async (invoice: string) => {
  const isIOS = Platform.OS === 'ios';
  const isAndroid = Platform.OS === 'android';

  if (isIOS) {
    // Use universal link for iOS
    return openURL(`https://blink.sv/pay?invoice=${invoice}`);
  } else if (isAndroid) {
    // Use app link for Android
    return openURL(`blink://pay?invoice=${invoice}`);
  } else {
    // Web: open payment modal
    return showPaymentModal(invoice);
  }
};
```

---

## Part 10: Success Metrics

### KPIs to Track

| Metric | Target | Timeline |
|--------|--------|----------|
| **Transaction Volume** | 100 transfers/week | Month 1 |
| **Blink Wallet Integration Usage** | 20% of transfers | Month 2 |
| **Zero-Fee Routing Adoption** | 50% of settlements | Month 3 |
| **Average Tx Time** | <5 minutes (payment→verification) | Ongoing |
| **Settlement Speed** | Weekly payout | Ongoing |
| **User Satisfaction** | >4.5/5 stars | Ongoing |
| **Agent Retention** | >90% | Ongoing |

### Monitoring & Analytics

```python
# src/monitoring/metrics.py

class RemittanceMetrics:
    
    @staticmethod
    async def track_transfer(transfer: Transfer):
        """Track transfer through pipeline"""
        metrics.counter(
            "transfer.created",
            labels={"location": transfer.agent_location}
        )
    
    @staticmethod
    async def track_payment_received(transfer: Transfer):
        """Track payment success"""
        duration = (transfer.payment_received_at - transfer.created_at).total_seconds()
        metrics.histogram(
            "transfer.payment_duration_seconds",
            value=duration
        )
    
    @staticmethod
    async def track_blink_transfer(transfer: Transfer):
        """Track Blink routing usage"""
        if transfer.used_blink_routing:
            metrics.counter("transfer.blink_routing_used")
            metrics.gauge("transfer.fees_saved_zar", transfer.saved_fees)
```

---

## Next Steps

1. **This Week**:
   - [ ] Complete webhook implementation
   - [ ] Add Lightning deep linking support
   - [ ] Test full flow with Blink wallet

2. **Next Week**:
   - [ ] Deploy background task workers
   - [ ] Add admin authentication
   - [ ] Implement rate locking

3. **Following Week**:
   - [ ] Reach out to Blink team for partnership
   - [ ] Design embedded widget
   - [ ] Implement Blink API check endpoints

4. **Month 2**:
   - [ ] Launch Blink integration
   - [ ] Begin zero-fee routing
   - [ ] Scale to 100+ transfers/week

---

## Resources

- **Blink API Docs**: https://dev.blink.sv/
- **Blink GitHub**: https://github.com/blinkbitcoin
- **Blink Community**: https://chat.blink.sv/ (Mattermost)
- **Lightning Network Docs**: https://docs.lightning.engineering/
- **LNURL Spec**: https://github.com/fiatjaf/lnurl-rfc

---

**Status**: Integration plan complete. Ready for Phase 1 implementation (webhooks + deep linking).  
**Next Review**: After webhook implementation is complete.
