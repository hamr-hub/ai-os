#!/bin/bash

set -euo pipefail

# ===== 1. 获取脚本目录 =====
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

resolve_venv_path() {
    local candidates=()

    if [ -n "${VLLM_ENV_PATH:-}" ]; then
        candidates+=("$VLLM_ENV_PATH")
    fi

    candidates+=(
        "$SCRIPT_DIR/vllm_env"
        "$PROJECT_ROOT/.venv-vllm"
        "/root/ai-suite/vllm_env"
    )

    for candidate in "${candidates[@]}"; do
        if [ -f "$candidate/bin/activate" ]; then
            echo "$candidate"
            return 0
        fi
    done

    return 1
}

# ===== 2. 激活虚拟环境 =====
VLLM_ENV_DIR="$(resolve_venv_path || true)"
if [ -z "$VLLM_ENV_DIR" ]; then
    echo "未找到 vLLM 虚拟环境，请设置 VLLM_ENV_PATH 或创建 /root/ai-suite/vllm_env" >&2
    exit 1
fi
source "$VLLM_ENV_DIR/bin/activate"

# ===== 3. 终端颜色支持 =====
export TERM=xterm-256color

# ===== 4. 核心稳定参数 =====
export VLLM_ATTENTION_BACKEND=FLASHINFER
export VLLM_USE_V1=0
export NCCL_P2P_DISABLE=1
export CUDA_MANAGED_FORCE_DEVICE_ALLOC=1
export OMP_NUM_THREADS=16

# ===== 5. 模型路径（从环境变量读取，提供默认值）=====
MODEL_STATE_FILE="${VLLM_MODEL_STATE_FILE:-$SCRIPT_DIR/.vllm_model_path}"
if [ -n "${VLLM_MODEL_PATH:-}" ]; then
    MODEL_PATH="$VLLM_MODEL_PATH"
elif [ -f "$MODEL_STATE_FILE" ]; then
    MODEL_PATH="$(tr -d '\r\n' < "$MODEL_STATE_FILE")"
else
    MODEL_PATH="/mnt/pve_models/Gemma-4-31B-Abliterated"
fi

# ===== 6. 日志配置 =====
LOG_DIR="${VLLM_LOG_DIR:-${PROJECT_ROOT}/logs/vllm-aiclient}"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/vllm_aiclient_$(date +%Y%m%d_%H%M%S).log"

# ===== 7. vLLM 服务端口 (默认 8000) =====
VLLM_PORT="${VLLM_PORT:-8000}"

# ===== 8. 等待模型目录就绪 =====
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 等待模型目录就绪: $MODEL_PATH" | tee -a "$LOG_FILE"
sleep 10
while [ ! -d "$MODEL_PATH" ]; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 模型目录不存在，5秒后重试..." | tee -a "$LOG_FILE"
    sleep 5
done
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 模型目录已就绪" | tee -a "$LOG_FILE"

# ===== 9. 记录 GPU 状态 =====
echo "[$(date '+%Y-%m-%d %H:%M:%S')] GPU 状态:" | tee -a "$LOG_FILE"
nvidia-smi --query-gpu=index,name,memory.total,memory.free --format=csv | tee -a "$LOG_FILE"

# ===== 10. 启动 vLLM =====
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 启动 vLLM 服务，模型: $MODEL_PATH, 端口: $VLLM_PORT" | tee -a "$LOG_FILE"

exec vllm serve "$MODEL_PATH" \
  --trust-remote-code \
  --gpu-memory-utilization 0.92 \
  --max-model-len 32768 \
  --host 0.0.0.0 \
  --port "$VLLM_PORT" \
  --kv-cache-dtype fp8 \
  --enable-chunked-prefill \
  --max-num-batched-tokens 16384 \
  --max-num-seqs 32 \
  2>&1 | tee -a "$LOG_FILE"
