#!/bin/bash

###############################################################################
# SatsRemit Deployment Script
# Automates: local commit → GitHub push → VPS pull → service restart
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
LOCAL_REPO="/home/satsinaction/satsremit"
VPS_HOST="ubuntu@vm-1327.lnvps.cloud"
VPS_DEPLOY_PATH="/opt/satsremit"
GITHUB_REMOTE="origin"
BRANCH="main"

###############################################################################
# Functions
###############################################################################

print_header() {
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}$1${NC}"
    echo -e "${GREEN}========================================${NC}"
}

print_step() {
    echo -e "${YELLOW}→ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

###############################################################################
# Step 1: Local Repository Check
###############################################################################

print_header "Step 1: Local Repository Check"

cd "$LOCAL_REPO"
print_step "Checking git status..."

if ! git rev-parse --git-dir > /dev/null 2>&1; then
    print_error "Not a git repository: $LOCAL_REPO"
    exit 1
fi

print_success "Git repository verified"

###############################################################################
# Step 2: Local Commit (if there are changes)
###############################################################################

print_header "Step 2: Local Changes"

if [ -z "$(git status --porcelain)" ]; then
    print_success "No local changes to commit"
else
    print_step "Uncommitted changes detected:"
    git status --short
    
    read -p "Commit these changes? (y/n): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "Enter commit message: " commit_msg
        
        if [ -z "$commit_msg" ]; then
            commit_msg="Update: $(date +'%Y-%m-%d %H:%M:%S')"
        fi
        
        git add -A
        git commit -m "$commit_msg"
        print_success "Changes committed: $commit_msg"
    else
        print_error "Deployment cancelled - please commit or stash changes"
        exit 1
    fi
fi

###############################################################################
# Step 3: Push to GitHub
###############################################################################

print_header "Step 3: Push to GitHub"

print_step "Pushing to $GITHUB_REMOTE/$BRANCH..."

if git push $GITHUB_REMOTE $BRANCH; then
    print_success "Pushed to GitHub successfully"
else
    print_error "Failed to push to GitHub"
    exit 1
fi

###############################################################################
# Step 4: VPS Deployment
###############################################################################

print_header "Step 4: VPS Deployment"

print_step "Connecting to VPS ($VPS_HOST)..."

# Check VPS connectivity
if ! ssh -o ConnectTimeout=5 $VPS_HOST "echo 'VPS connection OK'" > /dev/null 2>&1; then
    print_error "Cannot connect to VPS: $VPS_HOST"
    exit 1
fi

print_success "VPS connection established"

print_step "Deploying to $VPS_DEPLOY_PATH..."

# Run deployment on VPS
ssh $VPS_HOST << 'VPSCOMMAND'
    set -e
    
    echo "Checking if git is initialized in /opt/satsremit..."
    
    if [ ! -d /opt/satsremit/.git ]; then
        echo "Git not initialized - initializing repository..."
        
        # Clone to temp location with proper permissions
        cd /tmp
        git clone https://github.com/bstreetwise/satsremit.git satsremit-fresh
        
        # Move to /opt with sudo if needed
        if [ -d /opt/satsremit ]; then
            sudo rm -rf /opt/satsremit-old
            sudo mv /opt/satsremit /opt/satsremit-old
        fi
        sudo mv /tmp/satsremit-fresh /opt/satsremit
        sudo chown -R ubuntu:ubuntu /opt/satsremit
    fi
    
    cd /opt/satsremit
    echo "Fetching latest changes from GitHub..."
    git fetch origin
    
    echo "Pulling from main..."
    git pull origin main
    
    echo "Updating static files..."
    
    echo "Deployment complete on VPS"
VPSCOMMAND

print_success "VPS deployment completed"

###############################################################################
# Step 5: Restart Services (Optional)
###############################################################################

print_header "Step 5: Service Restart"

read -p "Restart Uvicorn service on VPS? (y/n): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_step "Restarting services..."
    
    ssh $VPS_HOST << 'RESTARTCOMMAND'
        # Kill existing uvicorn process
        pkill -f "uvicorn.*satsremit" || true
        sleep 1
        
        # Restart with proper environment
        cd /opt/satsremit
        
        # Check if virtualenv exists
        if [ -f venv/bin/uvicorn ]; then
            echo "Starting Uvicorn from virtualenv..."
            nohup venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 2 > /tmp/uvicorn.log 2>&1 &
        else
            echo "Virtual environment not found at /opt/satsremit/venv"
            echo "Trying to use system uvicorn..."
            nohup /opt/satsremit/venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 2 > /tmp/uvicorn.log 2>&1 &
        fi
        
        sleep 2
        ps aux | grep uvicorn | grep -v grep && echo "Uvicorn is running" || echo "Uvicorn may have failed to start - check /tmp/uvicorn.log"
RESTARTCOMMAND
    
    print_success "Services restarted"
else
    print_step "Skipping service restart"
    echo "Manual restart may be needed for changes to take effect"
fi

###############################################################################
# Deployment Complete
###############################################################################

print_header "Deployment Complete!"

echo ""
echo "Summary:"
echo "  Local:  ✓ Changes committed and pushed to GitHub"
echo "  GitHub: ✓ Latest code on origin/main"
echo "  VPS:    ✓ Latest code deployed to $VPS_DEPLOY_PATH"
echo ""
echo "Website: https://satsremit.com"
echo ""

# Show recent commits
echo "Recent commits:"
git log --oneline -3

echo ""
print_success "Deployment finished successfully!"
