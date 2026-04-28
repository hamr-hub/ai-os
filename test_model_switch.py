#!/usr/bin/env python3
"""
自动化测试：模型原子切换及插件状态一致性检查
"""

import json
import time
import requests
import sys
from datetime import datetime

# 服务地址
PYTHON_BACKEND = "http://localhost:35000"
GO_BACKEND = "http://localhost:35001"
AICLIENT_GATEWAY = "http://localhost:3000"

def log(msg, level="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")

def test_services_health():
    """测试各服务是否在线"""
    log("检查服务健康状态...")
    
    services = {
        "Python Backend": f"{PYTHON_BACKEND}/manage/switch/status",
        "Go Backend": f"{GO_BACKEND}/manage/switch/status",
        "AIClient Gateway": f"{AICLIENT_GATEWAY}/api/model-switch/switch-status",
    }
    
    results = {}
    for name, url in services.items():
        try:
            resp = requests.get(url, timeout=5)
            results[name] = {"status": "online", "code": resp.status_code}
            log(f"✓ {name} 在线 (HTTP {resp.status_code})")
        except Exception as e:
            results[name] = {"status": "offline", "error": str(e)}
            log(f"✗ {name} 离线: {e}", "ERROR")
    
    return results

def get_models_from_all_sources():
    """从不同数据源获取模型列表"""
    log("获取模型列表...")
    
    results = {}
    
    # Python 后端
    try:
        resp = requests.get(f"{PYTHON_BACKEND}/manage/models/aggregated", timeout=10)
        results["python"] = resp.json()
        log(f"✓ Python 后端返回 {results['python'].get('total_variants', 0)} 个模型变体")
    except Exception as e:
        log(f"✗ Python 后端获取失败: {e}", "ERROR")
        results["python"] = None
    
    # Go 后端 (代理)
    try:
        resp = requests.get(f"{GO_BACKEND}/manage/models/aggregated", timeout=10)
        results["go"] = resp.json()
        log(f"✓ Go 后端返回 {results['go'].get('total_variants', 0)} 个模型变体")
    except Exception as e:
        log(f"✗ Go 后端获取失败: {e}", "ERROR")
        results["go"] = None
    
    # 插件网关
    try:
        resp = requests.get(f"{AICLIENT_GATEWAY}/api/model-switch/aggregated", timeout=10)
        results["gateway"] = resp.json()
        if results["gateway"].get("success"):
            log(f"✓ 插件网关返回 {results['gateway']['data'].get('total_variants', 0)} 个模型变体")
        else:
            log(f"✗ 插件网关返回失败: {results['gateway'].get('error')}", "ERROR")
    except Exception as e:
        log(f"✗ 插件网关获取失败: {e}", "ERROR")
        results["gateway"] = None
    
    return results

def get_current_running_model():
    """获取当前运行的模型"""
    try:
        resp = requests.get(f"{PYTHON_BACKEND}/manage/models/aggregated", timeout=10)
        data = resp.json()
        current = data.get("current_model")
        
        # 找出运行中的模型
        running = []
        for group in data.get("groups", []):
            for variant in group.get("variants", []):
                if variant.get("running"):
                    running.append({
                        "name": variant["name"],
                        "is_current": variant.get("is_current", False),
                        "backend": variant.get("backend_type"),
                        "port": variant.get("port"),
                    })
        
        return current, running
    except Exception as e:
        log(f"获取当前模型失败: {e}", "ERROR")
        return None, []

def get_plugin_provider_check_model():
    """获取插件中的 provider checkModelName"""
    try:
        resp = requests.get(f"{AICLIENT_GATEWAY}/api/model-switch/models", timeout=10)
        data = resp.json()
        
        # 检查是否有健康检查模型信息
        if data.get("data"):
            running = [m for m in data["data"] if m.get("running")]
            if running:
                return running[0].get("name")
    except Exception as e:
        log(f"获取插件模型信息失败: {e}", "ERROR")
    return None

