#!/usr/bin/env python3
"""
Llama.cpp 推理测试脚本 - 简化版
"""
import sys
sys.path.insert(0, '/root/ai-os/venvs/llamacpp/lib/python3.13/site-packages')

from llama_cpp import Llama

print("=== Llama.cpp 推理测试 ===")
print(f"Python 版本: {sys.version}")

model_path = "/mnt/pve_models/Qwen3.6-35B-A3B-Uncensored/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive-Q8_K_P.gguf"

print(f"\n[1] 加载模型...")
print(f"    路径: {model_path}")

try:
    llm = Llama(
        model_path=model_path,
        n_ctx=512,
        n_threads=16,
        n_gpu_layers=0,
        use_mlock=True,
        verbose=False
    )
    print("[2] ✅ 模型加载成功！")
    print(f"    上下文长度: {llm.n_ctx()}")
    print(f"    Vocab 大小: {llm.n_vocab()}")

    print("\n[3] 执行推理...")
    print("    提示词: 'Hello, how are you?'")

    output = llm(
        "Hello, how are you?",
        max_tokens=128,
        temperature=0.8,
        top_p=0.95,
    )

    print("\n[4] ✅ 推理完成！")
    print("\n========== 生成结果 ==========")
    result = output['choices'][0]['text']
    print(result)
    print("================================\n")

    print("✅ Llama.cpp 推理测试成功！")

except KeyboardInterrupt:
    print("\n\n⚠️  测试被用户中断")
    sys.exit(0)
except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
