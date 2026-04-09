#!/bin/bash
# SatsRemit: Bitcoin & LND Setup on LNVPS (Testnet)
# Run as: bash setup_bitcoin_lnd.sh
# Tested on: Ubuntu 22.04

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}SatsRemit Bitcoin + LND Setup${NC}"
echo -e "${GREEN}LNVPS Testnet Installation${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if running as root (recommended)
if [[ $EUID -ne 0 ]]; then
   echo -e "${YELLOW}Note: Running as non-root. Some operations may require sudo.${NC}"
   SUDO="sudo"
else
   SUDO=""
fi

# ========== STEP 1: SYSTEM PREPARATION ==========
echo -e "${YELLOW}[1/8] Updating system packages...${NC}"
$SUDO apt update
$SUDO apt upgrade -y
$SUDO apt install -y \
    curl wget git build-essential \
    autoconf automake libtool pkg-config \
    libssl-dev libgmp-dev libsqlite3-dev

# ========== STEP 2: CREATE USER & DIRECTORIES ==========
echo -e "${YELLOW}[2/8] Setting up data directories...${NC}"

# Create bitcoin user if doesn't exist
if ! id "bitcoin" &>/dev/null; then
    $SUDO useradd -m -s /bin/bash bitcoin
fi

# Create data directories
$SUDO mkdir -p /data/bitcoin
$SUDO mkdir -p /data/lnd
$SUDO chown -R bitcoin:bitcoin /data/
$SUDO chmod 755 /data/bitcoin /data/lnd

echo -e "${GREEN}✓ Directories created at /data/bitcoin and /data/lnd${NC}"

# ========== STEP 3: REMOVE OLD INSTALLATION ==========
echo -e "${YELLOW}[3/8] Cleaning up old Bitcoin/LND installation...${NC}"

$SUDO systemctl stop bitcoin 2>/dev/null || true
$SUDO systemctl stop lnd 2>/dev/null || true
$SUDO systemctl disable bitcoin 2>/dev/null || true
$SUDO systemctl disable lnd 2>/dev/null || true

$SUDO rm -rf /opt/bitcoin* 2>/dev/null || true
$SUDO rm -rf /opt/lnd* 2>/dev/null || true
$SUDO rm -f /etc/systemd/system/bitcoin.service
$SUDO rm -f /etc/systemd/system/lnd.service

# Backup and clean blockchain data (WARNING)
echo -e "${YELLOW}Cleaning blockchain data (this removes the blockchain)...${NC}"
$SUDO rm -rf /data/bitcoin/testnet3
$SUDO rm -rf /data/bitcoin/regtest
$SUDO rm -f /data/bitcoin/.cookie
$SUDO rm -f /data/bitcoin/bitcoin.conf.old

# Clean LND data
$SUDO rm -rf /data/lnd/chain
$SUDO rm -rf /data/lnd/logs
$SUDO rm -f /data/lnd/lnd.conf.old

echo -e "${GREEN}✓ Old installation cleaned${NC}"

# ========== STEP 4: INSTALL BITCOIN CORE ==========
echo -e "${YELLOW}[4/8] Installing Bitcoin Core (latest)...${NC}"

# Get latest version
BITCOIN_VERSION="26.0"
BITCOIN_URL="https://bitcoincore.org/bin/bitcoin-core-${BITCOIN_VERSION}/bitcoin-${BITCOIN_VERSION}-x86_64-linux-gnu.tar.gz"

echo "Downloading Bitcoin Core ${BITCOIN_VERSION}..."
# Retry download with timeout
for attempt in 1 2 3; do
    echo "Download attempt $attempt/3..."
    if wget --timeout=60 -O /tmp/bitcoin-${BITCOIN_VERSION}.tar.gz "$BITCOIN_URL"; then
        if tar -tzf /tmp/bitcoin-${BITCOIN_VERSION}.tar.gz > /dev/null 2>&1; then
            echo "✓ Download verified successfully"
            break
        else
            echo "✗ Corrupted download, retrying..."
            rm -f /tmp/bitcoin-${BITCOIN_VERSION}.tar.gz
            if [ $attempt -eq 3 ]; then
                echo -e "${RED}Download failed after 3 attempts${NC}"
                exit 1
            fi
        fi
    else
        if [ $attempt -eq 3 ]; then
            echo -e "${RED}Download failed after 3 attempts${NC}"
            exit 1
        fi
    fi
