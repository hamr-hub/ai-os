#!/usr/bin/env python3
"""
端到端测试脚本 - T20260422-001
测试 Redis 配置、Mock vLLM 服务、前后端联调
"""

import requests
import json
import os
import sys
import time
from typing import Dict, Any

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def print_header(title: str):
    print(f"\n{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BLUE}  {title}{Colors.RESET}")
    print(f"{Colors.BLUE}{'='*60}{Colors.RESET}\n")

def print_test(name: str, passed: bool, detail: str = ""):
    status = f"{Colors.GREEN}✓ PASS{Colors.RESET}" if passed else f"{Colors.RED}✗ FAIL{Colors.RESET}"
    print(f"  {status} {name}")
    if detail:
        print(f"         {detail}")

def test_mock_vllm_service():
    """测试 Mock vLLM 服务"""
    print_header("测试 Mock vLLM 服务")
    
    base_url = "http://localhost:8001"
    results = []
    
    # 测试健康检查
    try:
        resp = requests.get(f"{base_url}/health", timeout=5)
        data = resp.json()
        passed = data.get("status") == "ok"
        results.append(("健康检查", passed, f"status={data.get('status')}"))
        print_test("健康检查", passed)
    except Exception as e:
        results.append(("健康检查", False, str(e)))
        print_test("健康检查", False, str(e))
    
    # 测试模型列表
    try:
        resp = requests.get(f"{base_url}/v1/models", timeout=5)
        data = resp.json()
        models = data.get("data", [])
        passed = len(models) > 0
        model_names = [m["id"] for m in models]
        results.append(("模型列表", passed, f"models={model_names}"))
        print_test("模型列表", passed, f"找到 {len(models)} 个模型")
    except Exception as e:
        results.append(("模型列表", False, str(e)))
        print_test("模型列表", False, str(e))
    
    # 测试聊天补全
    try:
        resp = requests.post(
            f"{base_url}/v1/chat/completions",
            json={
                "model": "Gemma-4-31B-Abliterated",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": False
            },
            timeout=10
        )
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        passed = len(content) > 0
        results.append(("聊天补全", passed, f"response={content[:50]}..."))
        print_test("聊天补全", passed, f"响应: {content[:50]}...")
    except Exception as e:
        results.append(("聊天补全", False, str(e)))
        print_test("聊天补全", False, str(e))
    
    return results

def test_backend_service():
    """测试后端服务"""
    print_header("测试后端服务")
    
    base_url = "http://localhost:35000"
    results = []
    
    # 测试健康检查
    try:
        resp = requests.get(f"{base_url}/health", timeout=5)
        data = resp.json()
        status = data.get("status", "")
        score = data.get("health_score", 0)
        passed = status in ["ok", "warning", "degraded"]
        results.append(("健康检查", passed, f"status={status}, score={score}"))
        print_test("健康检查", passed, f"状态: {status}, 健康分: {score}")
    except Exception as e:
        results.append(("健康检查", False, str(e)))
        print_test("健康检查", False, str(e))
    
    # 测试模型管理
    try:
        resp = requests.get(f"{base_url}/manage/models", timeout=5)
        data = resp.json()
        passed = len(data) > 0
        model_count = len(data)
        results.append(("模型管理", passed, f"models={model_count}"))
        print_test("模型管理", passed, f"找到 {model_count} 个模型配置")
    except Exception as e:
        results.append(("模型管理", False, str(e)))
        print_test("模型管理", False, str(e))
    
    # 测试 GPU 监控
    try:
        resp = requests.get(f"{base_url}/manage/gpu", timeout=5)
        data = resp.json()
        status = data.get("status", "")
        passed = status in ["available", "unavailable"]
        results.append(("GPU监控", passed, f"status={status}"))
        print_test("GPU监控", passed, f"状态: {status}")
    except Exception as e:
        results.append(("GPU监控", False, str(e)))
        print_test("GPU监控", False, str(e))
    
    # 测试 GPU 摘要
    try:
        resp = requests.get(f"{base_url}/manage/gpu/summary", timeout=5)
        data = resp.json()
        passed = "status" in data
        results.append(("GPU摘要", passed, f"data keys={list(data.keys())}"))
        print_test("GPU摘要", passed)
    except Exception as e:
        results.append(("GPU摘要", False, str(e)))
        print_test("GPU摘要", False, str(e))
    
    return results

def test_redis_config():
    """测试 Redis 配置"""
    print_header("测试 Redis 配置")
    
    results = []
    
    # 测试配置加载
    try:
        sys.path.insert(0, "/Users/hyx/codespace/ai-os/app-controller")
        from core.config import load_config, RedisConfig
        
        # 测试环境变量
        os.environ["REDIS_HOST"] = "test.redis.host"
        os.environ["REDIS_PORT"] = "6380"
        
        # 重新加载配置
        config = load_config("app-controller/config.yaml")
        
        if config.settings and config.settings.redis:
            host = config.settings.redis.host
            port = config.settings.redis.port
            passed = host == "test.redis.host" and port == 6380
            results.append(("环境变量配置", passed, f"host={host}, port={port}"))
            print_test("环境变量配置", passed, f"host={host}, port={port}")
        else:
            results.append(("环境变量配置", False, "Redis 配置未加载"))
            print_test("环境变量配置", False, "Redis 配置未加载")
        
        # 清理环境变量，测试配置文件
        del os.environ["REDIS_HOST"]
        del os.environ["REDIS_PORT"]
        
    except Exception as e:
        results.append(("Redis配置", False, str(e)))
        print_test("Redis配置", False, str(e))
    
    return results

def test_frontend():
    """测试前端"""
    print_header("测试前端服务")
    
    results = []
    
    # 测试前端可访问性
    try:
        resp = requests.get("http://localhost:30001/", timeout=5)
        passed = resp.status_code == 200 and "AI Controller" in resp.text
        results.append(("前端页面", passed, f"status={resp.status_code}"))
        print_test("前端页面", passed)
    except Exception as e:
        results.append(("前端页面", False, str(e)))
        print_test("前端页面", False, str(e))
    
    return results

def main():
    print(f"{Colors.YELLOW}")
    print("╔══════════════════════════════════════════════════════════╗")
    print("║     端到端测试 - T20260422-001                          ║")
    print("║     可配置 Redis + Mock vLLM + 前后端联调              ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"{Colors.RESET}")
    
    all_results = []
    
    # 运行所有测试
    all_results.extend(test_mock_vllm_service())
    all_results.extend(test_backend_service())
    all_results.extend(test_redis_config())
    all_results.extend(test_frontend())
    
    # 汇总结果
    print_header("测试汇总")
    
    passed = sum(1 for _, p, _ in all_results if p)
    total = len(all_results)
    
    print(f"  总计: {passed}/{total} 通过")
    
    if passed == total:
        print(f"\n  {Colors.GREEN}✓ 所有测试通过！{Colors.RESET}\n")
        return 0
    else:
        print(f"\n  {Colors.RED}✗ 有 {total - passed} 个测试失败{Colors.RESET}\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
