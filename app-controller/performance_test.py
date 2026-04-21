import asyncio
import httpx
import time
import statistics
from typing import Dict, List, Tuple
from datetime import datetime

BASE_URL = "http://192.168.7.103:5000"

API_ENDPOINTS = [
    # OpenAI兼容API
    {"method": "GET", "path": "/v1/models", "name": "list_models"},
    {"method": "POST", "path": "/v1/chat/completions", "name": "chat_completions", "body": {
        "model": "test-model",
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": False
    }},
    {"method": "POST", "path": "/v1/embeddings", "name": "embeddings", "body": {
        "model": "test-model",
        "input": "Hello world"
    }},
    {"method": "POST", "path": "/v1/images/generations", "name": "image_generations", "body": {
        "model": "dall-e-3",
        "prompt": "A beautiful sunset"
    }},
    {"method": "POST", "path": "/v1/images/validate", "name": "image_validate", "body": {
        "image_data": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    }},
    {"method": "GET", "path": "/v1/images/info", "name": "image_info"},
    
    # 管理API
    {"method": "GET", "path": "/manage/gpu", "name": "gpu_status"},
    {"method": "GET", "path": "/manage/gpu/summary", "name": "gpu_summary"},
    {"method": "GET", "path": "/manage/models", "name": "model_status"},
    {"method": "GET", "path": "/manage/queue", "name": "queue_status"},
    {"method": "GET", "path": "/manage/preload", "name": "preload_status"},
    {"method": "GET", "path": "/manage/preload/status", "name": "preload_detailed_status"},
    {"method": "GET", "path": "/manage/metrics", "name": "metrics"},
    {"method": "GET", "path": "/manage/config", "name": "config"},
    {"method": "GET", "path": "/manage/service/status", "name": "service_status"},
    {"method": "GET", "path": "/manage/cache/status", "name": "cache_status"},
    {"method": "GET", "path": "/manage/cache/stats", "name": "cache_stats"},
    {"method": "GET", "path": "/manage/gpu/history", "name": "gpu_history"},
    {"method": "GET", "path": "/manage/websocket/connections", "name": "websocket_connections"},
    {"method": "GET", "path": "/manage/redis/health", "name": "redis_health"},
    
    # 健康检查API
    {"method": "GET", "path": "/health", "name": "health_check"},
    {"method": "GET", "path": "/health/detailed", "name": "health_detailed"},
    {"method": "GET", "path": "/manage/health/alert", "name": "health_alert"},
    
    # Prometheus指标
    {"method": "GET", "path": "/metrics", "name": "prometheus_metrics"},
    {"method": "GET", "path": "/metrics/metadata", "name": "metrics_metadata"},
    
    # Node.js集成API
    {"method": "GET", "path": "/api/v1/status", "name": "node_integration_status"},
    
    # 测试API
    {"method": "GET", "path": "/manage/logs/test", "name": "logging_test"},
]

async def test_endpoint(client: httpx.AsyncClient, endpoint: Dict) -> Tuple[str, float, int, str]:
    """测试单个API端点"""
    method = endpoint["method"]
    path = endpoint["path"]
    name = endpoint["name"]
    body = endpoint.get("body")
    
    url = f"{BASE_URL}{path}"
    
    try:
        start_time = time.time()
        
        if method == "GET":
            response = await client.get(url, timeout=30)
        elif method == "POST":
            response = await client.post(url, json=body, timeout=30)
        else:
            return (name, 0, 0, f"Unsupported method: {method}")
        
        end_time = time.time()
        duration = (end_time - start_time) * 1000  # 转换为毫秒
        
        if response.status_code >= 200 and response.status_code < 300:
            return (name, duration, response.status_code, "success")
        else:
            return (name, duration, response.status_code, f"HTTP error: {response.status_code}")
    
    except httpx.TimeoutException:
        return (name, 0, 0, "timeout")
    except Exception as e:
        return (name, 0, 0, f"error: {str(e)}")

async def run_performance_test(iterations: int = 3):
    """运行性能测试"""
    results = {}
    
    for endpoint in API_ENDPOINTS:
        name = endpoint["name"]
        results[name] = []
    
    async with httpx.AsyncClient() as client:
        for iteration in range(iterations):
            print(f"\n=== 第 {iteration + 1}/{iterations} 次迭代 ===")
            
            for endpoint in API_ENDPOINTS:
                name, duration, status_code, status = await test_endpoint(client, endpoint)
                
                if status == "success":
                    results[name].append(duration)
                    print(f"  [{name}] {duration:.2f}ms")
                else:
                    print(f"  [{name}] {status} (HTTP {status_code})")
            
            await asyncio.sleep(1)
    
    return results

