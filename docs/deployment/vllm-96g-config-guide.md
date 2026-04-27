# 96G 显存 vLLM 模型部署配置指南

> 本文档针对 NVIDIA GPU 96GB 显存环境下部署各模型的推荐 vLLM 参数配置
> 
> 目标：避免 OOM（显存溢出），同时最大化模型性能

---

## 配置策略

### 显存分配原则

```
总显存(96GB) = 模型权重 + KV Cache + 激活值 + 安全余量
```

- **安全余量**: 至少保留 5-10GB 防止突发 OOM
- **gpu_memory_utilization**: 控制 vLLM 可使用显存的比例（不含模型权重）
- **KV Cache**: 主要显存消耗来源，由 `max_num_seqs` 和 `max_model_len` 决定

---

## 各模型推荐参数

### 1. 小型模型（30-40GB）

**适用模型:**
- Gemma-4-31B-Abliterated (40GB)
- Qwen3.6-35B-A3B (40GB)
- Qwen3.6-35B-A3B-NVFP4 (30GB)
- Qwen3.6-35B-A3B-Uncensored (40GB)

**推荐配置:**
```yaml
vllm_params:
  max_num_seqs: 256                # 最大并发序列数
  gpu_memory_utilization: 0.90     # GPU显存利用率
  max_model_len: 40960             # 最大上下文长度
  max_num_batched_tokens: 16384    # 最大批处理token数
  enable_chunked_prefill: true     # 启用分块预填充
```

**参数说明:**
- 可用显存约 50-60GB，空间充足
- 支持高并发（256个序列）
- 支持长上下文（40960 tokens）
- 适合高吞吐量场景

---

### 2. 中型模型（48GB）

**适用模型:**
- Qwen3-235B-A22B-Instruct-2507-AWQ (48GB)

**推荐配置:**
```yaml
vllm_params:
  max_num_seqs: 32                 # 降低并发数（MoE架构）
  gpu_memory_utilization: 0.75     # 降低利用率
  max_model_len: 8192              # 缩短上下文
  max_num_batched_tokens: 4096     # 减少批处理
  enable_chunked_prefill: true     # 启用分块预填充
```

**参数说明:**
- MoE 架构专家激活导致显存波动
- 可用显存约 48GB，需保守配置
- 并发数降至 32，防止峰值 OOM
- 上下文长度限制为 8192

---

### 3. 大型模型（70-80GB）

**适用模型:**
- llama-3.3-70b-8.0bpw (80GB)
- llama-3.3-70b-abliterated-gguf (80GB)
- llama-3.3-70b-exl2-6_5 (70GB)
- llama-3.3-70b-exl2-8_0 (80GB)
- qwen2.5-72b-exl2-8_0 (80GB)

**推荐配置:**
```yaml
vllm_params:
  max_num_seqs: 64                 # 中等并发
  gpu_memory_utilization: 0.85     # 保守利用率
  max_model_len: 16384             # 中等上下文
  max_num_batched_tokens: 8192     # 适中批处理
  enable_chunked_prefill: true     # 启用分块预填充
```

**参数说明:**
- 可用显存仅 16-26GB，非常紧张
- 必须降低并发和上下文长度
- 启用 chunked prefill 减少峰值显存
- 适合中等负载场景

---

### 4. 超大模型（>90GB）

**适用模型:**
- midnight-miqu-103b-5.0bpw (100GB)

**推荐配置:**
```yaml
vllm_params:
  max_num_seqs: 32                 # 低并发
  gpu_memory_utilization: 0.80     # 严格限制
  max_model_len: 8192              # 短上下文
  max_num_batched_tokens: 4096     # 小批处理
  enable_chunked_prefill: true     # 必须启用分块
```

**参数说明:**
- 模型已超 96GB，依赖量化/卸载
- 可用显存极度紧张（<16GB）
- 最低并发和上下文限制
- 仅适合轻负载场景
- ⚠️ 可能仍然 OOM，建议更大显存 GPU

---

## 关键参数详解

### gpu_memory_utilization

控制 vLLM 可以使用的 GPU 显存比例（0.0-1.0）。

