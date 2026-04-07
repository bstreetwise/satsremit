#!/bin/bash
# SatsRemit: Deploy Backend on LNVPS
# Run AFTER Bitcoin & LND are set up
# Usage: bash deploy_satsremit.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}SatsRemit Backend Deployment${NC}"
echo -e "${GREEN}LNVPS Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Check if Bitcoin is running
if ! pgrep -x "bitcoind" > /dev/null; then
    echo -e "${RED}❌ Bitcoin is not running!${NC}"
    echo "Start Bitcoin first: sudo systemctl start bitcoin"
    exit 1
fi

# Check if LND is running
if ! pgrep -x "lnd" > /dev/null; then
    echo -e "${RED}❌ LND is not running!${NC}"
    echo "Start LND first: sudo systemctl start lnd"
    exit 1
fi

echo -e "${GREEN}✓ Bitcoin and LND running${NC}"

# ========== STEP 1: INSTALL PYTHON & PIP ==========
echo -e "${YELLOW}[1/5] Installing Python dependencies...${NC}"

sudo apt update
sudo apt install -y python3.10 python3-pip python3-venv git

echo -e "${GREEN}✓ Python installed${NC}"

# ========== STEP 2: SETUP PROJECT ==========
echo -e "${YELLOW}[2/5] Setting up SatsRemit project...${NC}"

cd /home/ubuntu
if [ ! -d satsremit ]; then
    git clone https://github.com/satsremit/satsremit.git
    echo -e "${GREEN}✓ Repository cloned${NC}"
else
    echo -e "${YELLOW}Repository already exists, updating...${NC}"
    cd satsremit
    git pull origin main
    cd /home/ubuntu
fi

cd satsremit

echo -e "${GREEN}✓ Project ready${NC}"

# ========== STEP 3: CREATE VIRTUAL ENV ==========
echo -e "${YELLOW}[3/5] Creating Python virtual environment...${NC}"

python3.10 -m venv venv
source venv/bin/activate

echo -e "${GREEN}✓ Virtual environment created${NC}"

# ========== STEP 4: INSTALL DEPENDENCIES ==========
echo -e "${YELLOW}[4/5] Installing Python packages...${NC}"

pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

echo -e "${GREEN}✓ Dependencies installed${NC}"

# ========== STEP 5: CONFIGURE ENVIRONMENT ==========
echo -e "${YELLOW}[5/5] Creating .env configuration...${NC}"

if [ ! -f .env ]; then
    cp .env.example .env
    
    # Update with LNVPS defaults
    sed -i 's|DATABASE_URL=.*|DATABASE_URL=postgresql://satsremit:satsremit_dev_password@localhost:5432/satsremit|' .env
    sed -i 's|REDIS_URL=.*|REDIS_URL=redis://localhost:6379/0|' .env
    sed -i 's|LND_REST_URL=.*|LND_REST_URL=https://127.0.0.1:8080|' .env
    sed -i 's|LND_MACAROON_PATH=.*|LND_MACAROON_PATH=/data/lnd/data/chain/bitcoin/testnet/admin.macaroon|' .env
    sed -i 's|LND_CERT_PATH=.*|LND_CERT_PATH=/data/lnd/tls.cert|' .env
    
    echo -e "${YELLOW}⚠️  .env created. Please update with your values:${NC}"
    echo "  - Africa's Talking API key"
    echo "  - Bitcoin RPC password"
    echo "  - JWT secret key"
    echo "  - etc."
    echo ""
    echo "Edit: .env"
else
    echo -e "${GREEN}✓ .env already exists${NC}"
fi

# ========== INSTALL POSTGRESQL & REDIS ==========
echo -e "${YELLOW}Installing PostgreSQL & Redis...${NC}"

# PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# Redis
sudo apt install -y redis-server

# Start services
sudo systemctl start postgresql
sudo systemctl start redis-server
sudo systemctl enable postgresql
sudo systemctl enable redis-server

echo -e "${GREEN}✓ PostgreSQL and Redis installed${NC}"

# ========== DATABASE SETUP ==========
echo -e "${YELLOW}Setting up PostgreSQL database...${NC}"

sudo -u postgres psql << EOF
CREATE DATABASE satsremit;
CREATE USER satsremit WITH ENCRYPTED PASSWORD 'satsremit_dev_password';
ALTER ROLE satsremit SET client_encoding TO 'utf8';
ALTER ROLE satsremit SET default_transaction_isolation TO 'read committed';
ALTER ROLE satsremit SET default_transaction_deferrable TO on;
ALTER ROLE satsremit SET default_transaction_read_committed TO on;
GRANT ALL PRIVILEGES ON DATABASE satsremit TO satsremit;
EOF

echo -e "${GREEN}✓ PostgreSQL database created${NC}"

# ========== INITIALIZE DATABASE TABLES ==========
echo -e "${YELLOW}Initializing database schema...${NC}"

source venv/bin/activate
python -c "
from src.db.database import get_db_manager
db_manager = get_db_manager()
db_manager.create_tables()
print('✓ Database tables created')
"

echo -e "${GREEN}✓ Database initialized${NC}"

# ========== CREATE SYSTEMD SERVICE ==========
echo -e "${YELLOW}Creating systemd service...${NC}"

cat > /tmp/satsremit.service << 'EOF'
[Unit]
Description=SatsRemit Backend API
After=network.target postgresql.service redis-server.service
Requires=postgresql.service redis-server.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/satsremit
Environment="PATH=/home/ubuntu/satsremit/venv/bin"
ExecStart=/home/ubuntu/satsremit/venv/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

sudo cp /tmp/satsremit.service /etc/systemd/system/satsremit.service
sudo systemctl daemon-reload
sudo systemctl enable satsremit

echo -e "${GREEN}✓ Systemd service created${NC}"

# ========== SUMMARY ==========
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo ""
echo "1. Edit configuration:"
echo "   nano /home/ubuntu/satsremit/.env"
echo ""
echo "2. Check configuration:"
echo "   cat .env"
echo ""
echo "3. Test the application:"
echo "   source venv/bin/activate"
echo "   python -m uvicorn src.main:app --reload"
echo ""
echo "4. Start as service:"
echo "   sudo systemctl start satsremit"
echo "   sudo systemctl enable satsremit"
echo ""
echo "5. View logs:"
echo "   sudo journalctl -u satsremit -f"
echo ""
echo "6. Access API:"
echo "   http://localhost:8000/api/docs"
echo ""
echo -e "${YELLOW}Configuration to Update:${NC}"
cat .env | grep -E "^[A-Z_]+" | head -20
echo ""
echo -e "${GREEN}Setup complete!${NC}"
