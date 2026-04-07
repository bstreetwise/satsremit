# SatsRemit Deployment Ready Checklist ✅

**Status**: Phase 5 Infrastructure Deployment - READY FOR EXECUTION
**Last Updated**: Now
**Target**: LNVPS (vm-1327.lnvps.cloud)
**Credentials**: ssh ubuntu@vm-1327.lnvps.cloud with provided password

---

## Pre-Deployment Verification

### ✅ Codebase Complete
- [x] 8 SQLAlchemy ORM models with state machines
- [x] 25+ Pydantic validation schemas
- [x] 28 API endpoints specified (4 route modules)
- [x] Full service layer architecture (NotificationService complete)
- [x] Configuration management system
- [x] Database schema with indexes

### ✅ Deployment Automation Ready
- [x] `scripts/setup_bitcoin_lnd.sh` - Bitcoin v26.0 + LND v0.18.4 installation (200+ lines)
- [x] `scripts/deploy_satsremit.sh` - Backend deployment with stack initialization (180+ lines)
- [x] `scripts/setup_africas_talking.sh` - Notification service configuration
- [x] `init_project.py` - Database schema initialization
- [x] All scripts executed with proper permissions (chmod +x)

### ✅ Documentation Complete
- [x] REFINED_PLAN.md - 12-section refined architecture
- [x] BITCOIN_LND_SETUP.md - Comprehensive Bitcoin/LND guide
- [x] LNVPS_DEPLOYMENT_GUIDE.md - Step-by-step deployment (600+ lines)
- [x] LNVPS_QUICK_REFERENCE.md - Quick lookup commands
- [x] README.md - Project overview
- [x] SETUP_SUMMARY.md - What was built
- [x] AFRICAS_TALKING_SETUP.md - SMS service guide
- [x] MIGRATION_TWILIO_TO_AFRICAS_TALKING.md - Cost analysis

### ✅ Configuration Prepared
- [x] `.env.example` - 40+ template settings (rename to `.env` on VPS)
- [x] Africa's Talking credentials fields ready (to be filled)
- [x] LND configuration templates created
- [x] Bitcoin testnet pruning (550MB) preconfigured
- [x] Database connection settings ready

---

## Deployment Timeline

### Phase 1: Bitcoin & LND Infrastructure (~2-3 hours)
**Duration**: 1-2 hours automated + 30-60 minutes blockchain sync

```
Step 1: SSH to LNVPS (5 min)
  └─ ssh ubuntu@vm-1327.lnvps.cloud

Step 2: Run Bitcoin/LND Setup (2 min)
  └─ sudo bash ~/scripts/setup_bitcoin_lnd.sh

Step 3: Monitor Blockchain Sync (1-2 hours)
  └─ sudo journalctl -u bitcoin -f
  └─ Wait for "Leaving InitialBlockDownload" message

Step 4: Initialize LND Wallet (5 min)
  └─ sudo -u bitcoin lncli create
  └─ Save 24-word seed (CRITICAL!)
  └─ Set wallet password

Step 5: Verify Services (5 min)
  └─ sudo systemctl status bitcoin
  └─ sudo systemctl status lnd
  └─ Both should show "active (running)"
```

### Phase 2: Backend Deployment (~45 minutes)
**Duration**: 30 minutes installation + 15 minutes verification

```
Step 6: Deploy Backend (1 min)
  └─ sudo bash ~/scripts/deploy_satsremit.sh

Step 7: Configure Environment (5 min)
  └─ Edit ~/.env with:
     - AFRICAS_TALKING_API_KEY
     - AFRICAS_TALKING_USERNAME
     - Other sensitive credentials

Step 8: Start Services (5 min)
  └─ sudo systemctl start postgres
  └─ sudo systemctl start redis
  └─ sudo systemctl start satsremit

Step 9: Verify All Services (10 min)
  └─ curl http://localhost:8000/health
  └─ bitcoin-cli -testnet ping
  └─ lncli getinfo
  └─ Check PostgreSQL: psql -d satsremit -c "SELECT COUNT(*) FROM transfers;"

Step 10: Get Testnet Funds (10 min)
  └─ lncli newaddress p2wpkh
  └─ Send to Bitcoin testnet faucet
  └─ Wait for confirmation
```

