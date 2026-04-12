# SatsRemit: Bitcoin Lightning Remittance Platform

A secure, efficient Bitcoin Lightning Network remittance platform enabling users in South Africa to send ZAR to Zimbabwe via sats, with cash payouts verified by local agents.

**Status**: Phase 1 MVP - In Development

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Docker & Docker Compose
- PostgreSQL (via Docker)
- Redis (via Docker)

### Setup

1. **Clone & Install**
```bash
cd satsremit
pip install -r requirements.txt
```

2. **Start Services**
```bash
make docker-up
```

3. **Initialize Database**
```bash
make db-init
```

4. **Run Development Server**
```bash
make dev
```

Server will be available at `http://localhost:8000`
- API Docs: `http://localhost:8000/api/docs`
- ReDoc: `http://localhost:8000/api/redoc`

## �️ VPS Deployment

**Current Production Setup** (Updated April 12, 2026):
- **Host**: vm-1327.lnvps.cloud
- **Bitcoin Core**: v29.0.0 (testnet4)
- **LND**: 0.19.0-beta (testnet4)
- **App**: Running on Uvicorn (port 8000, 2 workers)
- **Status**: ✓ All systems operational

📖 See [VPS_CURRENT_SETUP.md](VPS_CURRENT_SETUP.md) for:
- Current service versions and status
- Quick command reference (bc, ln aliases)
- Network configuration details
- Troubleshooting guide

🚀 Setup guide: [VPS_SETUP.md](VPS_SETUP.md)  
⚙️ Production config: [SATSREMIT_PRODUCTION_CONFIG.md](SATSREMIT_PRODUCTION_CONFIG.md)

## �📁 Project Structure

```
satsremit/
├── src/
│   ├── api/
│   │   └── routes/          # API endpoint implementations
│   ├── core/
│   │   └── config.py        # Configuration management
│   ├── db/
│   │   └── database.py      # Database connection
│   ├── models/
│   │   ├── models.py        # SQLAlchemy ORM models
│   │   └── schemas.py       # Pydantic validation schemas
│   ├── services/            # Business logic services
│   ├── tasks/               # Celery async tasks
│   ├── utils/               # Utility functions
│   └── main.py              # FastAPI application
├── tests/                   # Test suite
├── config/                  # Configuration files
├── scripts/                 # Setup & migration scripts
├── docs/                    # Documentation
├── docker-compose.yml       # Local development environment
├── requirements.txt         # Python dependencies
├── Makefile                 # Development commands
└── REFINED_PLAN.md         # Detailed architecture & implementation plan
```

## 🔧 Configuration

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Edit `.env` with:
- Database credentials (auto-set for Docker)
- LND (Lightning Network Daemon) connection details
- Bitcoin RPC credentials
- Africa's Talking API credentials
- JWT secrets

## 📊 Database Schema

### Core Tables
- **transfers** - Main transfer records with state machine
- **agents** - Cash payout operators
- **settlements** - Weekly settlement records
- **invoice_holds** - Secure preimage storage
- **transfer_history** - Audit trail
- **rate_cache** - Exchange rate cache

