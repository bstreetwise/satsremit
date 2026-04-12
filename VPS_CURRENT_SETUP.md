# VPS Current Setup & Versions

**Last Updated**: April 12, 2026  
**VPS Host**: vm-1327.lnvps.cloud  
**OS**: Ubuntu 22.04 LTS

## Active Services & Versions

### Bitcoin Core
- **Version**: v29.0.0
- **Network**: testnet4
- **RPC Port**: 28332
- **Data Directory**: /data/bitcoin
- **Wallet Balance**: 0.01 BTC (1,000,000 sats)
- **Status**: ✓ Running (synced to chain)

### Lightning Network Daemon (LND)
- **Version**: 0.19.0-beta
- **Network**: testnet4
- **Listen Port**: 9735
- **RPC Port**: 10009
- **Data Directory**: /data/lnd
- **Geyser Block Height**: 129,963
- **Synced**: ✓ Yes (to chain, syncing graph)
- **Peers**: 2 connected
  - OpenNode.com (02eadbd9e755...)
  - aranguren.org (038863cf8ab9...)
- **Status**: ✓ Running

### Supporting Services
- **PostgreSQL 16**: ✓ Running
- **Redis**: ✓ Running (localhost:6379)
- **Nginx**: ✓ Running (4 worker processes)
- **Fail2ban**: ✓ Running
- **Satsremit App (Uvicorn)**: ✓ Running (port 8000, 2 workers)
- **Celery Workers**: ✓ Running (3 processes, concurrency=2 each)
- **Celery Beat**: ✓ Running

## Quick Command Reference

### Bitcoin CLI (Testnet4)
```bash
# Check balance
bc getbalance

# Generate new address
bc getnewaddress

# Get blockchain info
bc getblockchaininfo

# Note: 'bc' is a wrapper for:
# /usr/local/bin/bitcoin-cli -rpcuser=bitcoin -rpcpassword=SatsRemit2026Secure -rpcport=28332
```

### LND CLI (Testnet4)
```bash
# Get node info
ln getinfo

# List peers
ln listpeers

# List channels
ln listchannels

# Check wallet balance
ln walletbalance

# Note: 'ln' is a wrapper for:
# /usr/local/bin/lncli -n testnet4
```

## System Uptime

- **System**: 4 days (since Mon 2026-04-06 21:02:23 UTC)
- **Failed Units**: 0
- **Total Units**: 462 loaded

## Network Configuration

### Bitcoin Core
- **RPC Credentials**:
  - User: `bitcoin`
  - Password: `SatsRemit2026Secure`
- **Testnet4 Port**: 28332
- **ZMQ Pub Block**: tcp://127.0.0.1:28334
- **ZMQ Pub Tx**: tcp://127.0.0.1:28335

### LND
- **Network**: testnet4
- **Node Alias**: BitSpaza
- **Node Color**: #3399ff
- **Public Key**: 026068ae084e81e8f90edeeaa08f5752287927479a048b59fc1d687e3f02e93371
- **RPC Server**: localhost:10009
- **REST Server**: localhost:8080

## Recent Actions

1. ✓ Connected to testnet4 peers:
   - OpenNode.com (capacity: 22.38 BTC)
   - aranguren.org (capacity: 72.54 BTC)

2. ⏳ Pending: Fund wallet with more testnet4 BTC (minimum 0.1 BTC for channel opening)

3. ⏳ Next: Open channels with connected peers

## Important Notes

- **Testnet4 Address**: `tb1q8akdkrlwnev8q9nlk7z6lygcgsz9c7y240azut`
- **Channel Minimum**: 0.1 BTC (10,000,000 sats)
- **Current Wallet**: 0.01 BTC (insufficient for channel)
- **Faucet Address**: Send to `tb1q8akdkrlwnev8q9nlk7z6lygcgsz9c7y240azut` via https://testnet-faucet.mempool.space/

## Systemd Services

All services configured to auto-start on boot:

```bash
# View all services
systemctl list-units --type=service

# Key services:
# - bitcoin.service
# - lnd.service
# - satsremit.service
# - satsremit-worker.service
# - satsremit-beat.service
# - nginx.service
# - postgresql@16-main.service
# - redis-server.service
```

## Configuration Files

- **Bitcoin Config**: `/data/bitcoin/bitcoin.conf`
- **LND Config**: `/data/lnd/lnd.conf`
- **Environment**: `/etc/environment` (contains LNCLI_NETWORK=testnet4)
- **App Config**: `/opt/satsremit/.env`

## Troubleshooting

### Common Commands

```bash
# SSH into VPS
ssh ubuntu@vm-1327.lnvps.cloud

# Check systemd status
systemctl status bitcoin.service
systemctl status lnd.service
systemctl status satsremit.service

# View logs
journalctl -u bitcoin.service -f
journalctl -u lnd.service -f
journalctl -u satsremit.service -f

# Test connectivity
ln listpeers
bc getblockchaininfo
```

### Known Issues & Resolutions

1. **LND on different chain**: 
   - Ensure testnet4 is explicitly set: `LNCLI_NETWORK=testnet4`
   - Verify with: `ln getinfo | grep -E 'chain|testnet'`

2. **Bitcoin-cli RPC auth fails**:
   - Use `bc` wrapper or provide full credentials
   - Credentials saved in `~/.bashrc` function

3. **Channel minimum not met**:
   - Need 0.1 BTC minimum per channel
   - Get testnet4 Bitcoin from faucet
   - Current balance: 0.01 BTC

## Related Files

- [VPS_SETUP.md](VPS_SETUP.md) - Original setup guide
- [SATSREMIT_PRODUCTION_CONFIG.md](SATSREMIT_PRODUCTION_CONFIG.md) - Production configuration
- [scripts/setup_bitcoin_lnd.sh](scripts/setup_bitcoin_lnd.sh) - Automated setup script