**Total Deployment Time: ~3-4 hours**

---

## Critical Files & Locations

### On Local Machine (Before Deployment)
```
/home/satsinaction/satsremit/
├── scripts/
│   ├── setup_bitcoin_lnd.sh         ← Bitcoin + LND installation ⭐
│   ├── deploy_satsremit.sh          ← Backend deployment ⭐
│   └── setup_africas_talking.sh     ← Notification config
├── src/
│   ├── main.py                      ← FastAPI application
│   ├── models/models.py             ← 8 SQLAlchemy ORM models
│   ├── models/schemas.py            ← 25+ validation schemas
│   ├── core/config.py               ← Settings management
│   ├── db/database.py               ← Database management
│   ├── services/notification.py     ← Africa's Talking integration
│   └── api/routes/                  ← 28 endpoints (4 modules)
├── docs/
│   ├── LNVPS_DEPLOYMENT_GUIDE.md    ← Detailed deployment guide ⭐
│   ├── LNVPS_QUICK_REFERENCE.md     ← Quick commands ⭐
│   ├── BITCOIN_LND_SETUP.md         ← Bitcoin/LND specifics
│   ├── REFINED_PLAN.md              ← Architecture details
│   └── [5 more guides]
├── .env.example                      ← Configuration template ⭐
├── requirements.txt                  ← Python dependencies
├── docker-compose.yml                ← Local dev environment
└── Makefile                          ← Build utilities
```

### On LNVPS (After Deployment)
```
~/ (ubuntu home directory)
├── scripts/
│   ├── setup_bitcoin_lnd.sh          ← Downloaded & executed
│   ├── deploy_satsremit.sh           ← Downloaded & executed
│   └── setup_africas_talking.sh      ← Downloaded for later
├── .env                              ← PRODUCTION configuration (SECURED!)
├── satsremit/                        ← Cloned or deployed repo
│   ├── README.md
│   ├── requirements.txt
│   ├── src/                          ← Full Python codebase
│   └── docs/                         ← All documentation
└── bitcoin/
    ├── .bitcoin/                     ← Bitcoin data directory
    │   ├── testnet3/blocks           ← Blockchain data (pruned 550MB)
    │   └── bitcoin.conf              ← Bitcoin configuration
    └── .lnd/                         ← LND data directory
        ├── lnd.conf                  ← LND configuration
        └── data/chain/               ← LND wallet & channels
```

### Service Locations
```
Systemd Services:
- bitcoin       → /etc/systemd/system/bitcoin.service
- lnd           → /etc/systemd/system/lnd.service
- postgres      → /etc/systemd/system/postgres.service
- redis         → /etc/systemd/system/redis.service (if installed)
- satsremit     → /etc/systemd/system/satsremit.service

Configuration Files:
- Bitcoin       → ~/.bitcoin/bitcoin.conf
- LND           → ~/.lnd/lnd.conf
- PostgreSQL    → /etc/postgresql/16/main/postgresql.conf
- SatsRemit     → ~/.env (KEEP SECURE!)
```

---

## Deployment Commands Quick Reference

### Essential Commands
```bash
# SSH into VPS
ssh ubuntu@vm-1327.lnvps.cloud

# Run Phase 1: Bitcoin + LND
sudo bash ~/scripts/setup_bitcoin_lnd.sh

# Monitor Bitcoin sync
sudo journalctl -u bitcoin -f

# Initialize LND wallet (after Bitcoin syncs)
sudo -u bitcoin lncli create

# Run Phase 2: Backend
sudo bash ~/scripts/deploy_satsremit.sh

# Test Bitcoin
bitcoin-cli -testnet ping

# Test LND
lncli getinfo

# Test API
curl http://localhost:8000/health

# View Logs
sudo journalctl -u bitcoin -f       # Bitcoin logs
sudo journalctl -u lnd -f           # LND logs
sudo journalctl -u satsremit -f     # API logs

# Service Management
sudo systemctl status bitcoin       # Check status
sudo systemctl restart bitcoin      # Restart service
sudo systemctl start postgresql     # Start PostgreSQL
```

---

## What Gets Installed / Configured

