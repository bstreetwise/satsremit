#!/bin/bash

# Start all SatsRemit components (API + Celery Worker + Beat)
# Usage: bash scripts/start_all.sh [API_PORT] [WORKER_CONCURRENCY]
# Example: bash scripts/start_all.sh 8000 4

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PATH="${PROJECT_ROOT}/venv"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

API_PORT=${1:-8000}
WORKER_CONCURRENCY=${2:-4}

echo -e "${BLUE}╔════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   🚀 SatsRemit Complete Startup                    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo -e "${RED}❌ Virtual environment not found at $VENV_PATH${NC}"
    exit 1
fi

source "$VENV_PATH/bin/activate"
cd "$PROJECT_ROOT"

# Pre-flight checks
echo -e "${BLUE}📋 Running pre-flight checks...${NC}"

# Check Redis
if ! redis-cli ping > /dev/null 2>&1; then
    echo -e "${RED}❌ Redis not running${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Redis OK${NC}"

# Check PostgreSQL
if ! psql -U satsremit -d satsremit -c "SELECT 1;" > /dev/null 2>&1; then
    echo -e "${RED}❌ PostgreSQL not accessible${NC}"
    exit 1
fi
echo -e "${GREEN}✓ PostgreSQL OK${NC}"

echo -e "${GREEN}✓ All checks passed!${NC}"
echo ""

# Create log directory
mkdir -p /var/log/satsremit
mkdir -p data

# Start API in background
echo -e "${BLUE}Starting FastAPI server (port $API_PORT)...${NC}"
uvicorn src.main:app \
    --host 0.0.0.0 \
    --port $API_PORT \
    --log-level info \
    > /var/log/satsremit/api.log 2>&1 &
API_PID=$!
echo -e "${GREEN}✓ API started (PID: $API_PID)${NC}"

sleep 2

# Start Celery Worker in background
echo -e "${BLUE}Starting Celery Worker (concurrency: $WORKER_CONCURRENCY)...${NC}"
celery -A src.core.celery worker \
    --loglevel=info \
    --concurrency=$WORKER_CONCURRENCY \
    --logfile=/var/log/satsremit/celery-worker.log \
    --pidfile=/run/celery-worker.pid \
    > /dev/null 2>&1 &
WORKER_PID=$!
echo -e "${GREEN}✓ Celery Worker started (PID: $WORKER_PID)${NC}"

sleep 2

# Start Celery Beat in background
echo -e "${BLUE}Starting Celery Beat...${NC}"
celery -A src.core.celery beat \
    --loglevel=info \
    --logfile=/var/log/satsremit/celery-beat.log \
    --pidfile=/run/celery-beat.pid \
    --schedule=data/celery-beat-schedule \
    > /dev/null 2>&1 &
BEAT_PID=$!
echo -e "${GREEN}✓ Celery Beat started (PID: $BEAT_PID)${NC}"

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   ✅ All services started successfully!            ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${BLUE}📊 Service Information:${NC}"
echo "   API Server: http://localhost:$API_PORT"
echo "   API Docs: http://localhost:$API_PORT/api/docs"
echo "   Health Check: http://localhost:$API_PORT/health"
echo ""
echo "   API PID: $API_PID"
echo "   Worker PID: $WORKER_PID"
echo "   Beat PID: $BEAT_PID"
echo ""

echo -e "${BLUE}📋 Log Files:${NC}"
echo "   API: tail -f /var/log/satsremit/api.log"
echo "   Worker: tail -f /var/log/satsremit/celery-worker.log"
echo "   Beat: tail -f /var/log/satsremit/celery-beat.log"
echo ""

echo -e "${BLUE}🛑 To stop all services:${NC}"
echo "   kill $API_PID $WORKER_PID $BEAT_PID"
echo ""

echo -e "${BLUE}⏳ Services are now running. Press Ctrl+C to stop.${NC}"
echo ""

# Wait for signals
wait
