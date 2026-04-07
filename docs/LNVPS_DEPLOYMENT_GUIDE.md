# LNVPS Complete Deployment Guide

**Platform**: LNVPS (Luxembourg VPS)  
**Hostname**: vm-1327.lnvps.cloud  
**OS**: Ubuntu 22.04 LTS  
**Services**: Bitcoin, LND, PostgreSQL, Redis, FastAPI  

## 🎯 Deployment Overview

This guide covers the complete setup of SatsRemit infrastructure on LNVPS:

1. **Bitcoin Core** (testnet, pruned) - Block validation
2. **LND** (testnet) - Lightning Network
3. **PostgreSQL** - Database
4. **Redis** - Cache & message broker
5. **SatsRemit API** - FastAPI backend

**Total Deployment Time**: ~3-4 hours (includes blockchain sync)

---

## 📋 Prerequisites

### LNVPS Setup
- ✅ VPS provisioned: **vm-1327.lnvps.cloud**
- ✅ OS: Ubuntu 22.04 LTS
- ✅ SSH access with ubuntu user
- ✅ Sufficient disk space: ~20 GB

### Local Requirements
- SSH client (built-in on Mac/Linux, or PuTTY on Windows)
- Text editor (optional, for environment configuration)

---

## 🚀 Phase 1: Bitcoin & LND Setup (1-2 hours)

### Step 1: SSH into LNVPS

```bash
ssh ubuntu@vm-1327.lnvps.cloud
# Enter password when prompted
```

### Step 2: Download Setup Script

```bash
# Create scripts directory
mkdir -p ~/scripts

# Download Bitcoin & LND setup script
wget -O ~/scripts/setup_bitcoin_lnd.sh \
  https://raw.githubusercontent.com/satsremit/satsremit/main/scripts/setup_bitcoin_lnd.sh

chmod +x ~/scripts/setup_bitcoin_lnd.sh
```

### Step 3: Run Setup Script

```bash
# Run with sudo (installs system packages)
sudo bash ~/scripts/setup_bitcoin_lnd.sh

# This will:
# - Install Bitcoin Core v26.0
# - Install LND v0.18.4
# - Configure for testnet
# - Create systemd services
# Takes ~10 minutes
```

### Step 4: Start Bitcoin

```bash
# Start Bitcoin Core
sudo systemctl start bitcoin
sudo systemctl enable bitcoin

# Monitor blockchain sync (may take 1-2 hours for testnet)
sudo journalctl -u bitcoin -f

# Watch for: "Leaving InitialBlockDownload"
# When you see this, blockchain is synced!
```

**Expected output when done**:
```
bitcoin-bitcoind[1234]: 2026-04-06 12:34:56 Leaving InitialBlockDownload (height 2500000)
```

### Step 5: Initialize LND

Once Bitcoin is fully synced:

```bash
# Create LND wallet (saves seed, SAVE IT!)
sudo -u bitcoin lncli create

# Follow prompts:
# 1. Enter wallet password (min 8 chars)
# 2. Press enter to generate seed
# 3. Write down all 24 seed words in order
# 4. Confirm seed by entering words in order

# Check LND status
lncli getinfo
```

### Step 6: Start LND

```bash
# Start LND
sudo systemctl start lnd
sudo systemctl enable lnd

# Monitor LND startup
sudo journalctl -u lnd -f

# Watch for: "Server started successfully"
```

**Expected output**:
```
lnd[1234]: 2026-04-06 13:45:00 Server started successfully
```

### Verification

```bash
# Test Bitcoin RPC
bitcoin-cli -testnet ping
# Response: null (means success)

# Test LND REST API
curl http://127.0.0.1:8080/v1/getinfo
# Should return JSON with node info

# Check Bitcoin sync status
bitcoin-cli -testnet getblockchaininfo | grep -E "blocks|headers"
# blocks and headers should be equal
```

---

## 🚀 Phase 2: SatsRemit Backend Deployment (30-45 min)

### Step 1: Prepare Project

```bash
# Go to home directory
cd ~

# Clone repository (if not already cloned)
git clone https://github.com/satsremit/satsremit.git
cd satsremit
```

### Step 2: Run Deployment Script

```bash
# Download deployment script
wget -O ../deploy_satsremit.sh \
  https://raw.githubusercontent.com/satsremit/satsremit/main/scripts/deploy_satsremit.sh

chmod +x ../deploy_satsremit.sh

# Run deployment
sudo bash ../deploy_satsremit.sh

# This will:
# - Install Python 3.10
# - Create virtual environment
# - Install dependencies
# - Setup PostgreSQL & Redis
# - Initialize database
# - Create systemd service
```

### Step 3: Configure Environment