done

$SUDO mkdir -p /opt
$SUDO tar -xzf /tmp/bitcoin-${BITCOIN_VERSION}.tar.gz -C /opt/
$SUDO mv /opt/bitcoin-${BITCOIN_VERSION} /opt/bitcoin
$SUDO chown -R bitcoin:bitcoin /opt/bitcoin
$SUDO chmod +x /opt/bitcoin/bin/*

# Create symlinks for easy access
$SUDO ln -sf /opt/bitcoin/bin/bitcoind /usr/local/bin/bitcoind
$SUDO ln -sf /opt/bitcoin/bin/bitcoin-cli /usr/local/bin/bitcoin-cli

echo -e "${GREEN}✓ Bitcoin Core installed: $(/usr/local/bin/bitcoind --version | head -1)${NC}"

# ========== STEP 5: CONFIGURE BITCOIN ==========
echo -e "${YELLOW}[5/8] Configuring Bitcoin (Testnet, Pruned)...${NC}"

cat > /tmp/bitcoin.conf << 'EOF'
# SatsRemit Bitcoin Configuration
# Testnet Setup with Pruning

# Network
testnet=1
server=1
listen=1

# RPC Server
rpcuser=bitcoin
rpcpassword=changeMe123!@#
rpcbind=127.0.0.1
rpcport=18332
rpc=1

# Pruning (550 MB for testnet)
# 0 = no pruning, 1 = pruning enabled
prune=550

# Performance
maxconnections=100
maxuploadtarget=5000

# Indexing
txindex=1
blockfilterindex=0

# Logging
debug=rpc
debug=net

# Data directory
datadir=/data/bitcoin

# Wallet
disablewallet=0
wallet=default_wallet

# Mining (testnet)
generatenewaddress=1

# Connection pool
dbcache=512
EOF

$SUDO cp /tmp/bitcoin.conf /data/bitcoin/bitcoin.conf
$SUDO chown bitcoin:bitcoin /data/bitcoin/bitcoin.conf
$SUDO chmod 600 /data/bitcoin/bitcoin.conf

echo -e "${GREEN}✓ Bitcoin configuration created${NC}"
echo "  - Testnet enabled"
echo "  - Pruning: 550 MB"
echo "  - RPC user: bitcoin"
echo "  - Data: /data/bitcoin"

# ========== STEP 6: INSTALL LND ==========
echo -e "${YELLOW}[6/8] Installing LND...${NC}"

LND_VERSION="0.18.4"
LND_URL="https://github.com/lightningnetwork/lnd/releases/download/v${LND_VERSION}/lnd-linux-amd64-v${LND_VERSION}.tar.gz"

echo "Downloading LND v${LND_VERSION}..."
# Retry download with multiple methods
DOWNLOAD_SUCCESS=0

for attempt in 1 2 3; do
    echo "Download attempt $attempt/3..."
    rm -f /tmp/lnd-${LND_VERSION}.tar.gz
    
    # Try wget first
    if wget --timeout=120 --tries=2 -O /tmp/lnd-${LND_VERSION}.tar.gz "$LND_URL" 2>/dev/null; then
        # Verify file integrity
        FILE_SIZE=$(stat -f%z /tmp/lnd-${LND_VERSION}.tar.gz 2>/dev/null || stat --printf="%s" /tmp/lnd-${LND_VERSION}.tar.gz 2>/dev/null || echo 0)
        if [ "$FILE_SIZE" -gt 1000000 ]; then  # At least 1MB
            if tar -tzf /tmp/lnd-${LND_VERSION}.tar.gz > /dev/null 2>&1; then
                echo "✓ Download verified successfully (Size: $FILE_SIZE bytes)"
                DOWNLOAD_SUCCESS=1
                break
            fi
        fi
    fi
    
    # Try curl as fallback
    if [ $DOWNLOAD_SUCCESS -eq 0 ] && command -v curl &> /dev/null; then
        echo "Retrying with curl..."
        if curl -fL --max-time 120 -o /tmp/lnd-${LND_VERSION}.tar.gz "$LND_URL" 2>/dev/null; then
            FILE_SIZE=$(stat -f%z /tmp/lnd-${LND_VERSION}.tar.gz 2>/dev/null || stat --printf="%s" /tmp/lnd-${LND_VERSION}.tar.gz 2>/dev/null || echo 0)
            if [ "$FILE_SIZE" -gt 1000000 ]; then  # At least 1MB
                if tar -tzf /tmp/lnd-${LND_VERSION}.tar.gz > /dev/null 2>&1; then
                    echo "✓ Download verified successfully (Size: $FILE_SIZE bytes)"
                    DOWNLOAD_SUCCESS=1
                    break
                fi
            fi
        fi
    fi
    
    if [ $attempt -lt 3 ]; then
        echo "✗ Download failed, retrying in 5 seconds..."
        sleep 5
    fi
done

if [ $DOWNLOAD_SUCCESS -eq 0 ]; then
    echo -e "${RED}✗ LND download failed after 3 attempts${NC}"
    echo ""
    echo -e "${YELLOW}MANUAL FALLBACK: Download and copy LND manually:${NC}"
    echo "  1. On your local machine, download:"
    echo "     curl -fL -o /tmp/lnd.tar.gz https://github.com/lightningnetwork/lnd/releases/download/v${LND_VERSION}/lnd-linux-amd64-v${LND_VERSION}.tar.gz"
    echo ""
    echo "  2. Then copy to VPS:"
    echo "     scp /tmp/lnd.tar.gz ubuntu@vm-1327.lnvps.cloud:/tmp/"
    echo ""
    echo "  3. Extract on VPS:"
    echo "     sudo mkdir -p /opt/lnd-extract"
    echo "     sudo tar -xzf /tmp/lnd.tar.gz -C /opt/lnd-extract/"
    echo "     sudo mkdir -p /opt/lnd"
    echo "     sudo cp /opt/lnd-extract/lnd /opt/lnd/"
    echo "     sudo cp /opt/lnd-extract/lncli /opt/lnd/"
    echo "     sudo chown -R bitcoin:bitcoin /opt/lnd"
    echo "     sudo chmod +x /opt/lnd/*"
    echo "     sudo ln -sf /opt/lnd/lnd /usr/local/bin/lnd"
    echo "     sudo ln -sf /opt/lnd/lncli /usr/local/bin/lncli"
    echo ""
    exit 1
fi

$SUDO mkdir -p /opt/lnd-extract
$SUDO tar -xzf /tmp/lnd-${LND_VERSION}.tar.gz -C /opt/lnd-extract/
$SUDO mkdir -p /opt/lnd

# Handle both extraction formats (direct files or nested directory)
if [ -f /opt/lnd-extract/lnd ]; then
    $SUDO cp /opt/lnd-extract/lnd /opt/lnd/
    $SUDO cp /opt/lnd-extract/lncli /opt/lnd/
else
    # Extract from nested directory (lnd-linux-amd64-v0.18.4-beta/)
    $SUDO cp /opt/lnd-extract/lnd-linux-amd64-*/lnd /opt/lnd/
    $SUDO cp /opt/lnd-extract/lnd-linux-amd64-*/lncli /opt/lnd/
