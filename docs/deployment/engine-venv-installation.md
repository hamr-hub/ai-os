# 推理引擎虚拟环境与安装管理

> vLLM / SGLang / llama.cpp 三引擎的 Python 虚拟环境创建、依赖安装与统一管理规范。

---

## 1. 目录结构

所有引擎虚拟环境统一安装于项目根目录下的 `venvs/` 目录：

```
ai-os/
├── venvs/
│   ├── vllm/          # vLLM 虚拟环境
│   ├── sglang/        # SGLang 虚拟环境
│   └── llamacpp/      # llama.cpp 虚拟环境
├── config.yaml        # 引擎配置（含 venv_path / env_vars）
├── app-controller/    # Python 后端（LLMServiceManager）
└── ...
```

> **约定**: `venvs/` 下每个子目录对应一个引擎，目录名与 `engine_type` 一致。

---

## 2. config.yaml 路径映射

`config.yaml` 中各引擎的 `venv_path` 配置应指向 `venvs/` 下的对应目录：

| engine_type | venv_path (当前)            | venv_path (目标)            |
|-------------|----------------------------|----------------------------|
| vllm        | `/root/ai-suite/vllm_env`  | `/root/ai-os/venvs/vllm`   |
| sglang      | (待配置)                    | `/root/ai-os/venvs/sglang` |
| llamacpp    | (待配置)                    | `/root/ai-os/venvs/llamacpp` |

当前 vLLM 的 `venv_path` 位于 `/root/ai-suite/vllm_env`（历史路径），需迁移到统一的 `venvs/vllm`。SGLang 和 llama.cpp 的 venv_path 尚未在 config.yaml 中配置，添加引擎时需补充。

---

## 3. 各引擎安装方法

### 3.1 vLLM

#### 前置依赖

- Python 3.10 – 3.12
- CUDA 12.1+ (推荐 12.4)
- NVIDIA GPU (计算能力 7.0+)
- `gcc` / `g++` (编译 CUDA 内核)

#### 创建虚拟环境并安装

```bash
# 创建虚拟环境
python3 -m venv venvs/vllm
source venvs/vllm/bin/activate

# 安装 vLLM (含 CUDA 支持)
pip install vllm

# 验证安装
python -c "import vllm; print(vllm.__version__)"
```

#### 关键环境变量 (config.yaml → env_vars)

| 变量                        | 值  | 说明                     |
|-----------------------------|-----|--------------------------|
| `VLLM_USE_V1`               | 1   | 启用 V1 引擎架构         |
| `NCCL_P2P_DISABLE`          | 1   | 禁用 NCCL P2P (单机场景) |
| `NCCL_SOCKET_REUSEPORT`     | 1   | 端口重用                 |
| `NCCL_ASYNC_ERROR_HANDLING` | 1   | 异步错误处理             |
| `NCCL_IB_DISABLE`           | 1   | 禁用 InfiniBand          |
| `CUDA_MANAGED_FORCE_DEVICE_ALLOC` | 1 | 强制设备内存分配     |
| `OMP_NUM_THREADS`           | 16  | OpenMP 线程数            |
| `VLLM_NO_FLASHINFER`        | 1   | 禁用 FlashInfer          |
| `FLASHINFER_DISABLE`        | 1   | FlashInfer 禁用          |

#### 启动命令格式

```bash
vllm serve <model_path> \
  --host 0.0.0.0 \
  --port 8000 \
  --trust-remote-code \
  --gpu-memory-utilization 0.92 \
  --max-model-len 32768 \
  --kv-cache-dtype auto \
  --enforce-eager
```

> 启动脚本: `app-controller/scripts/start_vllm_aiclient.sh`

---

### 3.2 SGLang

#### 前置依赖

- Python 3.9 – 3.12
- CUDA 12.1+ (推荐 12.4)
- NVIDIA GPU (计算能力 7.0+)
- `gcc` / `g++`

#### 创建虚拟环境并安装

```bash
# 创建虚拟环境
python3 -m venv venvs/sglang
source venvs/sglang/bin/activate

# 安装 SGLang (含 CUDA 后端)
pip install sglang[all]

# 或指定 sgl 链式安装
# pip install "sglang[all]>=0.4.0"

# 验证安装
python -c "import sglang; print('SGLang installed')"
```

#### 关键环境变量

SGLang 的环境变量与 vLLM 类似，但部分参数通过 CLI 传递：

| 变量                        | 值  | 说明                     |
|-----------------------------|-----|--------------------------|
| `NCCL_P2P_DISABLE`          | 1   | 禁用 NCCL P2P            |
| `NCCL_IB_DISABLE`           | 1   | 禁用 InfiniBand          |

#### 启动命令格式

```bash
python -m sglang.launch_server \
  --model-path <model_path> \
  --host 0.0.0.0 \
  --port 8100 \
  --tp 1 \
  --mem-fraction-static 0.90 \
  --trust-remote-code \
  --log-level info
```

> config.yaml 中 `engines.sglang.default_port: 8100`

---

### 3.3 llama.cpp (llama_cpp server)

#### 前置依赖

- Python 3.8 – 3.12
- CUDA 12.x (可选，GPU 推理需要)
- `cmake` / `gcc` (编译 C++ 后端)

#### 创建虚拟环境并安装

