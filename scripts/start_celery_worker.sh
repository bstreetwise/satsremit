#!/bin/bash

# Start Celery Worker for SatsRemit
# Usage: bash scripts/start_celery_worker.sh

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PATH="${PROJECT_ROOT}/venv"
LOG_DIR="/var/log/satsremit"
PID_FILE="/run/satsremit-celery-worker.pid"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting SatsRemit Celery Worker${NC}"

# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo -e "${RED}❌ Virtual environment not found at $VENV_PATH${NC}"
    exit 1
fi

# Activate virtual environment
source "$VENV_PATH/bin/activate"

# Create log directory if it doesn't exist
if [ -d "$LOG_DIR" ]; then
    mkdir -p "$LOG_DIR"
fi

# Go to project root
cd "$PROJECT_ROOT"

# Check Redis connection
echo -e "${BLUE}🔍 Checking Redis connection...${NC}"
if ! redis-cli ping > /dev/null 2>&1; then
    echo -e "${RED}❌ Redis not running or not accessible${NC}"
    echo "   Start Redis with: redis-server"
    exit 1
fi
echo -e "${GREEN}✓ Redis is accessible${NC}"

# Check PostgreSQL connection
echo -e "${BLUE}🔍 Checking PostgreSQL connection...${NC}"
if ! psql -U satsremit -d satsremit -c "SELECT 1;" > /dev/null 2>&1; then
    echo -e "${RED}❌ PostgreSQL not accessible${NC}"
    echo "   Check database credentials in .env"
    exit 1
fi
echo -e "${GREEN}✓ PostgreSQL is accessible${NC}"

# Parse command line arguments
CONCURRENCY=${1:-4}  # Default: 4 workers
LOGLEVEL=${2:-info}  # Default: info
POOL=${3:-prefork}   # Default: prefork (process-based)

echo -e "${BLUE}⚙️  Configuration:${NC}"
echo "   Concurrency: $CONCURRENCY workers"
echo "   Log Level: $LOGLEVEL"
echo "   Worker Pool: $POOL"
echo ""

# Start Celery worker
echo -e "${GREEN}Starting Celery worker...${NC}"
celery -A src.core.celery worker \
    --loglevel=$LOGLEVEL \
    --concurrency=$CONCURRENCY \
    --pool=$POOL \
    --logfile="$LOG_DIR/celery-worker.log" \
    --pidfile=$PID_FILE \
    --without-gossip \
    --without-mingle \
    --without-heartbeat \
    --task-events \
    --max-tasks-per-child=1000

echo -e "${YELLOW}Celery worker stopped${NC}"