fi

$SUDO rm -rf /opt/lnd-extract
$SUDO chown -R bitcoin:bitcoin /opt/lnd
$SUDO chmod +x /opt/lnd/*

# Create symlinks
$SUDO ln -sf /opt/lnd/lnd /usr/local/bin/lnd
$SUDO ln -sf /opt/lnd/lncli /usr/local/bin/lncli

echo -e "${GREEN}✓ LND installed: $(/usr/local/bin/lnd --version)${NC}"

# ========== STEP 7: CONFIGURE LND ==========
echo -e "${YELLOW}[7/8] Configuring LND (Testnet + Hold Invoices)...${NC}"

cat > /tmp/lnd.conf << 'EOF'
# SatsRemit LND Configuration
# Testnet with Hold Invoices

[Application Options]
# Network
bitcoin.testnet=1
bitcoin.active=1

# LND Data
datadir=/data/lnd

# Node identity
alias=SatsRemit-Node
color=#FF6600

# API & RPC
listen=0.0.0.0:9735
rpclisten=127.0.0.1:10009
restlisten=127.0.0.1:8080

# bitcoind RPC
bitcoin.node=bitcoind

[bitcoind]
rpchost=127.0.0.1:18332
rpcuser=bitcoin
rpcpass=changeMe123!@#
zmqpubrawblock=tcp://127.0.0.1:28332
zmqpubrawtx=tcp://127.0.0.1:28333

[Bitcoin]
bitcoin.testnet=1

[protocol]
# Hold Invoice Support (AMP)
protocol.wumbo-channels=true
protocol.anchors=true

[routing]
routing.strict-zombie-pruning=false

# Fees
[invoices]
hodl.invoice.expiry=600

[tlsextradomain]
# Add your domain here for production
EOF

$SUDO cp /tmp/lnd.conf /data/lnd/lnd.conf
$SUDO chown bitcoin:bitcoin /data/lnd/lnd.conf
$SUDO chmod 600 /data/lnd/lnd.conf

echo -e "${GREEN}✓ LND configuration created${NC}"
echo "  - Testnet enabled"
echo "  - REST API: 127.0.0.1:8080"
echo "  - gRPC: 127.0.0.1:10009"
echo "  - Hold invoices: enabled"

# ========== STEP 8: CREATE SYSTEMD SERVICES ==========
echo -e "${YELLOW}[8/8] Setting up systemd services...${NC}"

# Bitcoin Service
cat > /tmp/bitcoin.service << 'EOF'
[Unit]
Description=Bitcoin Core (Testnet)
After=network.target

[Service]
Type=simple
User=bitcoin
Group=bitcoin
WorkingDirectory=/data/bitcoin
ExecStart=/usr/local/bin/bitcoind -conf=/data/bitcoin/bitcoin.conf
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

$SUDO cp /tmp/bitcoin.service /etc/systemd/system/bitcoin.service
$SUDO systemctl daemon-reload

# LND Service
cat > /tmp/lnd.service << 'EOF'
[Unit]
Description=Lightning Network Daemon (Testnet)
After=network.target bitcoin.service
Requires=bitcoin.service

[Service]
Type=simple
User=bitcoin
Group=bitcoin
WorkingDirectory=/data/lnd
ExecStart=/usr/local/bin/lnd --configfile=/data/lnd/lnd.conf
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

$SUDO cp /tmp/lnd.service /etc/systemd/system/lnd.service
$SUDO systemctl daemon-reload

echo -e "${GREEN}✓ Systemd services created${NC}"

# ========== SUMMARY ==========
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Installation Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo ""
echo "1. Start Bitcoin:"
echo "   $SUDO systemctl start bitcoin"
echo "   $SUDO systemctl enable bitcoin"
echo ""
echo "2. Wait for Bitcoin to sync (may take 1-2 hours for testnet)"
echo "   $SUDO journalctl -u bitcoin -f"
echo ""
echo "3. Once Bitcoin is synced, start LND:"
echo "   $SUDO systemctl start lnd"
echo "   $SUDO systemctl enable lnd"
echo ""
echo "4. Initialize LND wallet:"
echo "   sudo -u bitcoin lncli create"
echo ""
echo "5. Check LND status:"
echo "   lncli getinfo"
echo ""
echo -e "${YELLOW}Important Notes:${NC}"
echo "- Bitcoin RPC: user=bitcoin, pass=changeMe123!@# (CHANGE IN PRODUCTION!)"
echo "- Blockchain data: /data/bitcoin (pruned to 550MB)"
echo "- LND data: /data/lnd"
echo "- REST API: http://127.0.0.1:8080"
echo "- Testnet: Enabled"
echo ""
echo -e "${YELLOW}Configuration Files:${NC}"
echo "- Bitcoin: /data/bitcoin/bitcoin.conf"
echo "- LND: /data/lnd/lnd.conf"
echo ""
echo -e "${YELLOW}Systemd Commands:${NC}"
echo "- Start Bitcoin: systemctl start bitcoin"
echo "- Stop Bitcoin: systemctl stop bitcoin"
echo "- Start LND: systemctl start lnd"
echo "- Stop LND: systemctl stop lnd"
echo "- View logs: journalctl -u bitcoin -f"
echo ""
echo -e "${GREEN}Setup script complete! Run the next steps manually.${NC}"
echo ""
