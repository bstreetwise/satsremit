# SatsRemit: South Africa → Zimbabwe Lightning Remittance Platform
## Refined Architecture & Implementation Plan

---

## 1. Executive Summary (Refined)

**SatsRemit** is a Bitcoin Lightning Network remittance platform enabling users in South Africa to send ZAR to Zimbabwe via sats, with cash payouts verified by local agents. The platform uses hold invoices to lock funds, enforces dual verification for security, and manages agent liquidity through weekly settlements.

**Key Improvement**: Phase 1 focuses on single-agent MVP with manual processes; Phase 2 scales to multi-agent with automation.

---

## 2. System Architecture (Refined)

### 2.1 Technology Stack

| Component | Technology | Cost | Notes |
|-----------|------------|------|-------|
| VPS Provider | LNVPS (London, Medium) | €13.80/mo | Single instance Phase 1; split Phase 2 |
| Bitcoin Node | bitcoind (pruned, signet → mainnet) | Included | Run on same VPS Phase 1 |
| Lightning Node | LND v0.18.4 | Included | Hold invoices + webhooks support |
| Database | PostgreSQL (self-hosted) | Free | Basic replication Phase 2 |
| Backend | Python FastAPI | Free | Async, extensible |
| Task Queue | Celery + Redis | Free | For async payout processing |
| Notifications | WhatsApp Business API | $0/mo | WhatsApp: unlimited free messages to opted-in users |
| KYC/AML | OpenNode/Coinbase Commerce | $0-100/mo | Phase 2+ (risk-based) |
| Domain | Custom + SSL | ~$1/mo | Let's Encrypt (free cert) |
| **Total Phase 1** | | **~$30-40/mo** | **Major cost reduction from Twilio** |
| **Phase 2 (+)** | Replication, KYC | ~$100-150/mo | Added reliability + compliance |

### 2.2 Deployment Architecture

```
PHASE 1 (MVP - Single VPS)
┌─────────────────────────────────────────────────────┐
│  LNVPS (London, €13.80/mo)                          │
│  ┌────────────────┐  ┌────────────────────────────┐ │
│  │  bitcoind      │  │  LND (Lightning Node)      │ │
│  │  (signet/      │◀─│  - Hold invoices           │ │
│  │   mainnet)     │  │  - Webhook callbacks       │ │
│  └────────────────┘  └────────┬───────────────────┘ │
│                               │                      │
│  ┌────────────────────────────▼──────────────────┐ │
│  │  FastAPI Backend                             │ │
│  │  - /api/transfers                            │ │
│  │  - /api/agent/*                              │ │
│  │  - /api/admin/*                              │ │
│  │  - /webhooks/lnd                             │ │
│  └────────────┬───────────┬──────────────────────┘ │
│               │           │                        │
│  ┌────────────▼─┐  ┌──────▼──────┐  ┌──────────┐ │
│  │ PostgreSQL   │  │ Redis/Cache │  │ Celery   │ │
│  │ (transfers,  │  │             │  │ (async   │ │
│  │  agents,     │  │             │  │  tasks)  │ │
│  │  balances)   │  │             │  │          │ │
│  └──────────────┘  └─────────────┘  └──────────┘ │
└─────────────────────────────────────────────────────┘

PHASE 2 (Scale - Multi-VPS)
┌──────────────────────────────────┬──────────────────────────────────┐
│  VPS-1: Bitcoin/LND              │  VPS-2: FastAPI + DB Replica     │
│  (Validator)                     │  (Redundancy)                    │
└──────────────────────────────────┴──────────────────────────────────┘
         │                                  │
         └──────────────┬───────────────────┘
                        │
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
     SA Sender      ZW Agent      Admin Dashboard
```

### 2.3 Data Consistency & Finality

**LND Invoice Lifecycle:**
```
GENERATED (sats locked)
    ↓
OPEN (payment possible)
    ↓
SETTLED (payment received, platform owns sats)
    ↓
    [Receiver verified → Agent pays cash]
    ↓
FINAL (invoice closed)
    ↓
[Weekly settlement: ZAR collected, sats returned to platform]
```

---

## 3. Transfer State Machine (NEW)

### 3.1 Transfer States & Transitions

