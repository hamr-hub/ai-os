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
export VLLM_ATTENTION_BACKEND=TRITON_ATTN
export VLLM_USE_V1=1
export NCCL_P2P_DISABLE=1
export NCCL_SOCKET_REUSEPORT=1
export NCCL_ASYNC_ERROR_HANDLING=1
export NCCL_IB_DISABLE=1
export CUDA_MANAGED_FORCE_DEVICE_ALLOC=1
export OMP_NUM_THREADS=16
export VLLM_NO_FLASHINFER=1
export FLASHINFER_DISABLE=1

# ===== 5. 模型路径（从环境变量读取，提供默认值）=====
MODEL_STATE_FILE="${VLLM_MODEL_STATE_FILE:-$SCRIPT_DIR/.vllm_model_path}"
if [ -n "${VLLM_MODEL_PATH:-}" ]; then
    MODEL_PATH="/mnt/pve_models/Gemma-4-31B-Abliterated"
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

# ===== 7.1 读取模型个性化 vLLM 参数 =====
VLLM_PARAMS_FILE="${SCRIPT_DIR}/.vllm_model_params.json"
if [ -f "$VLLM_PARAMS_FILE" ]; then
    GPU_MEMORY_UTILIZATION=$(python3 -c "import json; print(json.load(open('$VLLM_PARAMS_FILE')).get('gpu_memory_utilization', 0.92))")
    MAX_MODEL_LEN=$(python3 -c "import json; print(json.load(open('$VLLM_PARAMS_FILE')).get('max_model_len', 32768))")
    MAX_NUM_SEQS=$(python3 -c "import json; print(json.load(open('$VLLM_PARAMS_FILE')).get('max_num_seqs', 256))")
    MAX_NUM_BATCHED_TOKENS=$(python3 -c "import json; print(json.load(open('$VLLM_PARAMS_FILE')).get('max_num_batched_tokens', 16384))")
    ENABLE_CHUNKED_PREFILL=$(python3 -c "import json; v=json.load(open('$VLLM_PARAMS_FILE')).get('enable_chunked_prefill', True); print('true' if v else 'false')")
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 已加载模型个性化参数: gpu_memory_utilization=$GPU_MEMORY_UTILIZATION, max_model_len=$MAX_MODEL_LEN, max_num_seqs=$MAX_NUM_SEQS" | tee -a "$LOG_FILE"
else
    GPU_MEMORY_UTILIZATION="0.92"
    MAX_MODEL_LEN="32768"
    MAX_NUM_SEQS="256"
    MAX_NUM_BATCHED_TOKENS="16384"
    ENABLE_CHUNKED_PREFILL="true"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 未找到参数文件，使用默认值" | tee -a "$LOG_FILE"
fi

# 构建 chunked prefill 参数
CHUNKED_PREFILL_ARGS=""
if [ "$ENABLE_CHUNKED_PREFILL" = "true" ]; then
    CHUNKED_PREFILL_ARGS="--enable-chunked-prefill"
fi

# ===== 8. 等待模型目录就绪 =====
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 等待模型目录就绪: $MODEL_PATH" | tee -a "$LOG_FILE"
sleep 10
while [ ! -d "$MODEL_PATH" ]; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 模型目录不存在，5秒后重试..." | tee -a "$LOG_FILE"
    sleep 5
done
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 模型目录已就绪" | tee -a "$LOG_FILE"

# ===== 8.1 等待旧端口彻底释放 =====
wait_for_port_release() {
    local port="$1"
    local max_wait="${2:-60}"
    local waited=0

    while ss -lntp 2>/dev/null | grep -q ":${port} "; do
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 端口 ${port} 仍被占用，等待释放..." | tee -a "$LOG_FILE"
        sleep 1
        waited=$((waited + 1))
        if [ "$waited" -ge "$max_wait" ]; then
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] 端口 ${port} 长时间未释放，强制清理占用进程" | tee -a "$LOG_FILE"
            if command -v fuser >/dev/null 2>&1; then
                fuser -k "${port}/tcp" || true
            else
                pkill -f "vllm serve "/mnt/pve_models/Gemma-4-31B-Abliterated" --port ${port}" || true
            fi
            sleep 2
        fi
    done

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 端口 ${port} 已释放" | tee -a "$LOG_FILE"
}

wait_for_port_release "$VLLM_PORT" 90

# ===== 9. 记录 GPU 状态 =====
echo "[$(date '+%Y-%m-%d %H:%M:%S')] GPU 状态:" | tee -a "$LOG_FILE"
nvidia-smi --query-gpu=index,name,memory.total,memory.free --format=csv | tee -a "$LOG_FILE"

# ===== 10. 启动 vLLM =====
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 启动 vLLM 服务，模型: $MODEL_PATH, 端口: $VLLM_PORT" | tee -a "$LOG_FILE"

exec vllm serve "$MODEL_PATH" \
  --trust-remote-code \
  --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" \
  --max-model-len "$MAX_MODEL_LEN" \
  --host 0.0.0.0 \
  --port "$VLLM_PORT" \
  --kv-cache-dtype auto \
  $CHUNKED_PREFILL_ARGS \
  --max-num-batched-tokens "$MAX_NUM_BATCHED_TOKENS" \
  --max-num-seqs "$MAX_NUM_SEQS" \
  --enforce-eager \
  --enable-auto-tool-choice \
  --tool-call-parser gemma4 \
  2>&1 | tee -a "$LOG_FILE"
