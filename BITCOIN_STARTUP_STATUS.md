# Bitcoin Startup Status & Monitoring

**VPS**: vm-1327.lnvps.cloud  
**Date**: April 7, 2026  
**Phase**: Bitcoin initialization (Phase 1)

---

## Current Status

Bitcoin Core v26.0 has been configured and started on testnet. It is currently initializing its database and network connections.

### Bitcoin Configuration
- **Network**: Testnet
- **Pruning**: 550 MB
- **RPC User**: bitcoin
- **RPC Password**: SatsRemit123SecurePass
- **RPC Port**: 18332 (testnet)
- **Data Directory**: /data/bitcoin
- **Config File**: /data/bitcoin/bitcoin.conf

---

## Monitor Bitcoin Startup (SSH to VPS)

```bash
ssh ubuntu@vm-1327.lnvps.cloud

# View Bitcoin logs in real-time
sudo journalctl -u bitcoin -f

# Check if RPC is responding (in a new terminal)
watch -n 5 'bitcoin-cli -testnet getblockcount 2>&1 | grep -v "error" || echo "RPC connecting..."'

# Check service status
sudo systemctl status bitcoin

# Verify process is running
ps aux | grep bitcoind
```

---

## Expected Timeline

| Phase | Duration | Signal |
|-------|----------|--------|
| Database initialization | 5-10 min | Seeing debug lines in logs |
| RPC binding | 1-2 min | RPC responds to `bitcoin-cli` |
| Network sync starts | Immediate | Connections to testnet peers |
| Initial block download | 45-90 min | "Leaving InitialBlockDownload" message |
| **Ready for LND** | ~2 hours | Fully synced, ready for wallet |

---

## Next Steps (After Bitcoin Syncs)

### 1. Wait for Sync Complete
Watch logs until you see:
```
Leaving InitialBlockDownload [Main thread takes ~90% CPU during sync]
```

### 2. Check Current Block Height
```bash
bitcoin-cli -testnet4 getblockcount
# Should match https://mempool.space/testnet4 current block
```

### 3. Create LND Wallet (When Bitcoin is synced)
```bash
# Initialize the LND wallet
sudo -u bitcoin lncli create

# You will be prompted for:
# - Wallet password (set something secure)
# - Backup seed phrase (SAVE THIS IN A SECURE LOCATION!)
```

### 4. Unlock Wallet
```bash
# Unlock the wallet with the password you just set
sudo -u bitcoin lncli unlock

# Enter your wallet password when prompted
```

### 5. Start LND
```bash
sudo systemctl start lnd
sudo systemctl enable lnd

# Verify LND is running
lncli getinfo
```

---

## Troubleshooting

### Bitcoin won't start
```bash
sudo systemctl status bitcoin
sudo journalctl -u bitcoin -n 50
# Check for config errors in /data/bitcoin/bitcoin.conf
```

### Bitcoin RPC not responding
```bash
# Give it more time on first startup (can take 10+ minutes)
# Bitcoin is initializing database

# Check if process is running
sudo ps aux | grep bitcoind

# Check ports
sudo ss -tlnp | grep bitcoind
```

### Stuck on "Leaving InitialBlockDownload"
```bash
# Check current vs network block height
bitcoin-cli -testnet4 getblockcount
# vs https://mempool.space/testnet4

# If far behind, check network connection
bitcoin-cli -testnet getnetworkinfo | grep connections
```

---

## Current Configuration Files

**Bitcoin**: `/data/bitcoin/bitcoin.conf`  
**LND**: `/data/lnd/lnd.conf` (not needed until wallet created)  
**Services**: `/etc/systemd/system/bitcoin.service`  
**Logs**: `journalctl -u bitcoin -f`

---

## Key Credentials (SAVE THESE!)

```
Bitcoin RPC:
  User: bitcoin
  Pass: SatsRemit123SecurePass
  Port: 18332 (testnet)

LND Wallet:
  Seed phrase: (WILL BE GENERATED - SAVE IMMEDIATELY!)
  Password: (You will set this)

Location:
  Bitcoin: /data/bitcoin
  LND: /data/lnd
```

---

## Commands Reference

```bash
# Bitcoin
bitcoin-cli -testnet ping
bitcoin-cli -testnet getblockcount
bitcoin-cli -testnet getblockchaininfo
bitcoin-cli -testnet getnewaddress

# System
sudo systemctl start bitcoin
sudo systemctl restart bitcoin
sudo systemctl status bitcoin
sudo journalctl -u bitcoin -f

# Once LND is running
lncli getinfo
lncli walletbalance
```

---

**⏭️ Next**: Monitor Bitcoin sync until it reaches current block height, then initialize LND wallet.

**Est. Time**: 2 hours from startup to LND ready for channels
