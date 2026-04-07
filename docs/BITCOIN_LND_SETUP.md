# Bitcoin & LND Setup on LNVPS

**Platform**: LNVPS (Luxembourg VPS)  
**OS**: Ubuntu 22.04 LTS  
**Configuration**: Testnet (pruned) → Mainnet (ready for migration)  
**Date**: April 6, 2026

## 📋 Quick Start

### 1. SSH into LNVPS

```bash
ssh ubuntu@vm-1327.lnvps.cloud
# Password provided separately
```

### 2. Download & Run Setup Script

```bash
# Download the setup script
cd /home/ubuntu
curl -o setup_bitcoin_lnd.sh https://raw.githubusercontent.com/satsremit/satsremit/main/scripts/setup_bitcoin_lnd.sh
chmod +x setup_bitcoin_lnd.sh

# Run with sudo
sudo bash setup_bitcoin_lnd.sh

# This will take ~15 minutes
```

### 3. Start Bitcoin & LND

```bash
# Start Bitcoin (will sync blockchain)
sudo systemctl start bitcoin
sudo systemctl enable bitcoin

# Monitor Bitcoin sync
sudo journalctl -u bitcoin -f

# Wait until you see "Leaving InitialBlockDownload"
# (testnet typically takes 1-2 hours)
```

### 4. Initialize LND Wallet

Once Bitcoin is synced:

```bash
# Create LND wallet
sudo -u bitcoin lncli create

# Follow the prompts:
# - Create password for wallet
# - Create seed (SAVE THIS!)
# - Confirm seed

# Check status
lncli getinfo
```

### 5. Start LND

```bash
# Start LND
sudo systemctl start lnd
sudo systemctl enable lnd

# Monitor LND
sudo journalctl -u lnd -f

# Check LND status
lncli getinfo
```

---

## 🏗️ What Gets Installed

### Bitcoin Core v26.0
- **Build**: Pruned (550 MB)
- **Network**: Testnet (initially)
- **RPC**: `bitcoin-cli` available
- **Location**: `/opt/bitcoin`
- **Data**: `/data/bitcoin`

### LND v0.18.4
- **Network**: Testnet (initially)
- **Features**: Hold invoices, AMP, anchors
- **REST API**: `http://127.0.0.1:8080`
- **gRPC**: `127.0.0.1:10009`
- **Location**: `/opt/lnd`
- **Data**: `/data/lnd`

---

## 🔧 Configuration Details

### Bitcoin (Testnet Pruned)

**File**: `/data/bitcoin/bitcoin.conf`

```ini
# Network
testnet=1              # Enable testnet
server=1               # Enable RPC server
listen=1               # Accept connections

# RPC
rpcuser=bitcoin        # RPC username
rpcpassword=change...  # RPC password (CHANGE!)
rpcbind=127.0.0.1      # Bind to localhost only
rpcport=18332          # Testnet RPC port

# Pruning (550 MB)
prune=550              # Prune to 550 MB blocks

# Performance
maxconnections=100     # Max peers
dbcache=512            # Cache in MB

# Indexing
txindex=1              # Index all transactions
```

**Key Settings**:
- ✅ `testnet=1` - Testnet blockchain
- ✅ `prune=550` - Keeps only recent blocks (~550 MB)
- ✅ `txindex=1` - LND needs transaction index
- ✅ `rpcbind=127.0.0.1` - Localhost only (secure)

### LND (Testnet with Hold Invoices)

**File**: `/data/lnd/lnd.conf`

```ini
# Network
bitcoin.testnet=1           # Testnet
bitcoin.active=1            # Bitcoin only

# API
listen=0.0.0.0:9735         # P2P port
rpclisten=127.0.0.1:10009   # gRPC
restlisten=127.0.0.1:8080   # REST API

# Bitcoin connection
bitcoin.node=bitcoind        # Use local Bitcoin
[bitcoind]
rpchost=127.0.0.1:18332     # Bitcoin RPC
rpcuser=bitcoin
rpcpass=change...

# Features
protocol.wumbo-channels=true # Large channels
protocol.anchors=true        # Anchor outputs

# Hold Invoices
[invoices]
hodl.invoice.expiry=600      # 10 min hold
```