```
┌─────────────┐
│  INITIATED  │  User creates transfer request
└──────┬──────┘
       │ Validate receiver + agent liquidity
       ▼
┌─────────────────────────┐
│ INVOICE_GENERATED       │  Hold invoice created, TTL = 96 hours
│ (sats locked in LND)    │  Sender sees amount + REF-XXXXX
└──────┬──────────────────┘
       │ User pays invoice (Lightning)
       ▼
┌─────────────────────────┐
│ PAYMENT_LOCKED          │  Sats received, marked pending settlement
│ (awaiting verification) │  Receiver notified (PIN via WhatsApp)
└──────┬──────────────────┘
       │ Agent + Receiver verify (PIN + phone)
       ├─ VERIFICATION_FAILED → REFUNDED (sats returned to sender)
       │
       ├─ VERIFICATION_PASSED ↓
┌──────────────────────┐
│ RECEIVER_VERIFIED    │  Agent confirms cash ready to pay
└──────┬───────────────┘
       │ Agent pays cash to receiver
       ▼
┌──────────────────────┐
│ PAYOUT_EXECUTED      │  Agent marks complete in system
└──────┬───────────────┘
       │ Platform auto-settles invoice after 5 min confirmation delay
       ▼
┌──────────────────────┐
│ SETTLED              │  Sats moved to platform balance
│ (commission applied) │  Agent earns 0.5% commission
└──────┬───────────────┘
       │ Weekly settlement
       ▼
┌──────────────────────┐
│ FINAL                │  All accounting complete
└──────────────────────┘

FAILURE PATHS:
- INVOICE_EXPIRED → REFUNDED (after 96 hours)
- VERIFICATION_FAILED → REFUNDED
- AGENT_OFFLINE > 1hr → AUTO_REFUNDED
- AGENT_INSUFFICIENT_FUNDS (caught at INITIATED)
```

### 3.2 State Persistence

| Field | Type | Purpose |
|-------|------|---------|
| `transfer_id` | UUID | Unique identifier |
| `state` | ENUM | Current state above |
| `reference` | VARCHAR(20) | User-visible REF-XXXXX |
| `payment_hash` | VARCHAR(66) | LND invoice hash |
| `invoice_expiry_at` | TIMESTAMP | Hold invoice TTL |
| `verified_at` | TIMESTAMP | Verification completion time |
| `payout_at` | TIMESTAMP | When agent paid cash |
| `settled_at` | TIMESTAMP | When sats settled to platform |
| `receiver_phone_verified` | BOOLEAN | Dual verification flag |
| `agent_verified` | BOOLEAN | Agent confirmed payout |

---

## 4. Currency & Settlement Model (Refined)

### 4.1 Multi-Currency Flow

1. **Sender**: Pays in BTC sats (Lightning)
2. **Platform Rate**: ZAR/BTC quoted at invoice generation time
3. **Agent Receives**: 0.5% commission in **sats** (at settlement time)
   - Agent can hold sats or request conversion to ZAR via weekly payout
4. **Weekly Settlement**:
   - Agent accumulates ZAR cash from payouts
   - Agent pays platform in ZAR (via bank transfer or physical)
   - Platform converts ZAR collected → sats at market rate
   - Net: Platform retains sats, agent gets liquidity

### 4.2 Setoff Process (Detailed)

```
Day 1-7: Transaction Cycle
├─ Sender sends 100 ZAR worth of sats
├─ Agent pays cash to receiver
├─ Agent earns 0.5% commission = 0.5 ZAR worth sats
├─ Repeat (10 weeks)
│
├─ Week 1 Accumulation:
│  - Agent paid out: 1000 ZAR (cash)
│  - Agent earned: 5 ZAR equivalent in sats
│  - Agent balance owed to platform: 1000 ZAR
│
└─ Weekly Settlement (Friday EOD):
   ├─ Agent confirms settlement ready
   ├─ Agent pays platform 1000 ZAR (bank transfer/Pix/cash)
   ├─ Platform receives 1000 ZAR
   ├─ Platform converts 1000 ZAR → ~0.15 BTC sats (example rate)
   ├─ Sats transferred to platform LND wallet
   ├─ Agent commission (5 ZAR in sats) deducted from next week
   └─ Cycle repeats
```

### 4.3 Commission Structure

| Actor | Rate | When Paid | In What |
|-------|------|-----------|---------|
| Platform | 0.5% of transfer | On settlement | Sats |
| Agent | 0.5% of transfer | On settlement | Sats (can convert weekly) |
| Total Fee | 1% | Transparent to sender | Sats |

---

## 5. LND Hold Invoice Management

### 5.1 Invoice Creation & Hold