### Phase 1: Bitcoin & LND
✅ **Bitcoin Core v26.0**
- Network: Testnet (safe for development)
- Mode: Pruned (550MB - space efficient)
- Features: RPC enabled, txindex disabled
- Auto-start: Yes (systemd)

✅ **LND v0.18.4**
- Network: Testnet
- Features: Hold invoices enabled (CRITICAL for remittance model)
- Auto-start: Yes (systemd)
- REST API: https://localhost:8080
- gRPC: localhost:10009

### Phase 2: Backend Stack
✅ **Python 3.10+ Environment**
- Virtual environment in ~/venv
- All dependencies from requirements.txt
- Celery + Redis for async tasks
- Auto-start: Yes (systemd)

✅ **PostgreSQL 16**
- Database: satsremit
- Schema: Auto-initialized with 8 tables
- Auto-start: Yes (systemd)

✅ **Redis 7** (Optional, for production task queue)
- Port: 6379
- Auto-start: Yes (systemd)

✅ **SatsRemit API**
- FastAPI on http://localhost:8000
- 28 endpoints ready for implementation
- Configuration from .env
- Auto-start: Yes (systemd)

---

## Pre-Execution Checklist

### Before SSH-ing In
- [ ] Have LNVPS login credentials ready: ubuntu@vm-1327.lnvps.cloud
- [ ] Have LNVPS password available
- [ ] Reserve 2-3 hours for deployment time
- [ ] Have Africa's Talking API credentials ready
- [ ] Ensure good internet connection (blockchain sync requires stable connectivity)

### Before Running setup_bitcoin_lnd.sh
- [ ] Confirm you want fresh installation (deletes old Bitcoin/LND data)
- [ ] Check disk space: `df -h` (need ~10GB available)
- [ ] Confirm network = testnet (safe for development)
- [ ] Have password for ubuntu user for sudo commands

### Before Running deploy_satsremit.sh
- [ ] Bitcoin fully synced: `bitcoin-cli -testnet getblockcount` matches explorer
- [ ] LND wallet created and unlocked: `lncli getinfo` shows sync status
- [ ] PostgreSQL running: `sudo systemctl status postgres`
- [ ] Have .env file ready with credentials