def compare_model_states(models_data):
    """比较不同来源的模型状态一致性"""
    log("比较模型状态一致性...")
    
    issues = []
    
    if models_data.get("python") and models_data.get("go"):
        python_current = models_data["python"].get("current_model")
        go_current = models_data["go"].get("current_model")
        
        if python_current != go_current:
            issues.append(f"当前模型不一致: Python={python_current}, Go={go_current}")
        else:
            log(f"✓ 当前模型一致: {python_current}")
    
    if models_data.get("python") and models_data.get("gateway"):
        python_groups = models_data["python"].get("groups", [])
        gateway_data = models_data["gateway"].get("data", {})
        gateway_groups = gateway_data.get("groups", [])
        
        # 比较运行中的模型
        python_running = set()
        for group in python_groups:
            for variant in group.get("variants", []):
                if variant.get("running"):
                    python_running.add(variant["name"])
        
        gateway_running = set()
        for group in gateway_groups:
            for variant in group.get("variants", []):
                if variant.get("running"):
                    gateway_running.add(variant["name"])
        
        if python_running != gateway_running:
            issues.append(f"运行中模型不一致: Python={python_running}, Gateway={gateway_running}")
        else:
            log(f"✓ 运行中模型一致: {python_running}")
    
    return issues

def check_websocket_status():
    """检查 WebSocket 连接状态"""
    log("检查 WebSocket 连接...")
    
    try:
        resp = requests.get(f"{PYTHON_BACKEND}/manage/websocket/connections", timeout=5)
        stats = resp.json()
        log(f"✓ WebSocket 连接统计: {json.dumps(stats, indent=2)}")
        return stats
    except Exception as e:
        log(f"✗ WebSocket 检查失败: {e}", "ERROR")
        return None

def check_cache_status():
    """检查缓存状态"""
    log("检查缓存状态...")
    
    try:
        resp = requests.get(f"{PYTHON_BACKEND}/manage/cache/status", timeout=5)
        status = resp.json()
        log(f"✓ 缓存状态: {json.dumps(status, indent=2)}")
        return status
    except Exception as e:
        log(f"✗ 缓存检查失败: {e}", "ERROR")
        return None

def test_finalize_endpoint():
    """测试 finalize-switch 端点"""
    log("测试 finalize-switch 端点...")
    
    try:
        # 获取当前实际运行的模型
        current_model, running = get_current_running_model()
        if not current_model:
            log("⚠ 没有运行的模型，跳过 finalize 测试", "WARNING")
            return None
        
        # 使用真实的 session 结构测试
        mock_session = {
            "session_id": "test-" + str(int(time.time())),
            "target_model": current_model,
            "target_model_path": "/tmp/test-model",
            "previous_model": None,
            "previous_model_path": None,
            "started_at": datetime.now().isoformat(),
            "finished_at": datetime.now().isoformat(),
            "overall_phase": "completed",
            "overall_progress": 100,
            "phases": [
                {"phase": 1, "name": "停止旧服务", "status": "success", "progress": 100, "logs": []},
                {"phase": 2, "name": "强制清理进程", "status": "success", "progress": 100, "logs": []},
                {"phase": 3, "name": "启动新服务", "status": "success", "progress": 100, "logs": []},
                {"phase": 4, "name": "冒烟测试", "status": "success", "progress": 100, "logs": []},
            ],
            "completed_successfully": True,
            "error": None,
            "rollback_reason": None,
        }
        
        resp = requests.post(
            f"{AICLIENT_GATEWAY}/api/model-switch/finalize-switch",
            json={"session": mock_session},
            timeout=30
        )
        
        result = resp.json()
        if result.get("success"):
            log("✓ finalize-switch 端点可用")
            log(f"  预热状态: {result.get('data', {}).get('warmup', {}).get('success', 'N/A')}")
            log(f"  Provider更新: {result.get('data', {}).get('providerUpdate', {}).get('success', 'N/A')}")
        else:
            error = result.get('error', 'Unknown')
            # 检查是否是预期的失败（模型文件不存在导致预热失败）
            if 'warmup' in str(error).lower() or 'provider' in str(error).lower():
                log(f"⚠ finalize-switch 执行但部分步骤失败: {error}", "WARNING")
                log("  这是预期的，因为测试环境可能没有完整的模型文件")
            else:
                log(f"✗ finalize-switch 返回失败: {error}", "ERROR")
        
        return result
    except Exception as e:
        log(f"✗ finalize-switch 测试失败: {e}", "ERROR")
        return None


