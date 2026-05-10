#!/bin/bash

echo "=========================================="
echo "  AI OS 页面按钮功能测试报告"
echo "=========================================="
echo ""
echo "测试时间: $(date)"
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

BASE_URL="http://localhost:3000"
passed=0
failed=0
skipped=0

test_api() {
    local method=$1
    local endpoint=$2
    local description=$3
    local body=$4
    
    echo -e "${BLUE}[测试]${NC} $description"
    echo -e "  端点: $method $endpoint"
    
    if [ -z "$body" ]; then
        response=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" "$BASE_URL$endpoint")
    else
        response=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" -H "Content-Type: application/json" -d "$body" "$BASE_URL$endpoint")
    fi
    
    if [ "$response" -eq 200 ] || [ "$response" -eq 204 ]; then
        echo -e "  ${GREEN}✓ 通过${NC} (状态码: $response)"
        ((passed++))
    else
        echo -e "  ${RED}✗ 失败${NC} (状态码: $response)"
        ((failed++))
    fi
    echo ""
}

echo "=========================================="
echo "  1. GPU 监控功能测试"
echo "=========================================="
echo ""

test_api "GET" "/api/gpu-monitor/info" "GPU监控 - 刷新按钮 (获取GPU信息)"
test_api "GET" "/api/gpu-monitor/status" "GPU监控 - 获取监控状态"
test_api "POST" "/api/gpu-monitor/start" "GPU监控 - 启动自动监控按钮"
test_api "POST" "/api/gpu-monitor/stop" "GPU监控 - 停止自动监控按钮"

echo ""
echo "=========================================="
echo "  2. 模型管理功能测试"
echo "=========================================="
echo ""

test_api "GET" "/api/model-switch/models" "模型管理 - 刷新按钮 (获取模型列表)"
test_api "GET" "/api/model-switch/aggregated" "模型管理 - 获取聚合模型信息"
test_api "GET" "/api/model-switch/switch-status" "模型管理 - 获取切换状态"

echo ""
echo "=========================================="
echo "  3. 引擎管理功能测试"
echo "=========================================="
echo ""

test_api "GET" "/api/engine/status" "引擎管理 - 刷新引擎状态"
test_api "POST" "/api/engine/switch" "引擎管理 - 切换引擎按钮" '{"model_name":"Gemma-4-31B-Abliterated","engine_type":"vllm","port":8000}'

echo ""
echo "=========================================="
echo "  4. 模型下载功能测试"
echo "=========================================="
echo ""

test_api "GET" "/api/model-switch/downloads" "下载管理 - 获取下载任务列表"

echo ""
echo "=========================================="
echo "  5. 健康检查测试"
echo "=========================================="
echo ""

test_api "GET" "/api/health" "健康检查 - 系统健康状态"

echo ""
echo "=========================================="
echo "  6. 页面访问测试"
echo "=========================================="
echo ""

test_page() {
    local url=$1
    local description=$2
    
    echo -e "${BLUE}[测试]${NC} $description"
    echo -e "  URL: $BASE_URL$url"
    
    response=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL$url")
    
    if [ "$response" -eq 200 ]; then
        echo -e "  ${GREEN}✓ 通过${NC} (状态码: $response)"
        ((passed++))
    else
        echo -e "  ${RED}✗ 失败${NC} (状态码: $response)"
        ((failed++))
    fi
    echo ""
}

test_page "/gpu-admin" "管理面板 - GPU管理页面"
test_page "/plugins/ai-os-manager/inject.js" "插件脚本 - inject.js"
test_page "/plugins/ai-os-manager/styles.css" "插件样式 - styles.css"

echo ""
echo "=========================================="
echo "  详细API响应测试"
echo "=========================================="
echo ""

echo -e "${BLUE}[详细测试]${NC} 获取GPU信息完整响应:"
curl -s "$BASE_URL/api/gpu-monitor/info" | python3 -m json.tool 2>/dev/null || curl -s "$BASE_URL/api/gpu-monitor/info"
echo ""
echo ""

echo -e "${BLUE}[详细测试]${NC} 获取模型列表完整响应:"
curl -s "$BASE_URL/api/model-switch/aggregated" | python3 -m json.tool 2>/dev/null | head -100
echo "... (已截断)"
echo ""

echo -e "${BLUE}[详细测试]${NC} 获取引擎状态完整响应:"
curl -s "$BASE_URL/api/engine/status" | python3 -m json.tool 2>/dev/null || curl -s "$BASE_URL/api/engine/status"
echo ""

echo ""
echo "=========================================="
echo "  测试总结"
echo "=========================================="
echo ""
echo -e "  ${GREEN}通过: $passed${NC}"
echo -e "  ${RED}失败: $failed${NC}"
echo -e "  ${YELLOW}跳过: $skipped${NC}"
echo ""
total=$((passed + failed + skipped))
if [ $total -gt 0 ]; then
    pass_rate=$((passed * 100 / total))
    echo -e "  通过率: ${pass_rate}%"
fi
echo ""
echo "=========================================="

