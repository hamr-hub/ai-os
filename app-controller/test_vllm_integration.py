import requests
import json
import time

CONTROLLER_URL = "http://localhost:5000"
VLLM_URL = "http://localhost:8000"

def test_vllm_direct():
    print("=== 直接测试 vLLM 服务 ===")
    try:
        response = requests.get(f"{VLLM_URL}/v1/models")
        if response.status_code == 200:
            models = response.json()
            print(f"vLLM服务状态: ✅ 正常运行")
            print(f"可用模型: {[m['id'] for m in models.get('data', [])]}")
        else:
            print(f"vLLM服务状态: ❌ 异常 (状态码: {response.status_code})")
    except Exception as e:
        print(f"vLLM服务状态: ❌ 连接失败 - {e}")

def test_controller_models():
    print("\n=== 测试 AI Controller 模型列表 ===")
    try:
        response = requests.get(f"{CONTROLLER_URL}/v1/models")
        if response.status_code == 200:
            models = response.json()
            print(f"Controller状态: ✅ 正常运行")
            print(f"配置的模型: {[m['id'] for m in models.get('data', [])]}")
        else:
            print(f"Controller状态: ❌ 异常 (状态码: {response.status_code})")
    except Exception as e:
        print(f"Controller状态: ❌ 连接失败 - {e}")

def test_controller_gpu():
    print("\n=== 测试 GPU 监控 ===")
    try:
        response = requests.get(f"{CONTROLLER_URL}/manage/gpu")
        if response.status_code == 200:
            gpu_status = response.json()
            print(f"GPU状态: ✅")
            if gpu_status.get('status') != 'unavailable':
                print(f"  - GPU型号: {gpu_status.get('name', '未知')}")
                print(f"  - 显存使用: {gpu_status.get('used_memory', '0')} / {gpu_status.get('total_memory', '0')}")
                print(f"  - 显存占用率: {gpu_status.get('memory_utilization', '0')}%")
                print(f"  - 温度: {gpu_status.get('temperature', '0')}°C")
            else:
                print("  - 未检测到GPU")
        else:
            print(f"GPU监控: ❌ 异常 (状态码: {response.status_code})")
    except Exception as e:
        print(f"GPU监控: ❌ 连接失败 - {e}")

def test_controller_health():
    print("\n=== 测试 Controller 健康检查 ===")
    try:
        response = requests.get(f"{CONTROLLER_URL}/health")
        if response.status_code == 200:
            health = response.json()
            print(f"健康状态: {'✅ 健康' if health.get('status') == 'healthy' else '❌ 异常'}")
            print(f"健康分数: {health.get('health_score', 0)}/100")
        else:
            print(f"健康检查: ❌ 异常 (状态码: {response.status_code})")
    except Exception as e:
        print(f"健康检查: ❌ 连接失败 - {e}")

def test_controller_chat():
    print("\n=== 测试 Controller 聊天接口 ===")
    try:
        payload = {
            "model": "gemma-4-31b",
            "messages": [{"role": "user", "content": "Hello! What is AI?"}],
            "max_tokens": 100,
            "temperature": 0.7
        }
        
        print(f"请求模型: {payload['model']}")
        print(f"请求消息: {payload['messages'][0]['content']}")
        
        start_time = time.time()
        response = requests.post(f"{CONTROLLER_URL}/v1/chat/completions", json=payload)
        latency = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            print(f"响应状态: ✅ 成功")
            print(f"响应延迟: {latency:.2f}s")
            print(f"响应ID: {result.get('id', '')}")
            if 'choices' in result and len(result['choices']) > 0:
                content = result['choices'][0]['message'].get('content', '')
                print(f"响应内容: {content[:200]}..." if len(content) > 200 else f"响应内容: {content}")
        else:
            print(f"响应状态: ❌ 失败 (状态码: {response.status_code})")
            print(f"错误信息: {response.text}")
            
    except Exception as e:
        print(f"聊天接口测试: ❌ 连接失败 - {e}")

def test_vllm_direct_chat():
    print("\n=== 直接测试 vLLM 聊天接口 ===")
    try:
        payload = {
            "model": "/mnt/pve_models/Gemma-4-31B-Abliterated",
            "messages": [{"role": "user", "content": "Hello! What is AI?"}],
            "max_tokens": 50,
            "temperature": 0.7
        }
        
        print(f"请求模型: {payload['model']}")
        print(f"请求消息: {payload['messages'][0]['content']}")
        
        start_time = time.time()
        response = requests.post(f"{VLLM_URL}/v1/chat/completions", json=payload)
        latency = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            print(f"响应状态: ✅ 成功")
            print(f"响应延迟: {latency:.2f}s")
            print(f"响应ID: {result.get('id', '')}")
            if 'choices' in result and len(result['choices']) > 0:
                content = result['choices'][0]['message'].get('content', '')
                print(f"响应内容: {content[:200]}..." if len(content) > 200 else f"响应内容: {content}")
        else:
            print(f"响应状态: ❌ 失败 (状态码: {response.status_code})")
            print(f"错误信息: {response.text}")
            
    except Exception as e:
        print(f"vLLM直接测试: ❌ 连接失败 - {e}")

def test_model_management():
    print("\n=== 测试模型管理接口 ===")
    try:
        response = requests.get(f"{CONTROLLER_URL}/manage/models")
        if response.status_code == 200:
            model_status = response.json()
            print(f"模型状态获取: ✅ 成功")
            for model_name, status in model_status.items():
                status_icon = "🟢" if status.get('running') else "🔴"
                print(f"  {status_icon} {model_name}: running={status.get('running')}, active_requests={status.get('active_requests')}")
        else:
            print(f"模型状态获取: ❌ 失败 (状态码: {response.status_code})")
    except Exception as e:
        print(f"模型管理测试: ❌ 连接失败 - {e}")

def main():
    print("=" * 60)
    print("AI Controller 与 vLLM 服务联调测试")
    print("=" * 60)
    
    test_vllm_direct()
    test_controller_models()
    test_controller_gpu()
    test_controller_health()
    test_model_management()
    test_controller_chat()
    test_vllm_direct_chat()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    main()