def analyze_results(results: Dict[str, List[float]]):
    """分析测试结果"""
    print("\n" + "="*70)
    print("性能测试结果分析")
    print("="*70)
    
    slow_endpoints = []
    fast_endpoints = []
    
    for name, durations in results.items():
        if not durations:
            print(f"\n{name}: 无有效数据")
            continue
        
        avg = statistics.mean(durations)
        min_val = min(durations)
        max_val = max(durations)
        stdev = statistics.stdev(durations) if len(durations) > 1 else 0
        
        print(f"\n{name}:")
        print(f"  平均响应时间: {avg:.2f}ms")
        print(f"  最小响应时间: {min_val:.2f}ms")
        print(f"  最大响应时间: {max_val:.2f}ms")
        print(f"  标准差: {stdev:.2f}ms")
        print(f"  测试次数: {len(durations)}")
        
        if avg > 500:
            slow_endpoints.append((name, avg))
        elif avg < 100:
            fast_endpoints.append((name, avg))
    
    print("\n" + "-"*70)
    print("慢端点（响应时间 > 500ms）:")
    if slow_endpoints:
        for name, avg in sorted(slow_endpoints, key=lambda x: x[1], reverse=True):
            print(f"  {name}: {avg:.2f}ms")
    else:
        print("  无慢端点")
    
    print("\n快端点（响应时间 < 100ms）:")
    if fast_endpoints:
        for name, avg in sorted(fast_endpoints, key=lambda x: x[1]):
            print(f"  {name}: {avg:.2f}ms")
    else:
        print("  无快端点")
    
    return slow_endpoints

def generate_optimization_suggestions(slow_endpoints: List[Tuple[str, str, float]]):
    """生成优化建议"""
    print("\n" + "="*70)
    print("优化建议")
    print("="*70)
    
    endpoint_suggestions = {
        "chat_completions": [
            "考虑增加请求缓存，避免重复计算",
            "使用异步处理减少阻塞",
            "考虑引入模型预热机制",
            "增加并发请求限制避免过载"
        ],
        "embeddings": [
            "考虑使用批量处理减少请求次数",
            "增加结果缓存",
            "考虑使用更轻量的模型"
        ],
        "image_generations": [
            "考虑使用专用的图片生成服务",
            "增加请求队列管理",
            "考虑使用CDN缓存生成的图片"
        ],
        "gpu_history": [
            "考虑使用分页返回历史数据",
            "增加历史数据压缩",
            "使用缓存减少数据库查询"
        ],
        "prometheus_metrics": [
            "考虑增加指标缓存",
            "减少不必要的指标计算",
            "考虑异步指标收集"
        ],
        "model_status": [
            "增加模型状态缓存",
            "减少频繁的进程状态检查",
            "考虑使用事件驱动更新状态"
        ],
        "health_detailed": [
            "减少健康检查的计算复杂度",
            "增加健康状态缓存"
        ]
    }
    
    for name, _ in slow_endpoints:
        suggestions = endpoint_suggestions.get(name)
        if suggestions:
            print(f"\n{name}:")
            for i, suggestion in enumerate(suggestions, 1):
                print(f"  {i}. {suggestion}")
    
    print("\n通用优化建议:")
    print("  1. 增加Redis缓存策略，减少重复计算")
    print("  2. 使用异步处理提升并发性能")
    print("  3. 增加请求限流和熔断机制")
    print("  4. 考虑使用连接池复用HTTP连接")
    print("  5. 优化数据库查询，增加索引")
    print("  6. 使用Gunicorn或Uvicorn多进程部署")
    print("  7. 考虑引入响应压缩（gzip/brotli）")
    print("  8. 增加日志监控，追踪慢请求")

if __name__ == "__main__":
    print("="*70)
    print(f"Python控制器性能测试")
    print(f"目标地址: {BASE_URL}")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    try:
        results = asyncio.run(run_performance_test(iterations=3))
        slow_endpoints = analyze_results(results)
        generate_optimization_suggestions(slow_endpoints)
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"\n测试发生错误: {str(e)}")