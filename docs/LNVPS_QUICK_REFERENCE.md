# LNVPS Quick Reference Card

**VPS**: vm-1327.lnvps.cloud | **User**: ubuntu | **OS**: Ubuntu 22.04  
**Date Created**: April 6, 2026

---

## 🔑 SSH Access

```bash
ssh ubuntu@vm-1327.lnvps.cloud
```

---

## 📦 Installation Scripts

| Script | Purpose | Command |
|--------|---------|---------|
| `setup_bitcoin_lnd.sh` | Bitcoin + LND setup | `sudo bash ~/scripts/setup_bitcoin_lnd.sh` |
| `deploy_satsremit.sh` | Backend deployment | `sudo bash ~/deploy_satsremit.sh` |
| `init_project.py` | DB initialization | `python scripts/init_project.py` |

---

## 🚀 Quick Start (Fresh Install)

```bash
# 1. SSH in
ssh ubuntu@vm-1327.lnvps.cloud

# 2. Download & run Bitcoin setup
wget -O setup_bitcoin_lnd.sh https://raw.githubusercontent.com/bstreetwise/satsremit/main/scripts/setup_bitcoin_lnd.sh
sudo bash setup_bitcoin_lnd.sh

# 3. Start Bitcoin & wait for sync
sudo systemctl start bitcoin
sudo systemctl enable bitcoin
sudo journalctl -u bitcoin -f  # Watch until "Leaving InitialBlockDownload"

# 4. Initialize LND
sudo -u bitcoin lncli create  # Save the seed!

# 5. Start LND
sudo systemctl start lnd
sudo systemctl enable lnd

# 6. Deploy SatsRemit
cd ~/satsremit
wget -O deploy_satsremit.sh https://raw.githubusercontent.com/bstreetwise/satsremit/main/scripts/deploy_satsremit.sh
sudo bash deploy_satsremit.sh

# 7. Configure API
nano ~/satsremit/.env

# 8. Start API
sudo systemctl start satsremit
sudo systemctl enable satsremit
```

---

## 🔗 Service Ports & APIs

| Service | Port | URL | Command |
|---------|------|-----|---------|
| Bitcoin RPC | 18332 | `http://127.0.0.1:18332` | `bitcoin-cli -testnet` |
| LND gRPC | 10009 | `127.0.0.1:10009` | `lncli` |
| LND REST | 8080 | `https://127.0.0.1:8080` | `curl http://127.0.0.1:8080/v1/getinfo` |
| SatsRemit API | 8000 | `http://127.0.0.1:8000` | `curl http://127.0.0.1:8000/health` |
| PostgreSQL | 5432 | `localhost:5432` | `psql -U satsremit -d satsremit` |
| Redis | 6379 | `localhost:6379` | `redis-cli ping` |

---

## 📁 Important Directories

```
/data/bitcoin/          Bitcoin blockchain & config
/data/lnd/              LND wallet & config
~/satsremit/            SatsRemit backend code
/home/ubuntu/venv/      Python virtual environment
/var/lib/postgresql/    PostgreSQL database
```

---

## 🛠️ Essential Commands

### System Management
```bash
# Check all services
sudo systemctl status bitcoin lnd satsremit postgresql redis-server

# Start/stop services
sudo systemctl start bitcoin        # Start Bitcoin
sudo systemctl stop lnd             # Stop LND
sudo systemctl restart satsremit    # Restart API

# View logs
sudo journalctl -u bitcoin -f       # Follow Bitcoin logs
sudo journalctl -u lnd -n 50        # Last 50 LND logs
sudo journalctl -u satsremit -f     # Follow API logs
```

### Bitcoin
```bash
bitcoin-cli -testnet ping                   # Test connection
bitcoin-cli -testnet getblockcount          # Current block height
bitcoin-cli -testnet getblockchaininfo      # Full chain info
bitcoin-cli -testnet getnewaddress          # Generate address
bitcoin-cli -testnet getbalance             # Wallet balance
```

### LND
```bash
lncli getinfo                       # Node info
lncli walletbalance                 # Wallet balance
lncli newaddress p2wkh              # New address
lncli listchannels                  # List channels
lncli describegraph                 # Network graph
lncli unlock                        # Unlock wallet
```

### SatsRemit API
```bash
curl http://localhost:8000/health           # Health check
curl http://localhost:8000/api/docs         # API documentation
curl http://localhost:8000/api/transfers    # List transfers
```

### Database
```bash
psql -U satsremit -d satsremit              # Connect to DB
SELECT * FROM transfers;                    # Query transfers
SELECT * FROM agents;                       # Query agents
```

---

## ⚙️ Configuration Files

| File | Location | Purpose |
|------|----------|---------|
| Bitcoin | `/data/bitcoin/bitcoin.conf` | Bitcoin settings |
| LND | `/data/lnd/lnd.conf` | LND settings |
| SatsRemit | `~/satsremit/.env` | API environment |
| Services | `/etc/systemd/system/` | Systemd configs |

---

## 💼 LND Wallet Details (April 8, 2026)