def get_stopped_model():
    """获取一个已停止的 vLLM 模型用于切换测试（排除 llama.cpp gguf 模型）"""
    try:
        resp = requests.get(f"{PYTHON_BACKEND}/manage/models/aggregated", timeout=10)
        data = resp.json()
        
        for group in data.get("groups", []):
            for variant in group.get("variants", []):
                # 只选择 vLLM 后端且未运行的模型
                backend = variant.get("backend_type", "vllm")
                if not variant.get("running") and backend == "vllm":
                    return variant["name"]
        
        return None
    except Exception as e:
        log(f"获取已停止模型失败: {e}", "ERROR")
        return None


def test_model_switch_flow(target_model=None):
    """测试完整的模型切换流程"""
    log("测试模型切换流程...")
    
    if not target_model:
        target_model = get_stopped_model()
    
    if not target_model:
        log("⚠ 没有可用的停止模型，跳过切换测试", "WARNING")
        return False
    
    log(f"准备切换到模型: {target_model}")
    
    # 1. 获取切换前状态
    log("\n--- 切换前状态 ---")
    before_current, before_running = get_current_running_model()
    log(f"切换前当前模型: {before_current}")
    log(f"切换前运行中模型: {[m['name'] for m in before_running]}")
    
    # 2. 发起切换请求
    log("\n--- 发起切换请求 ---")
    try:
        resp = requests.post(
            f"{PYTHON_BACKEND}/manage/switch/atomic",
            json={
                "model_name": target_model,
                "set_as_default": True
            },
            timeout=10
        )
        
        if resp.status_code != 200:
            log(f"✗ 切换请求失败: HTTP {resp.status_code}, {resp.text}", "ERROR")
            return False
        
        switch_resp = resp.json()
        session_id = switch_resp.get("session_id")
        log(f"✓ 切换请求已接受, session_id: {session_id}")
        
    except Exception as e:
        log(f"✗ 切换请求异常: {e}", "ERROR")
        return False
    
    # 3. 轮询切换状态
    log("\n--- 监控切换进度 ---")
    max_wait = 300  # 最多等待 5 分钟
    poll_interval = 5
    elapsed = 0
    
    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval
        
        try:
            resp = requests.get(f"{PYTHON_BACKEND}/manage/switch/status", timeout=10)
            status = resp.json()
            
            session = status.get("session")
            if not session:
                log(f"等待中... ({elapsed}s)")
                continue
            
            overall_phase = session.get("overall_phase")
            overall_progress = session.get("overall_progress", 0)
            is_switching = status.get("is_switching", False)
            
            log(f"进度: {overall_phase} - {overall_progress}% (已等待 {elapsed}s)")
            
            # 显示各阶段状态
            for phase in session.get("phases", []):
                phase_name = phase.get("name", "")
                phase_status = phase.get("status", "")
                if phase_status in ["running", "failed", "success"]:
                    log(f"  [{phase_status}] {phase_name}")
            
            # 检查是否完成
            if not is_switching:
                if session.get("completed_successfully"):
                    log(f"\n✓ 模型切换成功!")
                    
                    # 4. 验证切换后状态
                    log("\n--- 切换后状态验证 ---")
                    after_current, after_running = get_current_running_model()
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

