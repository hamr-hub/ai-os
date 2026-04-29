#!/usr/bin/env python3
"""
Go后端模型切换流程测试
"""

import json
import time
import requests
import sys
from datetime import datetime

GO_BACKEND = "http://localhost:35001"
PYTHON_BACKEND = "http://localhost:35000"
AICLIENT_GATEWAY = "http://192.168.7.103:3000"

def log(msg, level="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")

def test_go_health():
    log("测试Go后端健康状态...")
    try:
        resp = requests.get(f"{GO_BACKEND}/manage/models/aggregated", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            log(f"✓ Go后端在线，返回 {data.get('total_variants', 0)} 个模型")
            return True
    except Exception as e:
        log(f"✗ Go后端离线: {e}", "ERROR")
    return False

def get_current_model():
    log("获取当前运行模型...")
    try:
        resp = requests.get(f"{GO_BACKEND}/manage/models/aggregated", timeout=10)
        data = resp.json()
        current = data.get("current_model")
        log(f"当前模型: {current}")
        
        running = []
        for group in data.get("groups", []):
            for variant in group.get("variants", []):
                if variant.get("running"):
                    running.append({
                        "name": variant["name"],
                        "is_current": variant.get("is_current", False),
                        "backend": variant.get("backend_type"),
                        "port": variant.get("port"),
                        "path": variant.get("path"),
                    })
        
        log(f"运行中模型: {[m['name'] for m in running]}")
        return current, running
    except Exception as e:
        log(f"获取当前模型失败: {e}", "ERROR")
        return None, []

def get_stopped_vllm_model():
    log("获取已停止的vLLM模型...")
    try:
        resp = requests.get(f"{GO_BACKEND}/manage/models/aggregated", timeout=10)
        data = resp.json()
        
        candidates = []
        for group in data.get("groups", []):
            for variant in group.get("variants", []):
                if not variant.get("running") and variant.get("backend_type") == "vllm":
                    name = variant.get("name")
                    mem = variant.get("required_memory_gb", 999)
                    priority = 1 if ("NVFP4" in name or "nvfp4" in name) else 0
                    candidates.append((priority, mem, name))
        
        if candidates:
            candidates.sort(key=lambda x: (-x[0], x[1]))
            return candidates[0][2]
        
        return None
    except Exception as e:
        log(f"获取停止模型失败: {e}", "ERROR")
        return None

def test_go_switch_model(target_model):
    log(f"测试Go后端切换模型: {target_model}")
    
    # 1. 切换前状态
    log("\n--- 切换前状态 ---")
    before_current, before_running = get_current_model()
    
    # 2. 通过Go后端发起切换
    log("\n--- 发起切换请求 ---")
    try:
        resp = requests.post(
            f"{GO_BACKEND}/manage/switch/atomic",
            json={"model_name": target_model, "set_as_default": True},
            timeout=10
        )
        
        if resp.status_code != 200:
            log(f"✗ 切换请求失败: HTTP {resp.status_code}", "ERROR")
            log(f"响应: {resp.text}")
            return False
        
        result = resp.json()
        session_id = result.get("session_id")
        log(f"✓ 切换请求已接受, session_id: {session_id}")
        
    except Exception as e:
        log(f"✗ 切换请求异常: {e}", "ERROR")
        return False
    
    # 3. 轮询状态
    log("\n--- 监控切换进度 ---")
    max_wait = 300
    poll_interval = 5
    elapsed = 0
    
    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval
        
        try:
            resp = requests.get(f"{GO_BACKEND}/manage/switch/status", timeout=10)
            status = resp.json()
            
            session = status.get("session")
            if not session:
                log(f"等待中... ({elapsed}s)")
                continue
            
            phase = session.get("overall_phase")
            progress = session.get("overall_progress", 0)
            is_switching = status.get("is_switching", False)
            
            log(f"进度: {phase} - {progress}% (已等待 {elapsed}s)")
            
            for p in session.get("phases", []):
                p_name = p.get("name", "")
                p_status = p.get("status", "")
                if p_status in ["running", "failed", "success"]:
                    log(f"  [{p_status}] {p_name}")
            
            if not is_switching:
                if session.get("completed_successfully"):
                    log(f"\n✓ 模型切换成功!")
                    
                    # 4. 验证切换后状态
                    log("\n--- 切换后状态验证 ---")
                    after_current, after_running = get_current_model()
                    log(f"切换后当前模型: {after_current}")
                    log(f"切换后运行中模型: {[m['name'] for m in after_running]}")
                    
                    if after_current == target_model:
                        log("✓ 当前模型已更新为目标模型")
                        return True
                    else:
                        log(f"✗ 当前模型未正确更新: 期望={target_model}, 实际={after_current}", "ERROR")
                        return False
                else:
                    error = session.get("error") or session.get("rollback_reason")
                    log(f"✗ 模型切换失败: {error}", "ERROR")
                    return False
        
        except Exception as e:
            log(f"轮询状态异常: {e}", "ERROR")
            continue
    
    log(f"✗ 切换超时 (>{max_wait}s)", "ERROR")
    return False

def test_go_direct_switch(model_name):
    log(f"测试Go后端直接切换端点: /manage/models/{model_name}/switch")
    try:
        resp = requests.post(
            f"{GO_BACKEND}/manage/models/{model_name}/switch",
            timeout=10
        )
        result = resp.json()
        log(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
        return resp.status_code == 200
    except Exception as e:
        log(f"直接切换端点测试失败: {e}", "ERROR")
        return False

def main():
    log("=" * 60)
    log("Go后端模型切换流程测试")
    log("=" * 60)
    
    if not test_go_health():
        log("✗ Go后端不可用，退出测试", "ERROR")
        return False
    
    log("\n--- 步骤 1: 获取当前运行模型 ---")
    current_model, running_models = get_current_model()
    
    if not current_model:
        log("✗ 没有运行的模型", "ERROR")
        return False
    
    log("\n--- 步骤 2: 获取可切换的目标模型 ---")
    target = get_stopped_vllm_model()
    
    if not target:
        log("⚠ 没有可用的停止模型", "WARNING")
        return True
    
    log(f"目标模型: {target}")
    
    log("\n--- 步骤 3: 执行模型切换 ---")
    switch_success = test_go_switch_model(target)
    
    if not switch_success:
        log("✗ 模型切换测试失败", "ERROR")
        return False
    
    log("\n" + "=" * 60)
    log("✓ Go后端模型切换测试完成")
    log("=" * 60)
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        log("\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        log(f"\n测试异常: {e}", "CRITICAL")
        import traceback
        traceback.print_exc()
        sys.exit(2)
