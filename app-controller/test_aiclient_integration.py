import asyncio
import httpx
import json
import sys

async def test_aiclient_interface():
    """测试 AIClient2API 与 app-controller 的集成"""
    
    # 从配置文件读取 app-controller 地址
    import os
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    
    # 默认使用配置中的端口
    base_url = "http://localhost:35000"
    
    print(f"测试目标: {base_url}")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=httpx.Timeout(30)) as client:
        # 测试 1: 获取模型列表
        print("\n[测试 1] 获取模型列表 /v1/models")
        try:
            response = await client.get(f"{base_url}/v1/models")
            response.raise_for_status()
            data = response.json()
            print(f"✓ 成功获取 {len(data.get('data', []))} 个模型")
            for model in data.get('data', []):
                print(f"  - {model['id']} (运行中: {model.get('running', False)})")
        except Exception as e:
            print(f"✗ 失败: {e}")
        
        # 测试 2: 健康检查
        print("\n[测试 2] 健康检查 /health")
        try:
            response = await client.get(f"{base_url}/health")
            response.raise_for_status()
            data = response.json()
            print(f"✓ 状态: {data.get('status')}, 健康分数: {data.get('health_score')}")
        except Exception as e:
            print(f"✗ 失败: {e}")
        
        # 测试 3: 获取 GPU 状态
        print("\n[测试 3] 获取 GPU 状态 /manage/gpu")
        try:
            response = await client.get(f"{base_url}/manage/gpu")
            response.raise_for_status()
            data = response.json()
            if data.get('status') == 'available':
                print(f"✓ GPU: {data.get('name')}")
                print(f"  显存: {data.get('used_memory', 0) // (1024**3)}GB / {data.get('total_memory', 0) // (1024**3)}GB")
                print(f"  温度: {data.get('temperature')}°C, 利用率: {data.get('utilization')}%")
            else:
                print(f"✗ GPU 不可用: {data.get('message')}")
        except Exception as e:
            print(f"✗ 失败: {e}")
        
        # 测试 4: 获取模型状态
        print("\n[测试 4] 获取模型状态 /manage/models")
        try:
            response = await client.get(f"{base_url}/manage/models")
            response.raise_for_status()
            data = response.json()
            print(f"✓ 获取 {len(data)} 个模型状态")
            for model_name, status in data.items():
                status_str = "🟢 运行中" if status['running'] else "🔴 停止"
                print(f"  - {model_name}: {status_str}")
        except Exception as e:
            print(f"✗ 失败: {e}")
        
        # 测试 5: Node.js 集成状态检查
        print("\n[测试 5] Node.js 集成状态 /api/v1/status")
        try:
            response = await client.get(f"{base_url}/api/v1/status")
            response.raise_for_status()
            data = response.json()
            print(f"✓ 服务: {data.get('service')}, 状态: {data.get('status')}")
            print(f"  GPU 可用: {data.get('gpu', {}).get('available', False)}")
            print(f"  模型数量: {len(data.get('models', {}))}")
        except Exception as e:
            print(f"✗ 失败: {e}")
        
        # 测试 6: 测试聊天补全（仅当有模型运行时）
        print("\n[测试 6] 测试聊天补全 /v1/chat/completions")
        try:
            # 先检查是否有运行中的模型
            response = await client.get(f"{base_url}/manage/models")
            response.raise_for_status()
            models_data = response.json()
            
            running_models = [name for name, status in models_data.items() if status['running']]
            
            if running_models:
                model_name = running_models[0]
                print(f"  使用模型: {model_name}")
                
                payload = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": "Hello, how are you?"}],
                    "max_tokens": 50,
                    "stream": False
                }
                
                response = await client.post(f"{base_url}/v1/chat/completions", json=payload)
                response.raise_for_status()
                data = response.json()
                
                if 'choices' in data and data['choices']:
                    content = data['choices'][0]['message']['content']
                    print(f"✓ 响应成功")
                    print(f"  回复: {content[:100]}..." if len(content) > 100 else f"  回复: {content}")
                else:
                    print(f"✗ 响应格式错误: {data}")
            else:
                print("⚠ 没有运行中的模型，跳过此测试")
        except Exception as e:
            print(f"✗ 失败: {e}")
    
    print("\n" + "=" * 60)
    print("测试完成")

if __name__ == "__main__":
    asyncio.run(test_aiclient_interface())