```bash
# Edit environment configuration
nano .env

# Update these critical values:
AFRICAS_TALKING_API_KEY=your_api_key_here
AFRICAS_TALKING_USERNAME=your_username
JWT_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
```

**Key settings for LNVPS**:
```bash
# Database (PostgreSQL)
DATABASE_URL=postgresql://satsremit:satsremit_dev_password@localhost:5432/satsremit

# Cache (Redis)
REDIS_URL=redis://localhost:6379/0

# Lightning Network (Local LND)
LND_REST_URL=https://127.0.0.1:8080
LND_MACAROON_PATH=/data/lnd/data/chain/bitcoin/testnet/admin.macaroon
LND_CERT_PATH=/data/lnd/tls.cert

# Bitcoin Network
BITCOIN_NETWORK=testnet
BITCOIN_RPC_URL=http://localhost:18332
BITCOIN_RPC_USER=bitcoin
BITCOIN_RPC_PASSWORD=changeMe123!@#  # CHANGE THIS!

# Platform
ENVIRONMENT=development
DEBUG=false

# Notifications
AFRICAS_TALKING_API_KEY=your_api_key
AFRICAS_TELLING_USERNAME=your_username
```

### Step 4: Test Database

```bash
# Verify PostgreSQL is running
sudo systemctl status postgresql

# Test database connection
python3 << 'EOF'
import psycopg2
try:
    conn = psycopg2.connect(
        "dbname=satsremit user=satsremit password=satsremit_dev_password host=localhost"
    )
    print("✓ Database connection successful")
    conn.close()
except Exception as e:
    print(f"✗ Database connection failed: {e}")
EOF
```

### Step 5: Test Application (Optional)

```bash
# Activate virtual environment
source venv/bin/activate

# Run development server (non-daemon)
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000

# In another SSH session, test:
curl http://localhost:8000/
curl http://localhost:8000/health

# Stop with Ctrl+C
```

### Step 6: Start as Service

```bash
# Start the service
sudo systemctl start satsremit
sudo systemctl enable satsremit

# Check status
sudo systemctl status satsremit

# View logs
sudo journalctl -u satsremit -n 50 -e

# Follow logs live
sudo journalctl -u satsremit -f
```

### Verification

```bash
# Test API endpoints
curl http://localhost:8000/
curl http://localhost:8000/health

# Check API documentation
# Visit: http://vm-1327.lnvps.cloud:8000/api/docs
# (from your local browser, or use SSH tunneling)

# Test database
curl http://localhost:8000/api/admin/transfers

# Check all services
sudo systemctl status bitcoin
sudo systemctl status lnd
sudo systemctl status postgresql
sudo systemctl status redis-server
sudo systemctl status satsremit
```

---

## 🔐 SSH Tunneling (Access API from Local Machine)

If you want to access the API from your local machine:

```bash
# Create SSH tunnel
ssh -L 8000:127.0.0.1:8000 \
    -L 8080:127.0.0.1:8080 \
    ubuntu@vm-1327.lnvps.cloud

# Keep this terminal open in background
# Now you can access:
# API: http://localhost:8000/api/docs
# LND: http://localhost:8080/v1/getinfo
```

---

## 📊 Service Status & Monitoring

### Check All Services

```bash
# Bitcoin
sudo systemctl status bitcoin
bitcoin-cli -testnet ping

# LND
sudo systemctl status lnd
lncli getinfo

# PostgreSQL
sudo systemctl status postgresql
psql -U satsremit -d satsremit -c "SELECT version();"

# Redis
sudo systemctl status redis-server
redis-cli ping

# SatsRemit API
sudo systemctl status satsremit
curl http://localhost:8000/health
```

### View Logs

```bash
# Bitcoin logs
sudo journalctl -u bitcoin -f

# LND logs
sudo journalctl -u lnd -f

# SatsRemit logs
sudo journalctl -u satsremit -f

# PostgreSQL logs (system)
sudo tail -f /var/log/postgresql/postgresql-*.log

# Redis logs
sudo journalctl -u redis-server -f
```

### Disk Usage

```bash
# Check overall usage
df -h /

# Bitcoin data
du -sh /data/bitcoin

# LND data
du -sh /data/lnd

# Database
du -sh /var/lib/postgresql
```

---

## 🔄 Maintenance

### Restart Services

```bash
# Restart all services
sudo systemctl restart bitcoin
sudo systemctl restart lnd
sudo systemctl restart postgresql
sudo systemctl restart redis-server
sudo systemctl restart satsremit

# Or use shortcut
sudo systemctl restart bitcoin lnd postgresql redis-server satsremit
```

### Update SatsRemit Code

```bash
cd ~/satsremit

# Pull latest changes
git pull origin main

# Reinstall dependencies if needed
source venv/bin/activate
pip install -r requirements.txt --upgrade

# Reinitialize database if schema changed
python -c "from src.db.database import get_db_manager; get_db_manager().create_tables()"

# Restart service
sudo systemctl restart satsremit
```