See [REFINED_PLAN.md](REFINED_PLAN.md#8-database-schema-simplified) for full schema details.

## 📡 API Endpoints

### Public API
```
POST   /api/transfers              - Create new transfer
GET    /api/transfers/{id}         - Get transfer status
GET    /api/agent/locations        - List available agents
GET    /health                     - Health check
```

### Agent API (Authenticated)
```
POST   /api/agent/auth/login                      - Agent login
GET    /api/agent/balance                         - Check balance
GET    /api/agent/transfers                       - Pending transfers
POST   /api/agent/transfers/{id}/verify           - Verify receiver
POST   /api/agent/transfers/{id}/confirm-payout   - Confirm payout
GET    /api/agent/settlements                     - Settlement records
POST   /api/agent/settlement/{id}/confirm         - Confirm settlement
```

### Admin API (Admin Only)
```
POST   /api/admin/agent/add                      - Create agent
GET    /api/admin/agent/{id}/balance             - Agent balance
POST   /api/admin/agent/{id}/advance             - Record cash advance
GET    /api/admin/transfers                      - List all transfers
GET    /api/admin/volume                         - Platform metrics
```

### Webhooks
```
POST   /api/webhooks/lnd/invoice-settled    - LND invoice settled
POST   /api/webhooks/lnd/invoice-expired    - LND invoice expired
```

Full API specification: See [REFINED_PLAN.md](REFINED_PLAN.md#7-api-endpoints-refined)

## 🔄 Transfer State Machine

```
INITIATED
  ↓ (validate → generate invoice)
INVOICE_GENERATED
  ↓ (user pays Lightning)
PAYMENT_LOCKED
  ↓ (agent + receiver verify)
RECEIVER_VERIFIED
  ↓ (agent pays cash)
PAYOUT_EXECUTED
  ↓ (auto-settle)
SETTLED
  ↓ (complete)
FINAL

FAILURE PATHS:
INITIATED → [insufficient funds] → REFUNDED
INVOICE_GENERATED → [invoice expires] → REFUNDED
PAYMENT_LOCKED → [verification fails] → REFUNDED
```

See [REFINED_PLAN.md](REFINED_PLAN.md#3-transfer-state-machine-new) for detailed state machine.

## 💰 Transaction Flow

1. **SA Sender** creates transfer (amount ZAR, receiver phone, location)
2. **Platform** validates agent has sufficient cash
3. **Platform** generates hold invoice + transfer reference (REF-XXXXX)
4. **SA Sender** pays Lightning invoice (sats locked in LND)
5. **Platform** notifies receiver (PIN) + agent (alert)
6. **Agent** verifies receiver (PIN + phone dual verification)
7. **Agent** pays cash to receiver
8. **Agent** confirms payout in system
9. **Platform** settles invoice (sats to platform)
10. **Agent** earns 0.5% commission
11. **Weekly**: Agent credits platform with ZAR collected
12. **Platform**: Records setoff + returns sats to pool

## 🔐 Security

| Feature | Implementation |
|---------|-----------------|
| Hold Invoices | LND pre-signed invoices, sats locked until verification |
| Dual Verification | Agent enters receiver PIN + confirms phone match |
| Agent Credit Check | Sender cannot send if agent balance insufficient |
| Rate Locking | ZAR/BTC rate locked at invoice generation (15 min TTL) |
| Webhook Signatures | HMAC-SHA256 verification on LND callbacks |
| JWT Tokens | Stateless authentication for agent + admin |
| Encrypted Preimages | Invoice preimages stored encrypted, decrypted only for settlement |

See [REFINED_PLAN.md](REFINED_PLAN.md#6-security--compliance) for security details.

## 📈 Development Workflow

### Testing
```bash
make test              # Run all tests
make test tests/api/ -v  # Run specific test file
```

### Code Quality
```bash
make lint              # Check code quality
make format            # Auto-format code
make clean             # Clean cache files
```

### Database
```bash
make db-init          # Create tables
make db-drop          # Drop all tables (test only)
make db-shell         # Open PostgreSQL shell
```

### Docker
```bash
make docker-up        # Start services
make docker-down      # Stop services
make docker-logs      # View logs
```

## 🎯 Phase 1 MVP Goals

- ✅ Single agent manual operations
- ✅ Testnet Bitcoin/LND setup
- ✅ Hold invoices + basic webhooks
- ✅ Manual weekly settlements
- ⏳ No KYC (low-volume testing phase)
- ⏳ Basic notifications (SMS/WhatsApp)

## 📋 Next Steps

1. **Implement transfer creation** (`POST /api/transfers`)
2. **Implement transfer status** (`GET /api/transfers/{id}`)
3. **Implement agent login** (`POST /api/agent/auth/login`)
4. **Implement transfer verification** (`POST /api/agent/transfers/{id}/verify`)
5. **Implement LND integration** (invoice creation, webhooks)
6. **Implement notification service** (Twilio WhatsApp/SMS)
7. **Add comprehensive tests**

## 💡 Contributing

1. Follow the project structure
2. Use type hints (Python 3.10+ match statements where appropriate)
3. Write tests for new features
4. Run `make lint && make format` before committing

## 📚 Documentation

- [REFINED_PLAN.md](REFINED_PLAN.md) - Full architecture & implementation details
- [Africa's Talking Setup Guide](docs/AFRICAS_TALKING_SETUP.md) - SMS notification service setup
- [API Documentation](http://localhost:8000/api/docs) - Interactive API docs (when running)

## ⚠️ Important Notes

**Phase 1 Limitations:**
- Single agent only
- Manual settlement processes
- Testnet Bitcoin (low value)
- No KYC/AML verification
- Basic error handling

**Security Considerations:**
- Keep `.env` secrets secure
- Encrypt preimages in production
- Use HTTPS in production
- Implement rate limiting
- Add OFAC screening (Phase 2)

## 📞 Support

For issues or questions:
1. Check [REFINED_PLAN.md](REFINED_PLAN.md) for architecture details
2. Review the API documentation at `/api/docs`
3. Check test files for usage examples

## 📄 License

MIT License - See LICENSE file for details

---

**Version**: 0.1.0 (Phase 1 MVP)  
**Last Updated**: April 6, 2026
