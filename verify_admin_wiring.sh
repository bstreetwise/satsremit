#!/bin/bash
# Comprehensive verification test for all wired SatsRemit dashboards

set -e

BASE_URL="http://localhost:8000"
RESULTS=()
PASS=0
FAIL=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "\n${BLUE}═══════════════════════════════════════════${NC}"
echo -e "${BLUE}  SatsRemit Dashboards - Complete Wiring Test${NC}"
echo -e "${BLUE}═══════════════════════════════════════════${NC}\n"

# Test function
test_dashboard() {
    local name=$1
    local url=$2
    local expected_content=$3
    
    echo -n "Testing ${name}... "
    
    if response=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null); then
        if [ "$response" = "200" ]; then
            if [ -z "$expected_content" ] || curl -s "$url" | grep -q "$expected_content"; then
                echo -e "${GREEN}✓ PASS${NC}"
                ((PASS++))
                return 0
            else
                echo -e "${RED}✗ FAIL${NC} (content mismatch)"
                ((FAIL++))
                return 1
            fi
        else
            echo -e "${RED}✗ FAIL${NC} (HTTP $response)"
            ((FAIL++))
            return 1
        fi
    else
        echo -e "${RED}✗ FAIL${NC} (connection error)"
        ((FAIL++))
        return 1
    fi
}

# Admin Panel Tests
echo -e "${BLUE}Admin Panel Sections:${NC}"
test_dashboard "Admin Panel (Root)" "$BASE_URL/admin" "Dashboard"
test_dashboard "Admin Panel (Dashboard)" "$BASE_URL/admin" "Agent Management"
test_dashboard "Admin CSS" "$BASE_URL/admin/css/style.css" ""
test_dashboard "Admin API Module" "$BASE_URL/admin/js/api.js" "getVolumeAnalytics"
test_dashboard "Admin UI Module" "$BASE_URL/admin/js/ui-new.js" "navigate_to_section"
test_dashboard "Admin App Module" "$BASE_URL/admin/js/app.js" "DOMContentLoaded"

echo -e "\n${BLUE}External Dashboard Links:${NC}"
test_dashboard "Send Money (/app)" "$BASE_URL/app" ""
test_dashboard "Agent Dashboard (/agent)" "$BASE_URL/agent" ""
test_dashboard "Receiver Portal (/receiver)" "$BASE_URL/receiver" ""
test_dashboard "Platform Guide" "$BASE_URL/platform-guide.html" ""

echo -e "\n${BLUE}Navigation Links in Admin Panel:${NC}"
echo -n "Testing /app link in admin... "
if curl -s "$BASE_URL/admin" | grep -q 'href="/app"'; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((PASS++))
else
    echo -e "${RED}✗ FAIL${NC}"
    ((FAIL++))
fi

echo -n "Testing /agent link in admin... "
if curl -s "$BASE_URL/admin" | grep -q 'href="/agent"'; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((PASS++))
else
    echo -e "${RED}✗ FAIL${NC}"
    ((FAIL++))
fi

echo -n "Testing /receiver link in admin... "
if curl -s "$BASE_URL/admin" | grep -q 'href="/receiver"'; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((PASS++))
else
    echo -e "${RED}✗ FAIL${NC}"
    ((FAIL++))
fi

echo -n "Testing /platform-guide.html link in admin... "
if curl -s "$BASE_URL/admin" | grep -q 'href="/platform-guide.html"'; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((PASS++))
else
    echo -e "${RED}✗ FAIL${NC}"
    ((FAIL++))
fi

# Admin Sections Test
echo -e "\n${BLUE}Admin Panel Sections HTML:${NC}"
echo -n "Testing Dashboard section... "
if curl -s "$BASE_URL/admin" | grep -q 'id="dashboard"'; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((PASS++))
else
    echo -e "${RED}✗ FAIL${NC}"
    ((FAIL++))
fi

echo -n "Testing Agents section... "
if curl -s "$BASE_URL/admin" | grep -q 'id="agents"'; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((PASS++))
else
    echo -e "${RED}✗ FAIL${NC}"
    ((FAIL++))
fi

echo -n "Testing Transfers section... "
if curl -s "$BASE_URL/admin" | grep -q 'id="transfers"'; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((PASS++))
else
    echo -e "${RED}✗ FAIL${NC}"
    ((FAIL++))
fi

echo -n "Testing Settlements section... "
if curl -s "$BASE_URL/admin" | grep -q 'id="settlements"'; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((PASS++))
else
    echo -e "${RED}✗ FAIL${NC}"
    ((FAIL++))
fi

echo -n "Testing Analytics section... "
if curl -s "$BASE_URL/admin" | grep -q 'id="analytics"'; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((PASS++))
else
    echo -e "${RED}✗ FAIL${NC}"
    ((FAIL++))
fi

# Summary
echo ""
echo -e "${BLUE}═══════════════════════════════════════════${NC}"
echo -e "${BLUE}Test Summary${NC}"
echo -e "${BLUE}═══════════════════════════════════════════${NC}"
echo -e "Passed: ${GREEN}$PASS${NC}"
echo -e "Failed: ${RED}$FAIL${NC}"
echo -e "Total:  $((PASS + FAIL))"

if [ $FAIL -eq 0 ]; then
    echo -e "\n${GREEN}✓ All dashboards are fully wired and functional!${NC}\n"
    exit 0
else
    echo -e "\n${RED}✗ Some tests failed${NC}\n"
    exit 1
fi
