#!/bin/bash

# Monitor SatsRemit background tasks
# Usage: bash scripts/monitor_tasks.sh [COMMAND]
# Commands: status, active, workers, stats, queue, retry

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PATH="${PROJECT_ROOT}/venv"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

COMMAND=${1:-status}

if [ ! -d "$VENV_PATH" ]; then
    echo -e "${RED}❌ Virtual environment not found${NC}"
    exit 1
fi

source "$VENV_PATH/bin/activate"
cd "$PROJECT_ROOT"

case "$COMMAND" in
    status)
        echo -e "${BLUE}📊 Celery Status${NC}"
        echo ""
        echo -e "${CYAN}Active Workers:${NC}"
        celery -A src.core.celery inspect active | python -m json.tool
        echo ""
        echo -e "${CYAN}Registered Tasks:${NC}"
        celery -A src.core.celery inspect registered | python -m json.tool | head -50
        ;;
    
    active)
        echo -e "${BLUE}🔄 Active Tasks${NC}"
        echo ""
        celery -A src.core.celery inspect active | python -m json.tool
        ;;
    
    workers)
        echo -e "${BLUE}👷 Worker Information${NC}"
        echo ""
        celery -A src.core.celery inspect stats | python -m json.tool
        ;;
    
    stats)
        echo -e "${BLUE}📈 Worker Statistics${NC}"
        echo ""
        celery -A src.core.celery inspect stats | python -m json.tool
        ;;
    
    queue)
        echo -e "${BLUE}📦 Queue Information${NC}"
        echo ""
        echo -e "${CYAN}Queue lengths:${NC}"
        redis-cli LLEN celery &
        redis-cli LLEN celery.invoices &
        redis-cli LLEN celery.settlements &
        redis-cli LLEN celery.verification &
        redis-cli LLEN celery.webhooks &
        wait
        ;;
    
    retry)
        echo -e "${BLUE}🔄 Retrying Failed Tasks${NC}"
        echo ""
        # Get all failed tasks from Redis and retry them
        echo -e "${CYAN}Finding failed tasks...${NC}"
        FAILED=$(redis-cli KEYS "celery-task-meta-*" | xargs -I {} sh -c 'RESULT=$(redis-cli GET {}) && echo "$RESULT" | grep -q "FAILURE" && echo {}')
        echo "Found $(echo "$FAILED" | wc -l) failed tasks"
        ;;
    
    logs-api)
        echo -e "${BLUE}📋 API Logs (live)${NC}"
        tail -f /var/log/satsremit/api.log
        ;;
    
    logs-worker)
        echo -e "${BLUE}📋 Worker Logs (live)${NC}"
        tail -f /var/log/satsremit/celery-worker.log
        ;;
    
    logs-beat)
        echo -e "${BLUE}📋 Beat Logs (live)${NC}"
        tail -f /var/log/satsremit/celery-beat.log
        ;;
    
    tasks)
        echo -e "${BLUE}📋 Running Tasks${NC}"
        echo ""
        celery -A src.core.celery inspect active --json | jq '.[]' | head -100
        ;;
    
    scheduled)
        echo -e "${BLUE}📅 Scheduled Tasks (Beat)${NC}"
        echo ""
        celery -A src.core.celery inspect scheduled | python -m json.tool
        ;;
    
    purge)
        echo -e "${YELLOW}⚠️  Purging all tasks from queue${NC}"
        read -p "Are you sure? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            celery -A src.core.celery purge
            echo -e "${GREEN}✓ Queues purged${NC}"
        fi
        ;;
    
    reset)
        echo -e "${YELLOW}⚠️  Resetting Celery Beat schedule${NC}"
        read -p "Are you sure? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -f data/celery-beat-schedule
            echo -e "${GREEN}✓ Schedule reset${NC}"
        fi
        ;;
    
    flower)
        echo -e "${BLUE}🌸 Starting Flower Web UI...${NC}"
        echo "   URL: http://localhost:5555"
        celery -A src.core.celery flower --port=5555
        ;;
    
    help|*)
        echo -e "${MAGENTA}SatsRemit Task Monitoring${NC}"
        echo ""
        echo -e "${CYAN}Usage: bash scripts/monitor_tasks.sh [COMMAND]${NC}"
        echo ""
        echo -e "${GREEN}Monitor Commands:${NC}"
        echo "  status        - Show worker and task status"
        echo "  active        - Show currently active tasks"
        echo "  workers       - Show worker information"
        echo "  stats         - Show worker statistics"
        echo "  queue         - Show queue lengths"
        echo "  tasks         - Show running tasks"
        echo "  scheduled     - Show scheduled (beat) tasks"
        echo ""
        echo -e "${GREEN}Log Commands:${NC}"
        echo "  logs-api      - Show API logs (live tail)"
        echo "  logs-worker   - Show Worker logs (live tail)"
        echo "  logs-beat     - Show Beat logs (live tail)"
        echo ""
        echo -e "${GREEN}Management Commands:${NC}"
        echo "  retry         - Retry failed tasks"
        echo "  purge         - Purge all tasks (careful!)"
        echo "  reset         - Reset Beat schedule"
        echo "  flower        - Start Flower web UI (http://localhost:5555)"
        echo ""
        echo -e "${YELLOW}Examples:${NC}"
        echo "  bash scripts/monitor_tasks.sh active"
        echo "  bash scripts/monitor_tasks.sh logs-worker"
        echo "  bash scripts/monitor_tasks.sh flower"
        ;;
esac
