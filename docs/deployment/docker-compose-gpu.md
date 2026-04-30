# GPU 环境部署

## 架构说明

GPU 环境在标准生产部署基础上增加 NVIDIA GPU 支持，用于 vLLM 模型推理加速。

```
用户 → Nginx (30000) — B端管控面板
         ↓ (B端管控路径)
     Frontend/插件 → app-controller (35000) — Python 管控 (引擎启停/模型管理)
         ↓ (C端推理路径)
     aiclient2api (3000) — 开源项目+GPU插件, Node后端
         ↓ provider → go-vllm-api (35001) — vLLM限流代理
         ↓
     vLLM (8000, GPU) — 推理引擎
     Redis (6379) ← 缓存/限流
```

## 前置条件

- NVIDIA GPU（建议 24GB+ 显存）
- NVIDIA Driver >= 525.0
- NVIDIA Container Toolkit (nvidia-docker2)
- CUDA 12.1+

### 验证 GPU 环境

```bash
# 检查 GPU
nvidia-smi

# 检查 NVIDIA Container Toolkit
docker run --rm --gpus all nvidia/cuda:12.1.1-base-ubuntu22.04 nvidia-smi
```

## Docker Compose GPU 配置

根目录 `docker-compose.yml` 中 `ai-controller` 已包含 GPU 配置：

```yaml
ai-controller:
  build:
    context: ./app-controller
    dockerfile: Dockerfile
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: all
            capabilities: [gpu]
```

### 指定特定 GPU

```yaml
# 使用指定 GPU
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          device_ids: ['0']    # 使用第 0 号 GPU
          capabilities: [gpu]
```

## 模型配置

编辑 `config.yaml`（或挂载的配置文件）配置可用模型：

```yaml
models:
  Gemma-4-31B-Abliterated:
    service: vllm
    port: 8000
    required_memory: 40GB
    preload: true            # 启动时预加载
    keep_alive: true          # 保持常驻
    model_path: /mnt/pve_models/Gemma-4-31B-Abliterated
    supports_images: false

  Qwen3-235B-A22B-Instruct-2507-AWQ:
    service: vllm
    port: 8000
    required_memory: 120GB
    preload: false
    keep_alive: false
    model_path: /mnt/pve_models/Qwen3-235B-A22B-Instruct-2507-AWQ
    supports_images: false

settings:
  gpu_memory_utilization: 0.92
  default_max_model_len: 32768
  vllm:
    default_port: 8000
    model_base_path: /mnt/pve_models
```

### 模型路径挂载

```yaml
ai-controller:
  volumes:
    - /mnt/pve_models:/mnt/pve_models    # 模型文件目录
    - /var/run/docker.sock:/var/run/docker.sock  # Docker socket（用于管理 vLLM 容器）
```

## 启动步骤

### 1. 准备模型文件

```bash
# 确认模型文件目录
ls /mnt/pve_models/
# 预期：Gemma-4-31B-Abliterated/  Qwen3-235B-.../  ...

# 如需从其他位置挂载，修改 docker-compose.yml 的 volumes
```

### 2. 配置与启动

```bash
# 配置环境
cp .env.example .env
# 修改 SECRET_KEY 和 REDIS_URL=redis://redis:6379

# 启动全部服务
docker compose up -d

# 验证 GPU 可用
docker exec ai-os-controller nvidia-smi
```

### 3. 验证 vLLM 服务

```bash
# 检查模型管理列表（Python 管理接口）
curl http://localhost:35000/manage/models

# 检查 OpenAI 兼容模型列表（Go 推理接口）
curl http://localhost:35001/v1/models

# 发送测试请求
curl http://localhost:35001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Gemma-4-31B-Abliterated",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 50
  }'
```

## GPU 内存管理

### 显存策略

`config.yaml` 中的关键配置：

```yaml
settings:
  gpu_memory_utilization: 0.92   # GPU 显存利用率上限
  min_available_memory: 4GB       # 最小可用显存
  default_memory_strategy: balanced
  memory_flush_interval: 300      # 内存清理间隔（秒）
  memory_cleanup_delay: 5         # 清理延迟（秒）
```

### 多模型切换

同一 GPU 上同时只能运行一个模型（共用 8000 端口）。切换模型时：

1. 停止当前模型（释放显存）
2. 等待显存释放
3. 加载新模型

前端界面提供了"切换"按钮自动执行此流程。

### 显存监控

```bash
# 宿主机 GPU 状态
nvidia-smi -l 5   # 每 5 秒刷新

# 容器内 GPU 使用
docker exec ai-os-controller nvidia-smi

# 通过 API 查询
curl http://localhost:35000/manage/gpu
```

## 性能调优

### GPU 相关参数

| 参数 | 建议值 | 说明 |
|------|--------|------|
| `gpu_memory_utilization` | 0.85~0.95 | 过高可能 OOM |
| `default_max_model_len` | 8192~32768 | 根据模型和显存调整 |
| `concurrency_limit` | 16~32 | 并发推理请求数 |

### Docker 资源限制

```yaml
ai-controller:
  deploy:
    resources:
      limits:
        memory: 48G       # 限制内存使用
      reservations:
        devices:
          - driver: nvidia
            count: all
            capabilities: [gpu]
```

## 故障排查

### GPU 不可用

```bash
# 检查 NVIDIA 驱动
nvidia-smi

# 检查 Container Toolkit
dpkg -l | grep nvidia-container

# 重启 Docker daemon
sudo systemctl restart docker
```

### 模型加载失败

```bash
# 检查模型文件
ls -la /mnt/pve_models/<model-name>/

# 查看后端日志
docker compose logs -f ai-controller | grep -i "vllm\|model\|error"

# 检查显存
nvidia-smi --query-gpu=memory.used,memory.total --format=csv
```

### OOM (Out of Memory)

1. 降低 `gpu_memory_utilization` 到 0.85
2. 减小 `default_max_model_len`
3. 选择更小的量化模型
4. 确保 `min_available_memory` 设置合理

## 仅后端 + GPU 部署

如只需 GPU 推理服务，使用 `app-controller/docker-compose.yml`：

```bash
cd app-controller
docker compose up -d
```

此方式启动后端 + Redis，GPU 自动启用，端口 35000 + 6379。
