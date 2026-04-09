#!/bin/bash

# Start Celery Beat Scheduler for SatsRemit
# Usage: bash scripts/start_celery_beat.sh

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PATH="${PROJECT_ROOT}/venv"
LOG_DIR="/var/log/satsremit"
SCHEDULE_FILE="${PROJECT_ROOT}/data/celery-beat-schedule"
PID_FILE="/run/satsremit-celery-beat.pid"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting SatsRemit Celery Beat Scheduler${NC}"

# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo -e "${RED}❌ Virtual environment not found at $VENV_PATH${NC}"
    exit 1
fi

# Activate virtual environment
source "$VENV_PATH/bin/activate"

# Create log directory if it doesn't exist
if [ ! -d "$LOG_DIR" ]; then
    mkdir -p "$LOG_DIR"
fi

# Create data directory for schedule file
if [ ! -d "${PROJECT_ROOT}/data" ]; then
    mkdir -p "${PROJECT_ROOT}/data"
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
LOGLEVEL=${1:-info}  # Default: info
SCHEDULER=${2:-beat}  # Default: built-in beat

echo -e "${BLUE}⚙️  Configuration:${NC}"
echo "   Log Level: $LOGLEVEL"
echo "   Scheduler: $SCHEDULER"
echo "   Schedule File: $SCHEDULE_FILE"
echo ""

# Check if another Beat instance is running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo -e "${YELLOW}⚠️  Celery Beat already running (PID: $OLD_PID)${NC}"
        echo "   Kill it with: kill $OLD_PID"
        exit 1
    fi
fi

# Start Celery Beat
echo -e "${GREEN}Starting Celery Beat scheduler...${NC}"
celery -A src.core.celery beat \
    --loglevel=$LOGLEVEL \
    --logfile="$LOG_DIR/celery-beat.log" \
    --pidfile=$PID_FILE \
    --schedule="$SCHEDULE_FILE"

echo -e "${YELLOW}Celery Beat scheduler stopped${NC}"
