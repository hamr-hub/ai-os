#!/bin/bash
# Comprehensive test script for ports 3000 and 30000
# Tests all API endpoints and functionality

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS_COUNT=0
FAIL_COUNT=0

pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    PASS_COUNT=$((PASS_COUNT + 1))
}

fail() {
    echo -e "${RED}[FAIL]${NC} $1: $2"
    FAIL_COUNT=$((FAIL_COUNT + 1))
}

info() {
    echo -e "${YELLOW}[INFO]${NC} $1"
}

# Test function with timeout
test_endpoint() {
    local name="$1"
    local url="$2"
    local expected_code="${3:-200}"
    local extra_headers="$4"
    
    local http_code
    if [ -n "$extra_headers" ]; then
        http_code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 --max-time 10 $extra_headers "$url" 2>/dev/null || echo "000")
    else
        http_code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 --max-time 10 "$url" 2>/dev/null || echo "000")
    fi
    
    if [ "$http_code" = "$expected_code" ]; then
        pass "$name (HTTP $http_code)"
    else
        fail "$name" "Expected HTTP $expected_code, got HTTP $http_code"
    fi
}

# Test function that checks for non-empty JSON response
test_json_endpoint() {
    local name="$1"
    local url="$2"
    local extra_headers="$3"
    
    local response
    if [ -n "$extra_headers" ]; then
        response=$(curl -s --connect-timeout 5 --max-time 10 $extra_headers "$url" 2>/dev/null || echo "")
    else
        response=$(curl -s --connect-timeout 5 --max-time 10 "$url" 2>/dev/null || echo "")
    fi
    
    if [ -n "$response" ] && [ "$response" != "" ]; then
        local is_json
        is_json=$(echo "$response" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null && echo "yes" || echo "no")
        if [ "$is_json" = "yes" ]; then
            pass "$name (Valid JSON response)"
        else
            fail "$name" "Response is not valid JSON"
        fi
    else
        fail "$name" "Empty response"
    fi
}

API_KEY="sk-5cc2c1c54e7b598536231629e912f342"
AUTH_HEADER="-H \"Authorization: Bearer $API_KEY\""

echo "=========================================="
echo "AI OS Web Interface Testing"
echo "=========================================="
echo ""

# ==========================================
# Test Port 3000 (aiclient2api - C端推理)
# ==========================================
echo -e "${YELLOW}=== Testing Port 3000 (aiclient2api) ===${NC}"
echo ""

# Basic page loads
info "Testing basic page loads..."
test_endpoint "Homepage" "http://localhost:3000/" "200"
test_endpoint "Login page" "http://localhost:3000/login.html" "200"
test_endpoint "Static CSS" "http://localhost:3000/app/base.css" "200"

# API endpoints with auth
info "Testing API endpoints (with authentication)..."
test_json_endpoint "GPU Monitor API" "http://localhost:3000/api/gpu-monitor" "" "$AUTH_HEADER"
test_json_endpoint "Model Switch API" "http://localhost:3000/api/model-switch/models" "" "$AUTH_HEADER"
test_json_endpoint "Engine API" "http://localhost:3000/api/engine/status" "" "$AUTH_HEADER"
test_json_endpoint "Config API" "http://localhost:3000/api/config" "" "$AUTH_HEADER"
test_json_endpoint "Health API" "http://localhost:3000/api/health/status" "" "$AUTH_HEADER"

# v1 API (inference endpoints)
info "Testing v1 API endpoints..."
test_json_endpoint "v1/models" "http://localhost:3000/v1/models" "" "-H \"Authorization: Bearer $API_KEY\""

# Plugin resources
info "Testing plugin resources..."
test_endpoint "AI-OS Manager inject.js" "http://localhost:3000/plugins/ai-os-manager/inject.js" "200"
test_endpoint "AI-OS Manager styles.css" "http://localhost:3000/plugins/ai-os-manager/styles.css" "200"

echo ""

# ==========================================
# Test Port 30000 (Frontend - B端管控)
# ==========================================
echo -e "${YELLOW}=== Testing Port 30000 (Frontend B-端管控面板) ===${NC}"
echo ""

# Basic page loads
info "Testing basic page loads..."
test_endpoint "Homepage" "http://localhost:30000/" "200"
test_endpoint "index.html" "http://localhost:30000/index.html" "200"

# API proxy endpoints (through nginx to Python backend)
info "Testing API proxy endpoints..."
test_json_endpoint "GPU Summary" "http://localhost:30000/api/gpu/summary" ""
test_json_endpoint "Models List" "http://localhost:30000/api/models" ""
test_json_endpoint "Default Model" "http://localhost:30000/api/default-model" ""
test_json_endpoint "Models Pool" "http://localhost:30000/api/models/pool?filter=all&page=1&page_size=50" ""
test_json_endpoint "Models Downloads" "http://localhost:30000/api/models/downloads" ""

# Health endpoint (Go backend)
info "Testing health endpoints (Go backend)..."
test_json_endpoint "Health" "http://localhost:30000/api/health" ""

# V1 proxy endpoints
info "Testing v1 proxy endpoints..."
test_json_endpoint "v1/models" "http://localhost:30000/v1/models" ""

# WebSocket
info "Testing WebSocket endpoint..."
test_endpoint "WebSocket download" "http://localhost:30000/ws/download" "101"

# Direct backend tests (bypass nginx)
info "Testing direct backend endpoints..."
test_json_endpoint "Direct Python GPU" "http://localhost:35000/manage/gpu/summary" ""
test_json_endpoint "Direct Python Models" "http://localhost:35000/manage/models" ""
test_json_endpoint "Direct Go Health" "http://localhost:35001/health" ""
test_json_endpoint "Direct Go GPU" "http://localhost:35001/manage/gpu/summary" ""

echo ""

# ==========================================
# Summary
# ==========================================
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo -e "Passed: ${GREEN}$PASS_COUNT${NC}"
echo -e "Failed: ${RED}$FAIL_COUNT${NC}"
echo ""

if [ $FAIL_COUNT -gt 0 ]; then
    echo -e "${RED}Some tests failed. Check the output above for details.${NC}"
    exit 1
else
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
fi