### Connection Info
```
Pubkey: 03c3ae167e1c69f5b7d7ae9b142b4228f8b903ec491d2642cc88db5d7077f7d945
Alias: 03c3ae167e1c69f5b7d7
Network: Bitcoin Testnet
Version: LND v0.18.4-beta
Block Height: 4,909,637 (synced)
```

### Wallet Access
```
Password: SatsRemit2026
Data Dir: /home/bitcoin/.lnd
TLS Cert: /home/bitcoin/.lnd/tls.cert
TLS Key: /home/bitcoin/.lnd/tls.key
```

### Recovery Seed (SAVE SECURELY!)
```
about despair hotel change trigger ill long lunar
sunny annual rookie ozone screen brain occur brain
peanut cousin morning true elegant curtain problem pledge
```

### Test Bitcoin Address (P2WPKH)
```
tb1qnrlxnty5x0nusendfyfxp903vmnmx7q0qu4hks
```

### Test Invoice (10,000 sat)
```
lntb100u1p5av22app55ggsflm3f7g9ezknw3e2kn633zjze03ttqe5mvamsqdmlhw3uwqqdp823jhxapqf9h8vmmfvdjjqtfq2dshgu6jv4kkjaqcqzzsxqyz5vqsp5j6rpnnatzvpkg03znpemckqsmtfqre9j5q8nykr4u4a8e5fka2as9qxpqysgqg55cfezlvn9pw9kc4jup5vx86egncl3q6y2w97mugswpw8pktq9x4pnflsukl9w0xqk2sxcv5pqkyt5r3d6lp2jrrryymjjxldmugxcpdugwgl
```

---

## 🧪 Testing Procedures

### 1. Unlock Wallet (Required for Each Session)
```bash
ssh ubuntu@vm-1327.lnvps.cloud

# Create tmux session for interactive password input
tmux new-session -d -s unlock
tmux send-keys -t unlock "sudo -u bitcoin lncli --lnddir=/home/bitcoin/.lnd --tlscertpath=/home/bitcoin/.lnd/tls.cert --network=testnet unlock" Enter
sleep 2
tmux send-keys -t unlock "SatsRemit2026" Enter
sleep 2

# Verify unlocked
sudo -u bitcoin lncli --lnddir=/home/bitcoin/.lnd --tlscertpath=/home/bitcoin/.lnd/tls.cert --network=testnet getinfo
```

### 2. Fund the Wallet
Send testnet BTC to the address above using:
- **Testnet Faucet**: https://testnet-faucet.mempool.co/
- **Faucet 2**: https://coinfaucet.eu/en/btc-testnet/
- **Amount**: Start with 0.01 BTC to test channels

### 3. Check Wallet Balance
```bash
sudo -u bitcoin lncli --lnddir=/home/bitcoin/.lnd --tlscertpath=/home/bitcoin/.lnd/tls.cert --network=testnet walletbalance
```

### 4. Create Test Invoice
```bash
sudo -u bitcoin lncli --lnddir=/home/bitcoin/.lnd --tlscertpath=/home/bitcoin/.lnd/tls.cert --network=testnet addinvoice --memo="Test" --amt=5000
```

### 5. List Active Channels
```bash
sudo -u bitcoin lncli --lnddir=/home/bitcoin/.lnd --tlscertpath=/home/bitcoin/.lnd/tls.cert --network=testnet listchannels
```

### 6. Test REST API
```bash
# LND REST API (gRPC proxy on :8080)
curl -s https://127.0.0.1:8080/v1/getinfo --cacert /home/bitcoin/.lnd/tls.cert | jq

# SatsRemit API (when deployed)
curl http://localhost:8000/api/health
```

---

## 🔌 LND Service Management

### Start LND
```bash
sudo systemctl start lnd
```

### Stop LND
```bash
sudo systemctl stop lnd
```

### View Logs
```bash
sudo journalctl -u lnd -f              # Follow live logs
sudo journalctl -u lnd -n 100          # Last 100 lines
sudo journalctl -u lnd --since "10 min ago"
```

### Check Status
```bash
sudo systemctl status lnd
ps aux | grep lnd
```

---

## 📡 SatsRemit API Integration

### LND Connection Configuration
When deploying SatsRemit API, configure LND connection with:

```python
# In src/core/config.py or .env
LND_HOST = "127.0.0.1"
LND_PORT = 10009
LND_CERT_PATH = "/home/bitcoin/.lnd/tls.cert"
LND_MACAROON_PATH = "/home/bitcoin/.lnd/data/chain/bitcoin/testnet3/admin.macaroon"
LND_NETWORK = "testnet"
```

### Required LND Methods for SatsRemit

```python
# Creating invoices for transfers
lncli addinvoice --memo="Transfer REF-12345" --amt=50000

# Getting node info
lncli getinfo

# Triggering notifications via WhatsApp
# (Integrated in TransferService)
```

### Test Transfer Flow
1. Sender initiates transfer via API
2. System creates LND invoice
3. Receiver gets WhatsApp PIN notification
4. Receiver pays invoice via Lightning
5. system sends completion notification

---

## ⚠️ Troubleshooting