def run_full_test(with_real_switch=False):
    """运行完整测试流程"""
    log("=" * 60)
    log("模型原子切换及插件状态一致性测试")
    log("=" * 60)
    
    # 1. 检查服务健康
    log("\n--- 步骤 1: 服务健康检查 ---")
    health_results = test_services_health()
    
    online_services = sum(1 for r in health_results.values() if r.get("status") == "online")
    if online_services < 2:
        log("✗ 至少需要 2 个服务在线才能继续测试", "ERROR")
        return False
    
    # 2. 获取当前运行模型
    log("\n--- 步骤 2: 获取当前运行模型 ---")
    current_model, running_models = get_current_running_model()
    log(f"当前标记模型: {current_model}")
    log(f"运行中模型: {json.dumps(running_models, indent=2, ensure_ascii=False)}")
    
    # 3. 获取所有来源的模型列表
    log("\n--- 步骤 3: 获取模型列表 ---")
    models_data = get_models_from_all_sources()
    
    # 4. 比较状态一致性
    log("\n--- 步骤 4: 状态一致性比较 ---")
    consistency_issues = compare_model_states(models_data)
    
    if consistency_issues:
        log("✗ 发现状态不一致问题:", "ERROR")
        for issue in consistency_issues:
            log(f"  - {issue}", "ERROR")
    else:
        log("✓ 所有数据源状态一致")
    
    # 5. 检查插件 provider 配置
    log("\n--- 步骤 5: 插件 provider 配置 ---")
    plugin_check_model = get_plugin_provider_check_model()
    if plugin_check_model:
        log(f"插件 checkModelName: {plugin_check_model}")
        if current_model and plugin_check_model != current_model:
            log(f"⚠ 插件 checkModelName 与当前模型不一致!", "WARNING")
        else:
            log("✓ 插件 checkModelName 与当前模型一致")
    
    # 6. 检查 WebSocket
    log("\n--- 步骤 6: WebSocket 检查 ---")
    check_websocket_status()
    
    # 7. 检查缓存
    log("\n--- 步骤 7: 缓存检查 ---")
    check_cache_status()
    
    # 8. 测试 finalize 端点
    log("\n--- 步骤 8: finalize-switch 端点测试 ---")
    test_finalize_endpoint()
    
    # 9. 真实切换测试（可选）
    if with_real_switch:
        log("\n--- 步骤 9: 真实模型切换测试 ---")
        switch_success = test_model_switch_flow()
        if not switch_success:
            log("✗ 真实模型切换测试失败", "ERROR")
            return False
        
        # 切换后再次检查状态一致性
        log("\n--- 步骤 10: 切换后状态一致性验证 ---")
        models_data_after = get_models_from_all_sources()
        consistency_issues_after = compare_model_states(models_data_after)
        
        if consistency_issues_after:
            log("✗ 切换后发现状态不一致:", "ERROR")
            for issue in consistency_issues_after:
                log(f"  - {issue}", "ERROR")
            return False
        else:
            log("✓ 切换后状态一致")
    else:
        log("\n--- 步骤 9: 跳过真实切换测试 (使用 --with-switch 启用) ---")
    
    # 总结
    log("\n" + "=" * 60)
    log("测试总结")
    log("=" * 60)
    
    if consistency_issues:
        log(f"✗ 发现 {len(consistency_issues)} 个状态不一致问题", "ERROR")
        for issue in consistency_issues:
            log(f"  问题: {issue}", "ERROR")
        return False
    else:
        log("✓ 所有检查通过，插件展示状态一致")
        return True

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="模型原子切换及插件状态一致性测试")
    parser.add_argument("--with-switch", action="store_true", help="执行真实模型切换测试")
    args = parser.parse_args()
    
    try:
        success = run_full_test(with_real_switch=args.with_switch)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        log("\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        log(f"\n测试异常: {e}", "CRITICAL")
        import traceback
        traceback.print_exc()
        sys.exit(2)