| 显存占用 | 推荐值 | 说明 |
|---------|--------|------|
| < 50GB  | 0.90   | 充分利用显存 |
| 50-80GB | 0.85   | 留足 buffer |
| > 80GB  | 0.75-0.80 | 严格限制 |

**计算公式:**
```
KV Cache 可用显存 = 总显存 × gpu_memory_utilization - 模型权重
```

### max_num_seqs

最大并发序列数（同时处理的请求数）。

| 模型大小 | 推荐值 | 影响 |
|---------|--------|------|
| 30-40GB | 256    | 高吞吐 |
| 70-80GB | 64     | 中等 |
| >90GB   | 32     | 保守 |

**显存影响:**
```
KV Cache ∝ max_num_seqs × max_model_len
```

### max_model_len

最大上下文长度（每个序列的最大 token 数）。

| 场景 | 推荐值 | 说明 |
|------|--------|------|
| 常规对话 | 8192 | 足够日常使用 |
| 长文档 | 16384-32768 | 需要更多显存 |
| 超大模型 | 8192 | 必须限制 |

### max_num_batched_tokens

单次批处理的最大 token 数。

- 通常设置为 `max_model_len / 2` 或 `max_num_seqs × 平均请求长度`
- 影响推理吞吐量和延迟

### enable_chunked_prefill

分块预填充，将长序列分块处理，减少峰值显存。

- **必须启用**，特别是对于大模型
- 略微增加延迟，但显著降低 OOM 风险

---

## 启动脚本示例

```bash
#!/bin/bash

# 激活虚拟环境
source /path/to/vllm_env/bin/activate

# 核心参数
export VLLM_ATTENTION_BACKEND=TRITON_ATTN
export VLLM_USE_V1=1
export NCCL_P2P_DISABLE=1
export CUDA_MANAGED_FORCE_DEVICE_ALLOC=1

# 启动 vLLM（以 llama-3.3-70b 为例）
exec vllm serve /mnt/pve_models/llama-3.3-70b-8.0bpw \
  --trust-remote-code \
  --gpu-memory-utilization 0.85 \
  --max-model-len 16384 \
  --host 0.0.0.0 \
  --port 8000 \
  --kv-cache-dtype auto \
  --enable-chunked-prefill \
  --max-num-batched-tokens 8192 \
  --max-num-seqs 64 \
  --enforce-eager \
  2>&1 | tee -a /var/log/vllm.log
```

---

## 故障排查

### OOM 错误处理

如果出现 `CUDA out of memory` 错误：

1. **降低 gpu_memory_utilization**
   ```bash
   --gpu-memory-utilization 0.80  # 从 0.90 降低
   ```

2. **减少 max_num_seqs**
   ```bash
   --max-num-seqs 32  # 从 64 降低
   ```

3. **缩短 max_model_len**
   ```bash
   --max-model-len 8192  # 从 16384 降低
   ```

4. **启用 chunked prefill**
   ```bash
   --enable-chunked-prefill
   ```

### 性能优化

如果性能不足：

1. **增加并发数**（如果显存允许）
   ```bash
   --max-num-seqs 128
   ```

2. **使用 Tensor Parallel**（多 GPU）
   ```bash
   --tensor-parallel-size 2
   ```

3. **启用 prefix caching**
   ```bash
   --enable-prefix-caching
   ```

---

## 配置文件位置

所有模型的推荐参数已写入:
```
/root/ai-os/app-controller/config.yaml
```

每个模型的 `vllm_params` 部分包含完整的推荐配置。

---

## 自动推荐

系统会根据模型显存需求自动推荐参数:

```python
from core.vllm_manager import _recommend_vllm_params

# 获取推荐参数
params = _recommend_vllm_params("llama-3.3-70b-8.0bpw", required_memory_gb=80, gpu_memory_gb=96)
print(params)
# 输出:
# {
#     "max_num_seqs": 64,
#     "gpu_memory_utilization": 0.85,
#     "max_model_len": 16384,
#     "max_num_batched_tokens": 8192,
#     "enable_chunked_prefill": true
# }
```

---

> 更新于 2026-04-27
