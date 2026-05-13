#!/bin/bash
# Install sglang dependencies on server - step by step with aria2c fallback
# For large packages: pip download with resume + aria2c retry
set -e

VENV=/root/ai-os/venvs/sglang
PIP="$VENV/bin/pip"
PY="$VENV/bin/python"
WDIR=/tmp/wheels_sglang
mkdir -p "$WDIR"

echo "=== [Step 1] Install torch (already done from local wheel) ==="
$PIP list | grep torch || {
    $PIP install --no-deps /tmp/wheels_sglang/torch-2.6.0+cu124-cp313-cp313-linux_x86_64.whl
}

echo "=== [Step 2] Install small deps ==="
$PIP install filelock typing-extensions networkx jinja2 fsspec sympy mpmath setuptools -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com --timeout 60

echo "=== [Step 3] Download+Install NVIDIA CUDA libs (with pip resume) ==="
# Use pip install directly - it handles resume internally
# Split into batches: small first, then large
echo "--- Small NVIDIA libs ---"
$PIP install nvidia-nvtx-cu12 nvidia-cuda-runtime-cu12 nvidia-cublas-cu12 nvidia-cufft-cu12 nvidia-curand-cu12 nvidia-cusparse-cu12 nvidia-cusolver-cu12 nvidia-cuda-cupti-cu12 nvidia-cuda-nvrtc-cu12 nvidia-nccl-cu12 -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com --timeout 600 --retries 10 2>&1 || echo "Some NVIDIA small libs may have failed"

echo "--- Large NVIDIA libs (cudnn, nvjitlink) with retry ---"
for pkg in nvidia-cudnn-cu12 nvidia-nvjitlink-cu12; do
    echo "Installing $pkg ..."
    for attempt in 1 2 3 4 5; do
        if $PIP install "$pkg" -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com --timeout 600 --retries 10 2>&1; then
            echo "$pkg installed!"
            break
        fi
        echo "Attempt $attempt failed for $pkg, retrying..."
        sleep 10
    done
done

echo "--- triton ---"
for attempt in 1 2 3 4 5; do
    if $PIP install triton -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com --timeout 600 --retries 10 2>&1; then
        break
    fi
    sleep 10
done

echo "=== [Step 4] Verify torch ==="
$PY -c "import torch; print(f'torch {torch.__version__}, CUDA available: {torch.cuda.is_available()}')" 2>&1 || echo "torch import still failing"

echo "=== [Step 5] Install sglang and remaining deps ==="
$PIP install sglang[all] -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com --timeout 600 --retries 10 2>&1 || {
    echo "Full sglang install failed, trying core sglang..."
    $PIP install sglang -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com --timeout 600 --retries 10 2>&1 || echo "sglang core also failed"
}

echo "=== [Step 6] Verify sglang ==="
$PY -c "import sglang; print('sglang imported successfully')" 2>&1 || echo "sglang import failed"

echo "=== ALL DONE ==="
