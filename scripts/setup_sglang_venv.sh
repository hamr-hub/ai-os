#!/bin/bash
# One-shot sglang venv setup script
# Prerequisites: torch wheel at /tmp/wheels_sglang/torch*.whl
set -e

VENV=/root/ai-os/venvs/sglang
PIP="$VENV/bin/pip"
PY="$VENV/bin/python"

echo "[1] Creating fresh venv..."
rm -rf "$VENV"
python3 -m venv "$VENV"

echo "[2] Upgrading pip..."
$PIP install --upgrade pip -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com 2>&1 | tail -2

echo "[3] Installing torch from local wheel..."
TORCH_WHL=$(ls /tmp/wheels_sglang/torch-2.11.0*.whl 2>/dev/null || ls /tmp/wheels_sglang/torch*.whl 2>/dev/null | head -1)
if [ -n "$TORCH_WHL" ]; then
    $PIP install --no-deps "$TORCH_WHL" 2>&1 | tail -2
else
    echo "No torch wheel found! Need aria2c download first."
    exit 1
fi

echo "[4] Installing torch deps (small packages)..."
$PIP install filelock typing-extensions networkx jinja2 fsspec sympy setuptools -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com --timeout 60 2>&1 | tail -2

echo "[5] Installing NVIDIA CUDA + triton..."
$PIP install nvidia-cublas-cu12 nvidia-cuda-cupti-cu12 nvidia-cuda-nvrtc-cu12 nvidia-cuda-runtime-cu12 nvidia-cudnn-cu12 nvidia-cufft-cu12 nvidia-curand-cu12 nvidia-cusolver-cu12 nvidia-cusparse-cu12 nvidia-nccl-cu12 nvidia-nvjitlink-cu12 nvidia-nvtx-cu12 nvidia-cusparselt-cu12 triton -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com --timeout 600 --retries 10 2>&1 | tail -3

echo "[6] Verify torch..."
$PY -c "import torch; v=torch.__version__; c=torch.cuda.is_available(); print(f'torch {v}, CUDA={c}')"

echo "[7] Installing sglang + remaining deps (excluding torch upgrade)..."
$PIP install sglang -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com --timeout 60 --no-deps 2>&1 | tail -2
$PIP install sglang[all] -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com --timeout 600 --retries 10 --no-deps 2>&1 | tail -5 || true

echo "[8] Installing individual sglang deps..."
for pkg in aiohttp anthropic fastapi flashinfer-python flashinfer-cubin transformers vllm uvicorn uvloop numpy pydantic orjson prometheus-client psutil requests scipy sentencepiece pillow tiktoken xgrammar outlines interegular msgspec IPython ninja packaging tqdm gguf easydict einops compressed-tensors cuda-python nvidia-ml-py openai mistral-common llguidance partial-json-parser pybase64 pyzmq watchfiles setproctitle py-spy torch_memory_saver torchao torchaudio torchvision torchcodec soundfile tiktoken timm datasets blobfile build modelscope; do
    echo "Installing $pkg..."
    $PIP install "$pkg" -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com --timeout 300 --retries 5 2>&1 | tail -1 || echo "  $pkg install failed, continuing..."
done

echo "[9] Verify sglang..."
$PY -c "import sglang; print('sglang imported OK')" 2>&1 || echo "sglang import failed"
$PY -c "from sglang import launch_server; print('launch_server OK')" 2>&1 || echo "launch_server import failed"

echo "[10] DONE!"