```python
# Pseudo-code
create_hold_invoice(
    amount_sats=1500,
    description=f"Transfer REF-{reference}",
    hold_expiry_minutes=5760,  # 96 hours
    cltv_delta=40,  # 6.5 hours actual timeout
)
→ Returns: (hash, preimage, payment_request)

# Store preimage in secure vault (NOT database)
# Only release preimage after verification complete
```

### 5.2 Invoice Expiry & Auto-Refund

- **Expiry TTL**: 96 hours from generation
- **Auto-Refund**: If unpaid after expiry → `REFUNDED` state
- **Hold Timeout**: If held >6.5 hours → LND auto-cancels → Check and mark refunded

### 5.3 Settlement Callback

```
LND Webhook → POST /webhooks/lnd/invoice-settled
Payload: {
  "invoice_hash": "...",
  "state": "SETTLED",
  "settled_at": "2026-04-06T14:30:00Z",
  "amount_milli_satoshis": 1500000
}

Handler:
1. Find transfer by invoice_hash
2. Set state → PAYMENT_LOCKED
3. Notify receiver (PIN)
4. Notify agent (alert)
5. Start verification timer (5 min, then escalate)
```

---

## 6. Security & Compliance

### 6.1 Dual Verification Flow

```
Receiver Gets Notification via WhatsApp:
┌────────────────────────────┐
│ SatsRemit Transfer         │
│ PIN: 1234                  │
│ Amount: 100 ZAR            │
│ Ref: REF-XYZ123            │
│ Valid for 5 minutes        │
└────────────────────────────┘

Agent Screen:
┌────────────────────────────┐
│ Payout Verification        │
├────────────────────────────┤
│ Transfer REF-XYZ123        │
│ Amount: 100 ZAR            │
│ Receiver: John Doe         │
├────────────────────────────┤
│ Enter PIN: [_ _ _ _]       │
│ Verify Phone: +263782XXXXX │
│ [Verify] [Cancel]          │
└────────────────────────────┘

Backend Checks:
1. PIN matches → ✓
2. Phone number matches → ✓
3. Agent has sufficient cash balance → ✓
4. Agent verified in system → ✓
→ Transition to RECEIVER_VERIFIED
```

### 6.2 KYC/AML (Phase 2)

| Tier | Sender Verification | Monthly Limit | Notes |
|------|---------------------|---------------|-------|
| Tier 1 | Phone number only | ZAR 5,000 | Phase 1 |
| Tier 2 | Phone + ID scan (selfie) | ZAR 20,000 | Phase 2 |
| Tier 3 | Phone + ID + Proof of Address | ZAR 100,000+ | Phase 2 |

### 6.3 Fraud Prevention

| Check | Implementation |
|-------|-----------------|
| Agent Location Geo-Check | Receiver location within 50km of agent |
| Rate Limiting | Max 5 transfers/hour per sender IP |
| Duplicate Detection | Reject if same receiver + agent + amount within 24h |
| OFAC Screening | Check phone/name against OFAC list (Phase 2) |
| Agent Rating System | Sender can see agent review scores (Phase 2) |

---

## 7. API Endpoints (Refined)

### 7.1 Public API

```
POST /api/transfers
├─ Body: {sender_phone, receiver_phone, receiver_name, amount_zar, location_code}
├─ Response: {transfer_id, reference, invoice, max_sats, rate_zar_per_btc}
├─ Validations:
│  ├─ Sender phone format
│  ├─ Receiver phone format
│  ├─ Amount in range [100-500 ZAR] (Phase 1)
│  └─ Agent has sufficient cash (credit check)
└─ Returns 201 CREATED or 400 BAD_REQUEST

GET /api/transfers/{id}
├─ Response: {id, reference, state, amount_zar, sender_amount_sats, receiver_status}
└─ Public: Only returns non-sensitive fields

GET /api/transfers/{id}/status
├─ Returns: {state, state_description, receiver_received (bool)}
└─ Used by receiver to check if funds arrived

GET /api/agent/locations
├─ Response: [{location_code, location_name, agent_name, agent_phone}]
└─ Lists available agent services

GET /api/health
└─ Returns: {bitcoind_synced, lnd_active, db_connected}
```

### 7.2 Agent API (Auth Required)

