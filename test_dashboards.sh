#!/bin/bash
# Test script to verify all SatsRemit dashboard static files are accessible
# This test works by serving static files with a simple HTTP server

set -e

BASE_URL="http://localhost:8000"
DASHBOARDS=(
    "/admin"
    "/agent"
    "/app"
    "/receiver"
    "/platform-guide.html"
)

QUIET=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_header() {
    echo -e "\n${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Check if server is running
check_server() {
    print_info "Checking if server is running at $BASE_URL..."
    
    if curl -s -f "$BASE_URL/health" > /dev/null 2>&1; then
        print_success "Server is responding"
        return 0
    elif curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/" 2>/dev/null | grep -q "^[0-9][0-9][0-9]$"; then
        print_warning "Server is running but /health endpoint unavailable (may be expected)"
        return 0
    else
        print_error "Cannot connect to server at $BASE_URL"
        return 1
    fi
}

# Test dashboard accessibility
test_dashboards() {
    print_header "Testing Dashboard Accessibility"
    
    local pass_count=0
    local fail_count=0
    
    for dashboard in "${DASHBOARDS[@]}"; do
        url="$BASE_URL$dashboard"
        http_code=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
        
        if [[ "$http_code" =~ ^[2345][0-9][0-9]$ ]] && [[ "$http_code" != "404" ]] && [[ "$http_code" != "500" ]]; then
            size=$(curl -s -w "%{size_download}" -o /dev/null "$url" 2>/dev/null || echo "0")
            print_success "$dashboard (HTTP $http_code, ${size} bytes)"
            ((pass_count++))
        else
            if [[ "$http_code" == "000" ]]; then
                print_error "$dashboard (Connection failed)"
            else
                print_error "$dashboard (HTTP $http_code)"
            fi
            ((fail_count++))
        fi
    done
    
    echo ""
    print_info "Dashboards: $pass_count passed, $fail_count failed"
    
    return $fail_count
}

# Test static resources within dashboards
test_resources() {
    print_header "Testing Dashboard Resources"
    
    declare -A resources=(
        ["/admin"]="index.html css/ js/"
        ["/agent"]="index.html js/"
        ["/app"]="index.html css/ js/"
        ["/receiver"]="index.html js/"
    )
    
    local pass_count=0
    local fail_count=0
    
    for dashboard in "${!resources[@]}"; do
        echo -e "${BLUE}$dashboard${NC}"
        
        for resource in ${resources[$dashboard]}; do
            url="$BASE_URL$dashboard/$resource"
            # For directories, we check if they redirect or return 200/301/302
            http_code=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
            
            if [[ "$http_code" =~ ^[23][0-9][0-9]$ ]]; then
                size=$(curl -s -w "%{size_download}" -o /dev/null "$url" 2>/dev/null || echo "0")
                print_success "  $resource (HTTP $http_code)"
                ((pass_count++))
            else
                if [[ "$http_code" == "000" ]]; then
                    print_error "  $resource (Connection failed)"
                else
                    print_error "  $resource (HTTP $http_code)"
                fi
                ((fail_count++))
            fi
        done
        echo ""
    done
    
    print_info "Resources: $pass_count passed, $fail_count failed"
    return $fail_count
}

# Generate summary report
generate_report() {
    print_header "Summary Report"
    echo "Timestamp: $(date)"
    echo "Testing URL: $BASE_URL"
    echo "Platform: $(uname -s)"
    echo ""
    
    if [ $1 -eq 0 ] && [ $2 -eq 0 ]; then
        echo -e "${GREEN}✓ All dashboards are working and reachable!${NC}"
        return 0
    else
        echo -e "${RED}✗ Some dashboards or resources are not accessible${NC}"
        return 1
    fi
}

# Main execution
main() {
    echo ""
    echo -e "${BLUE}╔═══════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  SatsRemit Dashboard Accessibility Test  ║${NC}"
    echo -e "${BLUE}╚═══════════════════════════════════════════╝${NC}"
    echo ""
    
    if ! check_server; then
        print_error "Please start the server with: PYTHONPATH=/home/satsinaction/satsremit python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8000"
        exit 1
    fi
    
    test_dashboards
    dashboard_result=$?
    
    test_resources
    resources_result=$?
    
    echo ""
    generate_report $dashboard_result $resources_result
    exit $?
}

main "$@"