### LND Not Starting
```bash
# Check config
sudo cat /data/lnd/lnd.conf

# Verify Bitcoin is synced
bitcoin-cli -testnet getblockcount

# Verify ZMQ is enabled on Bitcoin
sudo netstat -tlnp | grep :28332

# Check logs
sudo journalctl -u lnd -n 50
```

### Wallet Locked
```bash
# Always unlock after restart
tmux new-session -d -s unlock
tmux send-keys -t unlock "sudo -u bitcoin lncli --lnddir=/home/bitcoin/.lnd --tlscertpath=/home/bitcoin/.lnd/tls.cert --network=testnet unlock" Enter
sleep 2
tmux send-keys -t unlock "SatsRemit2026" Enter
```

### Connection Refused (10009)
```bash
# LND not responding to RPC
# 1. Check if LND is running
ps aux | grep lnd

# 2. Check if wallet is locked
sudo systemctl restart lnd
<unlock wallet>

# 3. Check if Bitcoin has ZMQ
sudo netstat -tlnp | grep 28332
```

---

## 🔒 Important Credentials

```
Bitcoin RPC:
  User: bitcoin
  Pass: changeMe123!@# (CHANGE THIS!)
  
PostgreSQL:
  User: satsremit
  Pass: satsremit_dev_password (CHANGE THIS!)
  
LND Seed:
  Location: Saved in ~/.lncli/.lndseed (BACKUP THIS!)
  
JWT Secret:
  Location: In .env file (GENERATE UNIQUE!)
```

---

## 🚨 Troubleshooting Quick Fixes

```bash
# Bitcoin won't start
sudo systemctl status bitcoin
sudo journalctl -u bitcoin -n 50
# If corrupted: sudo rm -rf /data/bitcoin/.lock

# LND won't connect
sudo systemctl status bitcoin
lncli unlock  # May need to unlock wallet
# If corrupted: sudo rm -rf /data/lnd/chain/bitcoin/testnet/

# API not responding
sudo systemctl status satsremit
sudo journalctl -u satsremit -n 50
# Check database: psql -U satsremit -d satsremit -c "SELECT 1;"

# Database connection error
sudo systemctl status postgresql
sudo -u postgres psql -l  # List databases
# Check .env DATABASE_URL is correct
```

---

## 📊 Status Checks

```bash
# Overall health
#!/bin/bash
echo "=== Bitcoin ===" && bitcoin-cli -testnet ping && echo "✓ OK" || echo "✗ FAIL"
echo "=== LND ===" && lncli getinfo > /dev/null && echo "✓ OK" || echo "✗ FAIL"
echo "=== PostgreSQL ===" && psql -U satsremit -d satsremit -c "SELECT 1;" && echo "✓ OK" || echo "✗ FAIL"
echo "=== Redis ===" && redis-cli ping && echo "✓ OK" || echo "✗ FAIL"
echo "=== API ===" && curl -s http://localhost:8000/health | grep -q "healthy" && echo "✓ OK" || echo "✗ FAIL"
```

---

## 📈 Monitoring

```bash
# Disk usage
df -h /data /var

# Memory usage
free -h

# CPU usage
top -b -n 1 | grep Cpu

# Process check
ps aux | grep -E "bitcoind|lnd|python" | grep -v grep

# Network connections
netstat -an | grep ESTABLISHED | wc -l

# Logs size
du -sh /var/log/
```

---

## 🔄 Maintenance Tasks

### Daily
- [ ] Check all services running: `sudo systemctl status bitcoin lnd satsremit`
- [ ] Review logs: `sudo journalctl -x -n 100`
- [ ] Check disk space: `df -h /`

### Weekly
- [ ] Backup database: `sudo -u postgres pg_dump satsremit | gzip > backup.sql.gz`
- [ ] Check Bitcoin sync: `bitcoin-cli -testnet getblockcount`
- [ ] Monitor API logs: `sudo journalctl -u satsremit -n 1000`

### Monthly
- [ ] Review service performance
- [ ] Update packages: `sudo apt update && sudo apt upgrade`
- [ ] Rotate logs: `sudo journalctl --vacuum=30d`
- [ ] Review security settings

---

## 🚀 Deployment Timeline

| Phase | Duration | Status |
|-------|----------|--------|
| Bitcoin setup | 10 min | ✅ |
| Bitcoin sync | 1-2 hours | ⏳ |
| LND setup | 10 min | ⏳ |
| Backend deploy | 30 min | ⏳ |
| Testing | 1 hour | ⏳ |
| **Total** | **~3-4 hours** | |

---

## 📞 Support

**Documentation**: `/home/ubuntu/satsremit/docs/`
- `LNVPS_DEPLOYMENT_GUIDE.md` - Full deployment guide
- `BITCOIN_LND_SETUP.md` - Bitcoin & LND details
- `REFINED_PLAN.md` - Architecture documentation

**External Resources**:
- Bitcoin: https://bitcoin.org
- LND: https://github.com/lightningnetwork/lnd
- LNVPS: https://www.lnvps.com

---

**VPS**: vm-1327.lnvps.cloud  
**Deployed**: April 6, 2026  
**Status**: Ready for Phase 1 Testing  
**Next**: Begin transfer testing