**Key Settings**:
- ✅ `bitcoin.testnet=1` - Testnet
- ✅ `restlisten=127.0.0.1:8080` - REST API for SatsRemit
- ✅ `hodl.invoice.expiry=600` - Hold invoice support

---

## 📊 Directory Structure

```
/data/
├── bitcoin/
│   ├── bitcoin.conf          # Bitcoin config
│   ├── testnet3/             # Testnet blockchain (pruned ~550MB)
│   │   ├── blocks/
│   │   ├── chainstate/
│   │   └── wallet.dat
│   └── bitcoin.log           # Bitcoin logs

└── lnd/
    ├── lnd.conf              # LND config
    ├── chain/
    │   └── bitcoin/
    │       └── testnet/      # LND testnet data
    ├── logs/                 # LND logs
    ├── tls.cert              # TLS certificate
    └── data/
        ├── graph.db          # Channel graph
        └── peers.db          # Peer database
```

---

## 🚀 Common Commands

### Bitcoin

```bash
# Check Bitcoin status
bitcoin-cli -testnet getblockchaininfo

# Get current block height
bitcoin-cli -testnet getblockcount

# Get network info
bitcoin-cli -testnet getnetworkinfo

# Create new address
bitcoin-cli -testnet getnewaddress

# Get balance
bitcoin-cli -testnet getbalance

# View logs
sudo journalctl -u bitcoin -f

# Stop Bitcoin
sudo systemctl stop bitcoin
```

### LND

```bash
# Get LND info
lncli getinfo

# Create wallet (first time only)
lncli create

# Get wallet balance
lncli walletbalance

# List channels
lncli listchannels

# Create invoice
lncli addinvoice --amt 10000

# Pay invoice
lncli payinvoice <invoice>

# View logs
sudo journalctl -u lnd -f

# Stop LND
sudo systemctl stop lnd
```

---

## 🔄 Blockchain Sync Status

### Check Bitcoin Sync Progress

```bash
bitcoin-cli -testnet getblockchaininfo | grep -A2 initialblockdownload
```

Output when syncing:
```json
{
  "verified_blocks": 2400000,
  "verifying_blocks": true
}
```

Output when done:
```json
{
  "initialblockdownload": false
}
```

**Testnet Sync Time**: 1-2 hours (much faster than mainnet)

### Monitor in Real-Time

```bash
# Watch progress
watch -n 10 'bitcoin-cli -testnet getblockchaininfo | grep verified_blocks'

# Or follow logs
sudo journalctl -u bitcoin -f | grep -i "progress\|block"
```

---

## 🔌 API Connectivity

### Test REST API

```bash
# Check LND is running
curl http://127.0.0.1:8080/v1/getinfo

# Get wallet balance
curl http://127.0.0.1:8080/v1/wallet/balance/blockchain

# List peers
curl http://127.0.0.1:8080/v1/peers
```

### Using with SatsRemit

Configure in `.env`:

```bash
LND_REST_URL=https://127.0.0.1:8080
LND_MACAROON_PATH=/data/lnd/data/chain/bitcoin/testnet/admin.macaroon
LND_CERT_PATH=/data/lnd/tls.cert
```

**Note**: To use REST API from SatsRemit backend:
1. Copy TLS cert and macaroon to backend server
2. Or use localhost (if backend on same VPS)

---

## 🛡️ Security

### Change Default RPC Password

Before production, update `/data/bitcoin/bitcoin.conf`:

```bash
# Generate new password
openssl rand -base64 32

# Edit config
sudo vi /data/bitcoin/bitcoin.conf

# Change this line:
rpcpassword=YOUR_NEW_PASSWORD_HERE

# Restart Bitcoin
sudo systemctl restart bitcoin
```

### Firewall (If Needed)

```bash
# Allow SSH
sudo ufw allow 22/tcp

# Allow Bitcoin P2P (only if needed)
sudo ufw allow 18333/tcp  # Testnet

# Allow LND P2P (only if needed)
sudo ufw allow 9735/tcp

# Check firewall
sudo ufw status
```

### Secure LND Macaroon