```bash
# 创建虚拟环境
python3 -m venv venvs/llamacpp
source venvs/llamacpp/bin/activate

# 安装 llama-cpp-python (含 CUDA 后端)
CMAKE_ARGS="-DGGML_CUDA=on" pip install llama-cpp-python[server]

# 验证安装
python -c "import llama_cpp; print('llama-cpp-python installed')"
```

> **注意**: `CMAKE_ARGS="-DGGML_CUDA=on"` 必须在安装时设置，否则只编译 CPU 后端。

#### Metal 后端 (macOS)

```bash
CMAKE_ARGS="-DGGML_METAL=on" pip install llama-cpp-python[server]
```

#### 启动命令格式

```bash
python -m llama_cpp.server \
  --model <gguf_model_path> \
  --host 0.0.0.0 \
  --port 8001 \
  -ngl -1 \
  -c 4096 \
  -b 512
```

> config.yaml 中 `llama_cpp.server_module: llama_cpp.server`

---

## 4. 虚拟环境激活方式

LLMServiceManager 使用 subprocess 模式启动引擎进程时，自动从 config.yaml 读取 `venv_path` 并激活：

```python
# 伪代码: LLMServiceManager 启动逻辑
venv_path = config["engines"][engine_type]["venv_path"]
activate_script = f"{venv_path}/bin/activate"
# subprocess 启动时先 source activate 再执行引擎命令
```

> 启动脚本 `start_vllm_aiclient.sh` 的 `resolve_venv_path()` 搜索顺序:
> 1. `VLLM_ENV_PATH` 环境变量
> 2. `$SCRIPT_DIR/vllm_env`
> 3. `$PROJECT_ROOT/.venv-vllm`
> 4. `/root/ai-suite/vllm_env`
>
> 迁移后应统一为 `$PROJECT_ROOT/venvs/vllm`。

---

## 5. 引擎切换与参数覆盖

各引擎的参数 Schema 定义在 `app-controller/core/engine_param_schema.py`：

| 引擎      | 参数组数 | 核心参数示例                                  |
|-----------|----------|----------------------------------------------|
| vllm      | 6 组     | gpu_memory_utilization, max_model_len, attention_backend |
| sglang    | 8 组     | mem_fraction_static, context_length, tp_size, schedule_policy |
| llamacpp  | 4 组     | n_gpu_layers, ctx_size, batch_size, flash_attn |

每个模型可在 config.yaml 中覆盖默认参数（如 `vllm_params` 字段），或通过前端 EngineParamEditor 实时调整。

---

## 6. 运维操作速查

### 创建所有虚拟环境

```bash
#!/bin/bash
PROJECT_ROOT="/root/ai-os"

mkdir -p "$PROJECT_ROOT/venvs"

# vLLM
python3 -m venv "$PROJECT_ROOT/venvs/vllm"
source "$PROJECT_ROOT/venvs/vllm/bin/activate"
pip install vllm
deactivate

# SGLang
python3 -m venv "$PROJECT_ROOT/venvs/sglang"
source "$PROJECT_ROOT/venvs/sglang/bin/activate"
pip install "sglang[all]"
deactivate

# llama.cpp
python3 -m venv "$PROJECT_ROOT/venvs/llamacpp"
source "$PROJECT_ROOT/venvs/llamacpp/bin/activate"
CMAKE_ARGS="-DGGML_CUDA=on" pip install llama-cpp-python[server]
deactivate
```

### 更新单个引擎依赖

```bash
source venvs/<engine>/bin/activate
pip install --upgrade <package>
deactivate
```

### 检查虚拟环境健康状态

```bash
source venvs/<engine>/bin/activate
python -c "import <package>; print(<package>.__version__)"
deactivate
```

### 清理重建虚拟环境

```bash
rm -rf venvs/<engine>
python3 -m venv venvs/<engine>
source venvs/<engine>/bin/activate
pip install <package>
deactivate
```

---

## 7. 版本兼容矩阵

| 引擎      | Python    | CUDA       | 推荐 GPU              | pip 包名              |
|-----------|-----------|------------|----------------------|-----------------------|
| vLLM      | 3.10-3.12 | 12.1+      | Ampere+ (SM 80+)     | `vllm`                |
| SGLang    | 3.9-3.12  | 12.1+      | Ampere+ (SM 80+)     | `sglang[all]`         |
| llama.cpp | 3.8-3.12  | 12.x (可选) | 任何 CUDA/Metal GPU  | `llama-cpp-python[server]` |

> vLLM 与 SGLang 共享 PyTorch/CUDA 生态，但依赖版本可能冲突，必须使用独立虚拟环境。llama.cpp 依赖链最短，冲突风险最低。

---

## 8. config.yaml venv_path 迁移计划

将现有分散路径统一到 `venvs/` 下：

```yaml
vllm:
  venv_path: /root/ai-os/venvs/vllm     # 从 /root/ai-suite/vllm_env 迁移

engines:
  sglang:
    venv_path: /root/ai-os/venvs/sglang  # 新增
  llamacpp:
    venv_path: /root/ai-os/venvs/llamacpp  # 新增
```

迁移步骤：
1. 创建 `venvs/vllm` 并迁移或重建
2. 更新 `config.yaml` 的 `vllm.venv_path`
3. 更新 `start_vllm_aiclient.sh` 的 `resolve_venv_path()` 搜索列表
4. 验证 vLLM 启动正常
5. 为 SGLang / llama.cpp 添加 `venv_path` 配置
