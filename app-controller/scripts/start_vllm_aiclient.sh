#!/bin/bash

# ===== 1. 获取脚本目录 =====
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ===== 2. 激活虚拟环境 =====
source "/root/ai-suite/vllm_env/bin/activate"

# ===== 3. 终端颜色支持 =====
export TERM=xterm-256color

# ===== 4. 核心稳定参数 =====
export VLLM_ATTENTION_BACKEND=FLASHINFER
export VLLM_USE_V1=0
export NCCL_P2P_DISABLE=1
export CUDA_MANAGED_FORCE_DEVICE_ALLOC=1
export OMP_NUM_THREADS=16

# ===== 5. 模型路径（从环境变量读取，提供默认值）=====
MODEL_PATH="${VLLM_MODEL_PATH:-/mnt/pve_models/Gemma-4-31B-Abliterated}"

# ===== 6. 日志配置 =====
LOG_DIR="${SCRIPT_DIR}/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/vllm_aiclient_$(date +%Y%m%d_%H%M%S).log"

# ===== 7. 等待模型目录就绪 =====
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 等待模型目录就绪: $MODEL_PATH" | tee -a "$LOG_FILE"
sleep 10
while [ ! -d "$MODEL_PATH" ]; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 模型目录不存在，5秒后重试..." | tee -a "$LOG_FILE"
    sleep 5
done
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 模型目录已就绪" | tee -a "$LOG_FILE"

# ===== 8. 记录 GPU 状态 =====
echo "[$(date '+%Y-%m-%d %H:%M:%S')] GPU 状态:" | tee -a "$LOG_FILE"
nvidia-smi --query-gpu=index,name,memory.total,memory.free --format=csv | tee -a "$LOG_FILE"

# ===== 9. 启动 vLLM =====
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 启动 vLLM 服务，模型: $MODEL_PATH" | tee -a "$LOG_FILE"

exec vllm serve "$MODEL_PATH" \
  --trust-remote-code \
  --gpu-memory-utilization 0.92 \
  --max-model-len 32768 \
  --host 0.0.0.0 \
  --kv-cache-dtype fp8 \
  --enable-chunked-prefill \
  --max-num-batched-tokens 16384 \
  --max-num-seqs 32 \
  2>&1 | tee -a "$LOG_FILE"