```bash
# Restrict macaroon access
sudo chmod 600 /data/lnd/data/chain/bitcoin/testnet/admin.macaroon

# Create read-only macaroon for API
lncli bakemacaroon --read
```

---

## 🔄 Migration: Testnet → Mainnet

When ready to go to production:

### 1. Backup Current Data

```bash
# Backup testnet wallet
sudo tar -czf /data/bitcoin-testnet-backup.tar.gz /data/bitcoin/testnet3/

# Backup LND testnet data
sudo tar -czf /data/lnd-testnet-backup.tar.gz /data/lnd/chain/
```

### 2. Update Configuration

Edit `/data/bitcoin/bitcoin.conf`:
```bash
# Change from:
testnet=1

# To:
# testnet=0  (comment out for mainnet)
```

Edit `/data/lnd/lnd.conf`:
```bash
# Change from:
bitcoin.testnet=1

# To:
# bitcoin.testnet=0  (comment out for mainnet)
```

### 3. Restart Services

```bash
sudo systemctl restart bitcoin
# Wait for mainnet sync (several hours)

sudo systemctl restart lnd
```

### 4. Verify Mainnet

```bash
# Check Bitcoin is on mainnet
bitcoin-cli getblockchaininfo | grep chain

# Check LND is on mainnet
lncli getinfo | grep testnet
```

---

## 🐛 Troubleshooting

### Bitcoin Won't Start

```bash
# Check logs
sudo journalctl -u bitcoin -n 50

# Check if port is in use
sudo lsof -i :18332

# Verify config syntax
bitcoind -conf=/data/bitcoin/bitcoin.conf -testnet -printtoconsole 2>&1 | head -20

# Restart service
sudo systemctl restart bitcoin
```

### LND Won't Connect to Bitcoin

```bash
# Check Bitcoin is running
sudo systemctl status bitcoin

# Check Bitcoin RPC works
bitcoin-cli -testnet ping

# Check LND logs
sudo journalctl -u lnd -n 50 | grep -i error

# Verify RPC credentials in lnd.conf
cat /data/lnd/lnd.conf | grep -A3 "bitcoind"
```

### Slow Blockchain Sync

```bash
# Check network connections
bitcoin-cli -testnet getnetworkinfo

# Check block height
bitcoin-cli -testnet getblockcount

# Check peer connections
bitcoin-cli -testnet getpeerinfo | wc -l

# If stuck, may need to restart
sudo systemctl restart bitcoin
```

### LND Wallet Issues

```bash
# If wallet locked
lncli unlock

# If wallet corrupted
sudo systemctl stop lnd
sudo rm -rf /data/lnd/chain/bitcoin/testnet
sudo systemctl start lnd
lncli create  # Recreate wallet
```

---

## 📈 Performance Monitoring

### Check Disk Usage

```bash
# Bitcoin blockchain
du -sh /data/bitcoin

# LND data
du -sh /data/lnd

# Overall
df -h /data
```

**Expected**:
- Bitcoin testnet: ~500-600 MB (pruned)
- LND data: ~100-200 MB

### Check CPU/Memory

```bash
# Real-time monitoring
htop

# Bitcoin process
ps aux | grep bitcoind

# LND process
ps aux | grep lnd
```

### View System Logs

```bash
# Bitcoin
sudo journalctl -u bitcoin -f

# LND
sudo journalctl -u lnd -f

# System
sudo journalctl -n 50
```

---

## 🔗 Related Documentation

- [Bitcoin Core Documentation](https://bitcoin.org/en/developer-reference)
- [LND Documentation](https://github.com/lightningnetwork/lnd)
- [SatsRemit LND Integration](../src/services/lnd_service.py)

---

## ⚡ Quick Checklist

- [ ] SSH into LNVPS
- [ ] Download and run setup script
- [ ] Wait for Bitcoin to sync
- [ ] Initialize LND wallet
- [ ] Start LND
- [ ] Test REST API (`curl http://127.0.0.1:8080/v1/getinfo`)
- [ ] Configure SatsRemit `.env` with LND details
- [ ] Test transfer creation flow
- [ ] Ready for Phase 1 testing!

---

**Status**: Installation guide complete  
**Next**: Run setup script and wait for blockchain sync  
**Estimated time**: 2-3 hours (includes blockchain download)