```
POST /api/agent/auth/login
├─ Body: {phone, password}
└─ Response: {token, agent_id, agent_name}

GET /api/agent/balance
├─ Response: {cash_balance_zar, commission_balance_sats, payout_date}
└─ Returns agent's current operational balance

GET /api/agent/transfers
├─ Response: [{transfer_id, reference, receiver_name, amount_zar}]
└─ Pending transfers awaiting verification

POST /api/agent/transfers/{id}/verify
├─ Body: {pin, phone_number_verified}
├─ Validations: PIN matches + Phone matches
├─ Response: {verified, instruction}
└─ Transitions transfer → RECEIVER_VERIFIED

POST /api/agent/transfers/{id}/confirm-payout
├─ Body: {} (agent confirming cash paid)
├─ Response: {status, settlement_pending}
└─ Transitions → PAYOUT_EXECUTED; triggers async settlement

GET /api/agent/settlements
├─ Response: [{settlement_id, period, amount_zar, status, due_date}]
└─ Weekly settlement records

POST /api/agent/settlement/{id}/confirm
├─ Body: {payment_method, reference_number}
├─ Response: {confirmed, next_payment_due}
└─ Agent confirms ZAR payment to platform
```

### 7.3 Admin API (Auth Required)

```
POST /api/admin/agent/add
├─ Body: {phone, name, location_code, initial_cash}
└─ Creates new agent

GET /api/admin/agent/{id}/balance
├─ Response: {cash_owed, sats_earned, settlements_pending}
└─ Real-time agent financial status

POST /api/admin/agent/{id}/advance
├─ Body: {zar_amount, note}
├─ Purpose: Record cash advance or corrective entry
└─ Updates agent cash balance

GET /api/admin/transfers
├─ Query params: ?state=SETTLED&date_from=&date_to=
├─ Response: [{transfer_id, reference, amount, state, settlement_date}]
└─ Full audit trail

GET /api/admin/volume
├─ Response: {daily_volume_zar, weekly_volume, monthly_volume, fee_collected}
└─ Analytics dashboard

POST /api/webhooks/lnd/invoice-settled (LND callback)
├─ Body: {invoice_hash, state, settled_at}
└─ Triggered by LND when payment received
```

---

## 8. Database Schema (Simplified)

### 8.1 Core Tables

**transfers**
```sql
id (UUID PRIMARY KEY)
reference (VARCHAR 20 UNIQUE)
sender_phone (VARCHAR 20)
receiver_phone (VARCHAR 20)
receiver_name (VARCHAR 100)
agent_id (FK agents.id)
amount_zar (DECIMAL 10,2)
amount_sats (BIGINT)
rate_zar_per_btc (DECIMAL 15,2)
state (ENUM: INITIATED, INVOICE_GENERATED, PAYMENT_LOCKED, RECEIVER_VERIFIED, PAYOUT_EXECUTED, SETTLED, FINAL, REFUNDED)
invoice_hash (VARCHAR 66 UNIQUE)
payment_request (TEXT)
invoice_expiry_at (TIMESTAMP)
verified_at (TIMESTAMP NULL)
payout_at (TIMESTAMP NULL)
settled_at (TIMESTAMP NULL)
receiver_phone_verified (BOOLEAN DEFAULT FALSE)
agent_verified (BOOLEAN DEFAULT FALSE)
created_at (TIMESTAMP)
updated_at (TIMESTAMP)
```

**agents**
```sql
id (UUID PRIMARY KEY)
phone (VARCHAR 20 UNIQUE)
name (VARCHAR 100)
password_hash (VARCHAR 255)
location_code (VARCHAR 10)
cash_balance_zar (DECIMAL 15,2)
commission_balance_sats (BIGINT)
status (ENUM: ACTIVE, INACTIVE, SUSPENDED)
rating (DECIMAL 3,2 NULL)
created_at (TIMESTAMP)
updated_at (TIMESTAMP)
```

**settlements** (Weekly)
```sql
id (UUID PRIMARY KEY)
agent_id (FK agents.id)
period_start (DATE)
period_end (DATE)
amount_zar_owed (DECIMAL 15,2)
amount_zar_paid (DECIMAL 15,2)
payment_method (VARCHAR 50)
payment_reference (VARCHAR 100)
status (ENUM: PENDING, CONFIRMED, COMPLETED)
completed_at (TIMESTAMP NULL)
created_at (TIMESTAMP)
```

**invoice_holds** (Secret management)
```sql
id (UUID PRIMARY KEY)
invoice_hash (VARCHAR 66 UNIQUE)
preimage (VARCHAR 128 ENCRYPTED) -- Only readable by verified code
transfer_id (FK transfers.id)
expires_at (TIMESTAMP)
created_at (TIMESTAMP)
```

### 8.2 Indexes (for performance)

