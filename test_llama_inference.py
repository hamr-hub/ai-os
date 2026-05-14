#!/usr/bin/env python3
"""
Llama.cpp 推理测试脚本
"""
import sys
sys.path.insert(0, '/root/ai-os/venvs/llamacpp/lib/python3.13/site-packages')

from llama_cpp import Llama
from llama_cpp.llama_chat_format import LlamaChatCompletionHandler

print("=== Llama.cpp 推理测试 ===")
print(f"Python 版本: {sys.version}")
print(f"llama_cpp_python 版本: {Llama.__module__}")

model_path = "/mnt/pve_models/Qwen3.6-35B-A3B-Uncensored/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive-Q8_K_P.gguf"

print(f"\n[1] 加载模型: {model_path}")
print("这可能需要几分钟...")

llm = Llama(
    model_path=model_path,
    n_ctx=2048,
    n_threads=16,
    n_gpu_layers=0,
    verbose=False
)

print("[2] 模型加载完成！")
print(f"   上下文长度: {llm.n_ctx()}")
print(f"   Vocab 大小: {llm.n_vocab()}")

print("\n[3] 执行推理测试...")

output = llm(
    "请简要介绍一下自己。",
    max_tokens=256,
    temperature=0.7,
    stop=["<|im_end|>", "<<STOP>>"]
)

print("[4] 推理完成！")
print("\n=== 生成结果 ===")
print(output['choices'][0]['text'])
print("\n✅ Llama.cpp 推理测试成功！")