### Before Starting Services
- [ ] All .env values filled in (especially Africa's Talking credentials)
- [ ] PostgreSQL initialized: `sudo bash ~/scripts/init_project.py`
- [ ] No port conflicts: 8000 (FastAPI), 8080 (LND REST), 5432 (PostgreSQL)

---

## Expected Results

### After Phase 1 Complete
```
✅ Bitcoin Core running
   - Status: "LND in sync"
   - Network: Testnet
   - Pruned: Yes (550MB)
   
✅ LND running
   - Status: "Synced to chain"
   - Wallet: Unlocked
   - REST API: Responding at https://localhost:8080
```

### After Phase 2 Complete
```
✅ PostgreSQL running
   - Database: satsremit
   - Tables: 8 (transfers, agents, settlements, etc.)
   
✅ Redis running (if enabled)
   - Port: 6379
   - Mode: Ready for Celery tasks
   
✅ SatsRemit API running
   - URL: http://localhost:8000
   - Health: ✅ /health endpoint responding
   - Status: Ready for route implementation
```

### Test Commands After Deployment
```bash
# Bitcoin test
bitcoin-cli -testnet getblockcount
bitcoin-cli -testnet ping

# LND test
lncli getinfo
lncli walletbalance

# API test
curl http://localhost:8000/health

# Database test
psql -d satsremit -c "SELECT COUNT(*) FROM transfers;"

# All services test
sudo systemctl status bitcoin lnd postgres satsremit redis
```

---

## Troubleshooting Quick Reference

### Bitcoin Not Syncing
```bash
# Check sync status
bitcoin-cli -testnet getblockcount
# If far behind current block, check:
sudo journalctl -u bitcoin | tail -50
# Restart if needed
sudo systemctl restart bitcoin
```

### LND Wallet Issues
```bash
# Check wallet status
lncli getinfo
# If locked: lncli unlock (and enter wallet password)
# If error: check LND logs
sudo journalctl -u lnd -f
```

### PostgreSQL Connection Failed
```bash
# Check status
sudo systemctl status postgresql
# Check if running on port 5432
sudo ss -tlnp | grep 5432
# Restart if needed
sudo systemctl restart postgresql
```

### API Won't Start
```bash
# Check port 8000 not in use
sudo ss -tlnp | grep 8000
# Check .env file
cat ~/.env
# Check logs
sudo journalctl -u satsremit -f
```

---

## Post-Deployment Next Steps

### 1. Test Infrastructure
- Use test commands above to verify all services
- Make Bitcoin testnet transaction to confirm working
- Create test LND channel

### 2. Load Testnet Funds
```bash
# Get testnet Bitcoin address
lncli newaddress p2wpkh
# Use Bitcoin testnet faucet to send coins
# Wait for confirmation (usually 10-30 minutes)
```

### 3. Implement Core Services
- [ ] TransferService (create_transfer, verify, confirm)
- [ ] LNDService (invoice creation, settlement)
- [ ] RateService (currency conversion)

### 4. Implement API Routes
- [ ] Fill in all 28 endpoints with business logic
- [ ] Add authentication middleware
- [ ] Add request/response validation

### 5. Testing & QA
- [ ] Unit tests (80%+ coverage target)
- [ ] Integration tests
- [ ] End-to-end flow tests
- [ ] Load testing

---

## Safety & Security Notes

### CRITICAL - Backup LND Seed
```
When you run: sudo -u bitcoin lncli create
You will receive a 24-word seed phrase.
SAVE THIS IN A SECURE LOCATION!
This is the ONLY way to recover your wallet.
```

### Secure .env File
```bash
# .env contains sensitive data!
# Set restrictive permissions
chmod 600 ~/.env

# Never commit .env to git
# Keep it only on VPS, not in repo
```

### Testnet Safety
- This setup uses Bitcoin TESTNET (not real money)
- Testnet coins have no value
- Safe for development and testing
- Migration to mainnet requires careful review

---

## Support & Documentation

**For Deployment Help**:
- Reference: [LNVPS_DEPLOYMENT_GUIDE.md](docs/LNVPS_DEPLOYMENT_GUIDE.md) - Full step-by-step guide
- Quick Lookup: [LNVPS_QUICK_REFERENCE.md](docs/LNVPS_QUICK_REFERENCE.md) - Command reference
- Bitcoin/LND Details: [BITCOIN_LND_SETUP.md](docs/BITCOIN_LND_SETUP.md) - Technical specifics

**For Architecture Questions**:
- Architecture: [REFINED_PLAN.md](docs/REFINED_PLAN.md) - Complete system design
- Cost Analysis: [MIGRATION_TWILIO_TO_AFRICAS_TALKING.md](docs/MIGRATION_TWILIO_TO_AFRICAS_TALKING.md) - SMS service comparison
- SMS Setup: [AFRICAS_TALKING_SETUP.md](docs/AFRICAS_TALKING_SETUP.md) - Notification integration

**Checklist Done**: All infrastructure scripts and documentation prepared. System ready for deployment. ✅

---

## Status Summary

| Component | Status | Location |
|-----------|--------|----------|
| Architecture | ✅ Complete | docs/REFINED_PLAN.md |
| Database Schema | ✅ Complete | src/models/models.py |
| API Schemas | ✅ Complete | src/models/schemas.py |
| API Routes | ✅ Specified | src/api/routes/ |
| Notification Service | ✅ Implemented | src/services/notification.py |
| Bitcoin Script | ✅ Ready | scripts/setup_bitcoin_lnd.sh |
| Backend Script | ✅ Ready | scripts/deploy_satsremit.sh |
| Deployment Guide | ✅ Complete | docs/LNVPS_DEPLOYMENT_GUIDE.md |
| Configuration | ✅ Template | .env.example |
| **READY FOR DEPLOYMENT** | **✅ YES** | **Execute scripts on LNVPS** |

---

**Next Action**: SSH into LNVPS and execute `sudo bash ~/scripts/setup_bitcoin_lnd.sh`

**Estimated Timeline**: Phase 1 (2-3 hrs) → Phase 2 (45 min) → **Total: 3-4 hours for full infrastructure ready**