```sql
CREATE INDEX idx_transfers_agent_state ON transfers(agent_id, state);
CREATE INDEX idx_transfers_state ON transfers(state);
CREATE INDEX idx_transfers_phone ON transfers(receiver_phone);
CREATE INDEX idx_settlements_agent_date ON settlements(agent_id, period_start);
CREATE INDEX idx_invoice_hash ON transfers(invoice_hash);
```

---

## 9. Infrastructure & Deployment

### 9.1 Phase 1: Single VPS Setup

**VPS Specs** (LNVPS Medium, €13.80/mo):
- CPU: 2 vCores
- RAM: 4 GB
- Disk: 100 GB SSD
- OS: Ubuntu 22.04

**Installation Scripts**:
```bash
# 1. System setup
apt update && apt upgrade -y
apt install -y postgresql postgresql-contrib redis-server python3-pip supervisor

# 2. bitcoind (pruned mode)
wget https://bitcoincore.org/bin/.../bitcoin-x.xx.x-x86_64-linux-gnu.tar.gz
tar -xzf bitcoin-*.tar.gz
mkdir -p /data/bitcoin
# bitcoin.conf with pruning=550

# 3. LND v0.18.4
wget https://github.com/lightningnetwork/lnd/releases/download/.../lnd-linux-amd64-v0.18.4.tar.gz
# lnd.conf with hold-invoice enabled

# 4. FastAPI + Celery
pip install fastapi uvicorn psycopg2-binary celery redis httpx python-dotenv

# 5. Systemd services for long-running processes
```

### 9.2 Environment Variables

```bash
# .env
DATABASE_URL=postgresql://satsremit:password@localhost/satsremit
REDIS_URL=redis://localhost:6379/0
LND_REST_URL=https://lnd:8080
LND_MACAROON_PATH=/data/lnd/admin.macaroon
LND_CERT_PATH=/data/lnd/tls.cert
AFRICAS_TALKING_API_KEY=your_api_key
AFRICAS_TALKING_USERNAME=your_username
BITCOIN_NETWORK=testnet  # or mainnet
RATE_BTC_ZAR=SOURCE=coingecko|kraken  # external rate source
```

---

## 10. Risk & Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Agent default on settlement | Loss of ZAR + platform sats | Require security deposit (2-week float) + agent rating system |
| LND crash + invoice loss | Sats locked indefinitely | Encrypted preimage backup + daily backup verification |
| Sender→Receiver fraud | Double-spending via WhatsApp interception | Dual verification + PIN expires in 5 min |
| Agent operates offline | Slow payout + user frustration | Auto-escalate after 1hr; backup agent check-in |
| Rate volatility | 100 ZAR sender gets <90 ZAR value | Lock rate at invoice generation time; show "expires in 15 min" |
| Platform bankruptcy | All sats lost | Keep minimal sats on platform; weekly settlement required |
| Bitcoin network spam | Invoices fail to propagate | Higher fee setting; fallback to custodial node (Phase 2) |

---

## 11. Implementation Roadmap

### Phase 1: MVP (4-6 weeks)
- [ ] Single agent manual operations
- [ ] Testnet Bitcoin/LND
- [ ] Hold invoices + basic webhooks
- [ ] Manual weekly settlements
- [ ] No KYC (accept risk; low volume)
- [ ] Notifications via WhatsApp Business API

### Phase 2: Scaling (6-8 weeks)
- [ ] Multi-agent support
- [ ] Mainnet deployment
- [ ] Automated settlement reconciliation
- [ ] Basic KYC/AML (Phase tier)
- [ ] Agent rating system
- [ ] WhatsApp priority notifications
- [ ] Dual VPS setup for redundancy

### Phase 3: Production Hardening (8-10 weeks)
- [ ] Full KYC/AML (Tier 3)
- [ ] OFAC screening
- [ ] Dispute resolution system
- [ ] Mobile app (Android/iOS)
- [ ] Advanced analytics
- [ ] Liquidity optimization

---

## 12. Success Metrics

| Metric | Target (Phase 1) | Target (Phase 2) |
|--------|------------------|------------------|
| Daily Volume | ZAR 500-1000 | ZAR 5000-10000 |
| Settlement Success Rate | >95% | >99% |
| Agent Uptime | >90% | >99.5% |
| Receiver Satisfaction | >4.0/5 | >4.5/5 |
| Platform Sats Reserve | 0.1 BTC | 1 BTC |
| Monthly Revenue | ~$100-150 | ~$500-1000 |

---

End of Refined Plan