### Backup Data

```bash
# Backup Bitcoin blockchain
sudo tar -czf ~/backups/bitcoin-$(date +%Y%m%d).tar.gz /data/bitcoin/testnet3/

# Backup LND data
sudo tar -czf ~/backups/lnd-$(date +%Y%m%d).tar.gz /data/lnd/

# Backup database
sudo -u postgres pg_dump satsremit | gzip > ~/backups/satsremit-$(date +%Y%m%d).sql.gz
```

---

## 🚨 Troubleshooting

### Bitcoin Won't Start

```bash
# Check for errors
sudo journalctl -u bitcoin -n 100

# Verify config
bitcoind -conf=/data/bitcoin/bitcoin.conf -testnet -printtoconsole 2>&1 | head -50

# Reset if corrupted
sudo systemctl stop bitcoin
sudo rm -rf /data/bitcoin/testnet3/.lock
sudo systemctl start bitcoin
```

### LND Won't Connect

```bash
# Check Bitcoin is running
sudo systemctl status bitcoin

# Check LND logs
sudo journalctl -u lnd -n 100 | grep -i error

# Verify Bitcoin RPC
bitcoin-cli -testnet ping

# Restart LND
sudo systemctl restart lnd
```

### Database Connection Error

```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Check if database exists
sudo -u postgres psql -l | grep satsremit

# Check if user exists
sudo -u postgres psql -c "\du" | grep satsremit

# Recreate if needed
sudo -u postgres dropdb satsremit  # Be careful!
sudo bash ~/deploy_satsremit.sh    # Run again
```

### API Not Responding

```bash
# Check if service is running
sudo systemctl status satsremit

# Check for errors
sudo journalctl -u satsremit -n 50

# Check port is listening
sudo lsof -i :8000

# Test locally
curl http://127.0.0.1:8000/health

# Restart service
sudo systemctl restart satsremit
```

---

## 📱 Production Checklist (Before Going Live)

- [ ] Change all default passwords (Bitcoin RPC, PostgreSQL)
- [ ] Generate strong JWT secret
- [ ] Configure Africa's Talking API key
- [ ] Enable firewall (UFW)
- [ ] Set up automatic backups
- [ ] Configure SSL/TLS certificates
- [ ] Set up log rotation
- [ ] Configure monitoring/alerting
- [ ] Test failover procedures
- [ ] Load test the API
- [ ] Security audit
- [ ] Set up DNS records
- [ ] Migrate to mainnet (Bitcoin & LND)

---

## 📞 Quick Commands Reference

```bash
# System
sudo systemctl status bitcoin/lnd/satsremit
sudo systemctl restart bitcoin/lnd/satsremit
sudo journalctl -u bitcoin/lnd/satsremit -f

# Bitcoin
bitcoin-cli -testnet ping
bitcoin-cli -testnet getblockcount
bitcoin-cli -testnet getbalance

# LND
lncli getinfo
lncli walletbalance
lncli newaddress p2wkh

# Database
psql -U satsremit -d satsremit
SELECT * FROM transfers;

# API
curl http://localhost:8000/health
curl http://localhost:8000/api/agent/locations
```

---

## 🎓 Next Steps After Deployment

1. **Test Transfer Flow**
   - Create test transfer
   - Verify invoice generation
   - Test agent verification
   - Test payout confirmation

2. **Integrate Frontend**
   - Deploy web UI
   - Test end-to-end
   - Load testing

3. **Go to Production**
   - Migrate to mainnet
   - Add KYC/AML
   - Set up monitoring
   - Go live with first users

---

## 📈 Performance Baseline (After Deployment)

```bash
# Check baseline performance
# CPU usage
top -b -n 1 | grep Cpu

# Memory usage
free -h

# Disk usage
df -h /

# Network
netstat -s

# API response time
time curl http://localhost:8000/health
```

**Expected baseline**:
- Bitcoin: 5-10% CPU, 500 MB RAM
- LND: 2-5% CPU, 200 MB RAM
- PostgreSQL: 1-3% CPU, 100 MB RAM
- Redis: <1% CPU, 50 MB RAM
- API: <2% CPU idle, 100 MB RAM

---

## 📞 Support & Documentation

- **Bitcoin Docs**: https://bitcoin.org/en/documentation
- **LND Docs**: https://github.com/lightningnetwork/lnd/tree/master/docs
- **SatsRemit Docs**: See `/docs` directory in repository
- **LNVPS Support**: https://www.lnvps.com/support

---

**Deployment Date**: April 6, 2026  
**Status**: Ready for Phase 1 Testing  
**Next Review**: After first 100 transfers
