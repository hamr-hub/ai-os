#!/usr/bin/env python3
"""
真实接口测试 - 直接调用运行中的服务 API，不使用任何 mock
测试目标: app-controller (35000) + go-vllm-api (35001)
"""

import requests
import json
import sys
import time
import traceback

PYTHON_BASE = "http://localhost:35000"
GO_BASE = "http://localhost:35001"

passed = 0
failed = 0
errors = []


def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  \033[92m✓ PASS\033[0m {name}")
    else:
        failed += 1
        errors.append((name, detail))
        print(f"  \033[91m✗ FAIL\033[0m {name}")
    if detail:
        print(f"         {detail}")


def get(url, base=PYTHON_BASE, **kwargs):
    try:
        r = requests.get(f"{base}{url}", timeout=10, **kwargs)
        return r
    except Exception as e:
        return None


def post(url, json_data=None, base=PYTHON_BASE, **kwargs):
    try:
        r = requests.post(f"{base}{url}", json=json_data, timeout=10, **kwargs)
        return r
    except Exception as e:
        return None


def put(url, json_data=None, base=PYTHON_BASE, **kwargs):
    try:
        r = requests.put(f"{base}{url}", json=json_data, timeout=10, **kwargs)
        return r
    except Exception as e:
        return None


def delete(url, base=PYTHON_BASE, **kwargs):
    try:
        r = requests.delete(f"{base}{url}", timeout=10, **kwargs)
        return r
    except Exception as e:
        return None


# ============================================================
print("\n\033[94m" + "=" * 60)
print("  真实接口测试 - app-controller (Python :35000)")
print("=" * 60 + "\033[0m\n")

# --- 健康检查 ---
print("\n--- 健康检查 ---")
r = get("/health")
test("GET /health 返回 200", r is not None and r.status_code == 200)
if r and r.status_code == 200:
    d = r.json()
    test("health 包含 status 字段", "status" in d, f"keys={list(d.keys())}")
    test("health 包含 health_score 字段", "health_score" in d, f"score={d.get('health_score')}")
    test("health_score > 0", d.get("health_score", 0) > 0, f"score={d.get('health_score')}")

r = get("/manage/health/alert")
test("GET /manage/health/alert 返回 200", r is not None and r.status_code == 200)
if r and r.status_code == 200:
    d = r.json()
    test("alert 包含 should_alert 字段", "should_alert" in d, f"should_alert={d.get('should_alert')}")
    test("alert 包含 health_score 字段", "health_score" in d, f"health_score={d.get('health_score')}")

# --- GPU 管理 ---
print("\n--- GPU 管理 ---")
r = get("/manage/gpu")
test("GET /manage/gpu 返回 200", r is not None and r.status_code == 200)
if r and r.status_code == 200:
    d = r.json()
    test("GPU status 包含 status 字段", "status" in d, f"status={d.get('status')}")
    test("GPU 可用", d.get("status") == "available", f"status={d.get('status')}")

r = get("/manage/gpu/summary")
test("GET /manage/gpu/summary 返回 200", r is not None and r.status_code == 200)

r = get("/manage/gpu/history?count=5")
test("GET /manage/gpu/history 返回 200", r is not None and r.status_code == 200)
if r and r.status_code == 200:
    d = r.json()
    test("GPU history 包含 history 数组", "history" in d and isinstance(d["history"], list))

r = get("/manage/gpu/processes")
test("GET /manage/gpu/processes 返回 200", r is not None and r.status_code == 200)

r = get("/manage/gpu/enhanced")
test("GET /manage/gpu/enhanced 返回 200", r is not None and r.status_code == 200)

r = get("/manage/gpu/realtime")
test("GET /manage/gpu/realtime 返回 200", r is not None and r.status_code == 200)

r = get("/manage/gpu/memory-check")
test("GET /manage/gpu/memory-check 返回 200", r is not None and r.status_code == 200)

# --- 模型管理 ---
print("\n--- 模型管理 ---")
r = get("/manage/models")
test("GET /manage/models 返回 200", r is not None and r.status_code == 200)
if r and r.status_code == 200:
    d = r.json()
    test("models 返回非空字典", isinstance(d, dict) and len(d) > 0, f"model_count={len(d)}")

r = get("/manage/models/summary")
test("GET /manage/models/summary 返回 200", r is not None and r.status_code == 200)
if r and r.status_code == 200:
    d = r.json()
    test("summary 包含 models 列表", "models" in d and isinstance(d["models"], list))
    test("summary 包含 running_model", "running_model" in d, f"running={d.get('running_model')}")

r = get("/manage/models/aggregated")
test("GET /manage/models/aggregated 返回 200", r is not None and r.status_code == 200)
if r and r.status_code == 200:
    d = r.json()
    test("aggregated 包含 groups 列表", "groups" in d and isinstance(d["groups"], list))

# --- 废弃接口 ---
print("\n--- 废弃接口 ---")
r = post("/manage/models/test-model/start")
test("POST /manage/models/{name}/start 返回 410", r is not None and r.status_code == 410)
if r and r.status_code == 410:
    d = r.json()
    test("410 响应包含 replacement", "replacement" in d.get("detail", d), f"detail={d}")

r = post("/manage/models/test-model/stop")
test("POST /manage/models/{name}/stop 返回 410", r is not None and r.status_code == 410)

r = post("/manage/models/test-model/switch")
test("POST /manage/models/{name}/switch 返回 410", r is not None and r.status_code == 410)

# --- 切换状态 ---
print("\n--- 模型切换 ---")
r = get("/manage/switch/status")
test("GET /manage/switch/status 返回 200", r is not None and r.status_code == 200)
if r and r.status_code == 200:
    d = r.json()
    test("switch/status 包含 is_switching", "is_switching" in d)

# --- 默认模型 ---
print("\n--- 默认模型 ---")
r = get("/manage/default-model")
test("GET /manage/default-model 返回 200", r is not None and r.status_code == 200)

# --- 队列 ---
print("\n--- 队列 ---")
r = get("/manage/queue")
test("GET /manage/queue 返回 200", r is not None and r.status_code == 200)
if r and r.status_code == 200:
    d = r.json()
    test("queue 返回字典", isinstance(d, dict))

# --- Preload ---
print("\n--- Preload ---")
r = get("/manage/preload")
test("GET /manage/preload 返回 200", r is not None and r.status_code == 200)
if r and r.status_code == 200:
    d = r.json()
    test("preload 包含 preloaded_models", "preloaded_models" in d)
    test("preload 包含 all_models", "all_models" in d)

r = get("/manage/preload/status")
test("GET /manage/preload/status 返回 200", r is not None and r.status_code == 200)

# --- Token 统计 ---
print("\n--- Token 统计 ---")
r = get("/manage/token/stats")
test("GET /manage/token/stats 返回 200", r is not None and r.status_code == 200)

r = get("/manage/token/history?count=5")
test("GET /manage/token/history 返回 200", r is not None and r.status_code == 200)

# --- Metrics ---
print("\n--- Metrics ---")
r = get("/manage/metrics")
test("GET /manage/metrics 返回 200", r is not None and r.status_code == 200)

r = get("/manage/metrics/health-detail")
test("GET /manage/metrics/health-detail 返回 200", r is not None and r.status_code == 200)

# --- Cache ---
print("\n--- Cache ---")
r = get("/manage/cache/status")
test("GET /manage/cache/status 返回 200", r is not None and r.status_code == 200)

r = get("/manage/cache/stats")
test("GET /manage/cache/stats 返回 200", r is not None and r.status_code == 200)

# --- Config ---
print("\n--- Config ---")
r = get("/manage/config")
test("GET /manage/config 返回 200", r is not None and r.status_code == 200)
if r and r.status_code == 200:
    d = r.json()
    test("config 包含 models", "models" in d)
    test("config 包含 settings", "settings" in d)
    test("config 包含 version", "version" in d, f"version={d.get('version')}")

# --- System ---
print("\n--- System ---")
r = get("/manage/system/status")
test("GET /manage/system/status 返回 200", r is not None and r.status_code == 200)
if r and r.status_code == 200:
    d = r.json()
    test("system 包含 cpu 信息", "cpu" in d)
    test("system 包含 memory 信息", "memory" in d)
    test("system 包含 disk 信息", "disk" in d)

r = get("/manage/system/history?count=5")
test("GET /manage/system/history 返回 200", r is not None and r.status_code == 200)

# --- Service ---
print("\n--- Service ---")
r = get("/manage/service/status")
test("GET /manage/service/status 返回 200", r is not None and r.status_code == 200)

# --- Redis ---
print("\n--- Redis ---")
r = get("/manage/redis/health")
test("GET /manage/redis/health 返回 200", r is not None and r.status_code == 200)
if r and r.status_code == 200:
    d = r.json()
    test("redis health 包含 connected 字段", "connected" in d, f"connected={d.get('connected')}")

# --- vLLM ---
print("\n--- vLLM ---")
r = get("/manage/vllm/metrics")
test("GET /manage/vllm/metrics 返回 200", r is not None and r.status_code == 200)

r = get("/manage/vllm/default-config")
test("GET /manage/vllm/default-config 返回 200", r is not None and r.status_code == 200)

# --- Engine ---
print("\n--- Engine ---")
r = get("/manage/engines/status")
test("GET /manage/engines/status 返回 200", r is not None and r.status_code == 200)

r = get("/manage/engines/config")
test("GET /manage/engines/config 返回 200", r is not None and r.status_code == 200)

r = get("/manage/engines/param-schema")
test("GET /manage/engines/param-schema 返回 200", r is not None and r.status_code == 200)

# --- Scheduler ---
print("\n--- Scheduler ---")
r = get("/manage/scheduler/status")
test("GET /manage/scheduler/status 返回 200", r is not None and r.status_code == 200)

r = get("/manage/scheduler/pool")
test("GET /manage/scheduler/pool 返回 200", r is not None and r.status_code == 200)

# --- Model Pool ---
print("\n--- Model Pool ---")
r = get("/manage/models/pool")
test("GET /manage/models/pool 返回 200", r is not None and r.status_code == 200)

r = get("/manage/models/downloads")
test("GET /manage/models/downloads 返回 200", r is not None and r.status_code == 200)

# --- Monitor All ---
print("\n--- Monitor All ---")
r = get("/manage/monitor/all")
test("GET /manage/monitor/all 返回 200", r is not None and r.status_code == 200)
if r and r.status_code == 200:
    d = r.json()
    test("monitor/all 包含 success=True", d.get("success") is True)
    test("monitor/all 包含 gpu 信息", "gpu" in d)
    test("monitor/all 包含 models 信息", "models" in d)
    test("monitor/all 包含 health 信息", "health" in d)

# --- Integration API ---
print("\n--- Integration API ---")
r = get("/api/v1/status")
test("GET /api/v1/status 返回 200", r is not None and r.status_code == 200)
if r and r.status_code == 200:
    d = r.json()
    test("integration status 包含 service", "service" in d)
    test("integration status 包含 models", "models" in d)

# --- OpenAI 兼容接口 ---
print("\n--- OpenAI 兼容接口 ---")
r = get("/v1/models")
test("GET /v1/models 返回 200", r is not None and r.status_code == 200)
if r and r.status_code == 200:
    d = r.json()
    test("v1/models 返回 object=list", d.get("object") == "list")
    test("v1/models 返回 data 数组", "data" in d and isinstance(d["data"], list))
    test("v1/models 有可用模型", len(d["data"]) > 0, f"count={len(d['data'])}")

# --- Rate Limit ---
print("\n--- Rate Limit ---")
r = get("/manage/ratelimit/config")
test("GET /manage/ratelimit/config 返回 200", r is not None and r.status_code == 200)

r = get("/manage/ratelimit/stats")
test("GET /manage/ratelimit/stats 返回 200", r is not None and r.status_code == 200)

# --- WebSocket ---
print("\n--- WebSocket ---")
r = get("/manage/websocket/connections")
test("GET /manage/websocket/connections 返回 200", r is not None and r.status_code == 200)

# --- Logs ---
print("\n--- Logs ---")
r = get("/manage/logs/test")
test("GET /manage/logs/test 返回 200", r is not None and r.status_code == 200)


# ============================================================
print("\n\033[94m" + "=" * 60)
print("  真实接口测试 - go-vllm-api (Go :35001)")
print("=" * 60 + "\033[0m\n")

# --- Health ---
print("\n--- Health ---")
r = get("/health", base=GO_BASE)
test("GET /health 返回 200", r is not None and r.status_code == 200)
if r and r.status_code == 200:
    d = r.json()
    test("go health 包含 status", "status" in d, f"status={d.get('status')}")

try:
    r = requests.get(f"{GO_BASE}/health/detailed", timeout=30)
except Exception as e:
    r = None
test("GET /health/detailed 返回 200", r is not None and r.status_code == 200)

# --- Metrics ---
print("\n--- Metrics ---")
r = get("/metrics", base=GO_BASE)
test("GET /metrics 返回 200", r is not None and r.status_code == 200)

r = get("/metrics/metadata", base=GO_BASE)
test("GET /metrics/metadata 返回 200", r is not None and r.status_code == 200)

# --- V1 Models ---
print("\n--- V1 Models ---")
r = get("/v1/models", base=GO_BASE)
test("GET /v1/models 返回 200", r is not None and r.status_code == 200)
if r and r.status_code == 200:
    d = r.json()
    test("go v1/models 返回 object=list", d.get("object") == "list")

r = get("/v1/status", base=GO_BASE)
test("GET /v1/status 返回 200", r is not None and r.status_code == 200)

# --- Agent ---
print("\n--- Agent ---")
r = get("/manage/agent/tools", base=GO_BASE)
test("GET /manage/agent/tools 返回 200", r is not None and r.status_code == 200)
if r and r.status_code == 200:
    d = r.json()
    test("agent tools 返回数据", isinstance(d, (list, dict)))


# ============================================================
# 汇总
# ============================================================
total = passed + failed
print("\n\033[94m" + "=" * 60)
print("  测试汇总")
print("=" * 60 + "\033[0m\n")
print(f"  总计: \033[92m{passed} passed\033[0m / \033[91m{failed} failed\033[0m / {total} total")

if errors:
    print(f"\n  \033[91m失败列表:\033[0m")
    for name, detail in errors:
        print(f"    ✗ {name}: {detail}")

if failed == 0:
    print(f"\n  \033[92m✓ 所有真实接口测试通过！\033[0m\n")
    sys.exit(0)
else:
    print(f"\n  \033[91m✗ 有 {failed} 个测试失败\033[0m\n")
    sys.exit(1)
