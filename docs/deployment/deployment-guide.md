# 部署指南总览

> AI Flow 项目提供多种部署方式，适用于不同场景。本文档详细说明每种部署方式的架构、步骤和适用场景。

---

## 部署方式总览

| 部署方式 | 适用场景 | 技术栈 | 端口 | 详细文档 |
|---------|---------|--------|------|---------|
| **本地开发环境** | 前端开发、后端开发、热更新调试 | Node.js + Python + Go | 30001/35000/35001 | [开发环境部署](./docker-compose-dev.md) |
| **Docker 全栈生产** | 生产环境一键部署 (5 服务) | Docker Compose | 30000/3000/35000/35001 | [生产环境部署](./docker-compose-prod.md) |
| **GPU 加速环境** | 大模型推理 + vLLM GPU 加速 | Docker + NVIDIA GPU | 30000/3000/35000/35001 | [GPU 环境部署](./docker-compose-gpu.md) |
| **Nginx 30000 systemd** | 独立 Nginx 服务，生产静态文件 | Nginx + systemd | 30000 | [Nginx 部署](./nginx-30000-deployment.md) |
| **后端独立部署** | 仅后端 + Redis，API 服务 | Docker Compose | 35000/6379 | 本文档下方 |
| **单服务部署** | 独立部署单个服务 | 各服务 docker-compose | 各服务端口 | 本文档下方 |

---

## 部署方式详细对比

### 1. 本地开发环境

**适用场景**: 日常开发、调试、热更新、前端开发

**架构**:
```
用户 → 浏览器
         ↓
     Vite Dev Server (30001) — 前端热更新 (B端管控面板)
         ↓ (代理 → Python B端)
     Python FastAPI (35000) — 管理接口 /api/manage, /ws (引擎/模型管控)
         
     Go go-vllm-api (35001) — vLLM限流代理 /v1 (C端推理接口)
     aiclient2api (3000, Docker) — 开源项目+GPU插件 (Node后端, provider→Go)
     Redis (6379) — 缓存/限流

两条核心路径:
  C端推理: aiclient2api(Node) → provider → go-vllm-api → 推理引擎
  B端管控: Frontend/插件 → Python → 引擎启停/模型管理
```

**前置条件**:
- Node.js >= 18, pnpm >= 8
- Python >= 3.11
- Go >= 1.26
- Redis (本地或 Docker)

**启动方式**:
```bash
# 1. 启动 Redis
docker run -d --name ai-os-redis -p 6379:6379 redis:7.2-alpine

# 2. 启动 Python 后端
cd app-controller && pip install -r requirements.txt && python main.py

# 3. 启动 Go 后端
cd go-vllm-api && go run cmd/server/main.go --port 35001

# 4. 启动前端
cd frontend && pnpm install && pnpm dev

# 5. 启动 aiclient2api (开源项目+GPU插件, Node后端)
cd aiclient2api && docker compose up -d
```

**特点**:
- 每个服务独立运行
- 支持热更新
- 可使用 Vue DevTools 调试
- FastAPI 自动文档: http://localhost:35000/docs

---

### 2. Docker 全栈生产部署

**适用场景**: 生产环境一键部署、测试环境、演示环境

**架构**:
```
用户 → Nginx Frontend (30000)
         ↓ (Docker 网络代理)
     aiclient2api (3000) — API 网关
         ↓
     app-controller (35000) — Python 管理接口
     go-vllm-api (35001) — Go 推理接口
         ↓
     Redis (6379) — 缓存
```

**服务清单** (5 个容器):

| 服务 | 容器名 | 端口映射 | 说明 |
|------|--------|---------|------|
| redis | ai-os-redis | 6379:6379 | Redis 缓存 |
| ai-controller | ai-os-controller | 35000:35000 | Python FastAPI |
| go-vllm-api | ai-os-go-vllm-api | 35001:35001 | Go vLLM API |
| aiclient | ai-os-aiclient | 3000:3000 | 开源项目+GPU插件 (Node后端) |
| frontend | ai-os-frontend | 30000:80 | Nginx 前端 |

**启动方式**:
```bash
# 1. 准备配置
cp .env.example .env
# 编辑 .env，设置 SECRET_KEY、REDIS_URL=redis://redis:6379

# 2. 构建并启动
docker compose build
docker compose up -d

# 3. 验证服务
docker compose ps
curl http://localhost:30000
curl http://localhost:35000/health
curl http://localhost:35001/health
```

**特点**:
- 一键部署，包含所有服务
- 容器间通过 `ai-os-network` 网络通信
- 前端使用 Nginx 提供静态文件服务
- 自动健康检查和依赖管理
- 日志轮转配置

**安全建议**:
```yaml
# 仅对外暴露 30000 (前端)
redis:
  ports:
    - "127.0.0.1:6379:6379"  # 仅内网访问
ai-controller:
  ports:
    - "127.0.0.1:35000:35000"
go-vllm-api:
  ports:
    - "127.0.0.1:35001:35001"
aiclient:
  ports:
    - "127.0.0.1:3000:3000"
```

---

### 3. GPU 加速环境部署

**适用场景**: 大模型推理、vLLM GPU 加速、生产 GPU 服务器

**前置条件**:
- NVIDIA GPU (建议 24GB+ 显存)
- NVIDIA Driver >= 525.0
- NVIDIA Container Toolkit (nvidia-docker2)
- CUDA 12.1+

**GPU 配置**:
```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all          # 使用所有 GPU
          capabilities: [gpu]
          # 或指定 GPU:
          # device_ids: ['0'] # 仅使用 GPU 0
```

**启动方式**:
```bash
# 1. 验证 GPU 环境
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.1.1-base-ubuntu22.04 nvidia-smi

# 2. 准备模型文件
ls /mnt/pve_models/

# 3. 配置环境
cp .env.example .env
# 设置 SECRET_KEY 和 REDIS_URL=redis://redis:6379

# 4. 启动全栈服务
docker compose up -d

# 5. 验证 GPU 和模型
docker exec ai-os-controller nvidia-smi
curl http://localhost:35000/manage/models
curl http://localhost:35001/v1/models
```

**模型配置** (`config.yaml`):
```yaml
models:
  Gemma-4-31B-Abliterated:
    service: vllm
    port: 8000
    required_memory: 40GB
    preload: true
    keep_alive: true
    model_path: /mnt/pve_models/Gemma-4-31B-Abliterated

settings:
  gpu_memory_utilization: 0.92
  default_max_model_len: 32768
  vllm:
    default_port: 8000
    model_base_path: /mnt/pve_models
```

**显存管理**:
- 同一 GPU 同时只能运行一个模型
- 切换模型时自动停止当前模型并释放显存
- 可通过前端界面"切换"按钮自动执行

**性能调优参数**:

| 参数 | 建议值 | 说明 |
|------|--------|------|
| `gpu_memory_utilization` | 0.85~0.95 | GPU 显存利用率上限 |
| `default_max_model_len` | 8192~32768 | 根据显存调整 |
| `concurrency_limit` | 16~32 | 并发推理请求数 |

---

### 4. Nginx 30000 systemd 服务部署

**适用场景**: 生产环境独立 Nginx 服务、开机自启动、系统级管理

**架构**:
```
用户 → Nginx (30000)
         ↓ (反向代理)
     Python 后端 (<后端IP>:35000) — /api/*
     Go 后端 (<后端IP>:35001) — /v1/*
```

> **注意**: `<后端IP>` 需替换为实际后端服务器 IP，示例中使用 `192.168.7.103`。

**文件清单**:

| 文件 | 路径 | 说明 |
|------|------|------|
| Nginx 配置 | `/etc/nginx/nginx_30000.conf` | 独立配置文件 |
| Systemd 服务 | `/etc/systemd/system/nginx-30000.service` | 服务单元文件 |
| 前端构建 | `/root/ai-os/frontend/dist` | 前端生产构建目录 |

**启动方式**:
```bash
# 1. 构建前端
cd /root/ai-os/frontend && pnpm build

# 2. 安装配置文件
sudo cp /root/ai-os/frontend/nginx_30000.conf /etc/nginx/nginx_30000.conf
sudo cp /root/ai-os/frontend/nginx-30000.service /etc/systemd/system/nginx-30000.service

# 3. 启动服务
sudo systemctl daemon-reload
sudo systemctl enable nginx-30000.service
sudo systemctl start nginx-30000.service

# 4. 验证
sudo systemctl status nginx-30000.service
curl http://localhost:30000
```

**后端代理路由**:

| 路径 | 目标 | 说明 |
|------|------|------|
| `/api/manage/` | `<后端IP>:35000/manage/` | Python 管理接口 |
| `/api/health` | `<后端IP>:35001/health` | Go 健康检查 |
| `/api/` | `<后端IP>:35000/manage/` | Python 通用接口 |
| `/v1/` | `<后端IP>:35001/v1/` | Go vLLM 接口 |
| `/manage/` | `<后端IP>:35000/manage/` | Python 管理接口 |
| `/ws/` | `<后端IP>:35000/ws/` | Python WebSocket |
| `/health` | `<后端IP>:35001/health` | Go 健康检查 |

> **注意**: `<后端IP>` 需替换为实际后端服务器 IP，示例中使用 `192.168.7.103`。

**特点**:
- 独立 PID 文件，与系统 Nginx 不冲突
- systemd 管理，支持开机自启动
- 直接使用 `dist` 目录，无需额外复制

---

### 5. 后端独立部署

**适用场景**: 仅需要后端 API 服务、不依赖前端、GPU 推理服务

**a. Python 后端 + Redis** (`app-controller/docker-compose.yml`):
```bash
cd app-controller
docker compose up -d
# 启动: Python 后端 (35000) + Redis (6379)
# 自动启用 GPU (如果可用)
```

**b. Go 后端 + Redis** (`go-vllm-api/docker-compose.yml`):
```bash
cd go-vllm-api
docker compose up -d
# 启动: Go vLLM API (35001) + Redis (6379)
# 自动启用 GPU (如果可用)
```

**特点**:
- 轻量级部署，仅启动所需服务
- 自动包含 Redis 依赖
- GPU 自动启用 (如果配置了 NVIDIA Container Toolkit)
- 适合微服务架构或独立 API 服务

---

### 6. 单服务独立部署

**适用场景**: 独立部署单个服务、测试、微服务架构

**a. API 网关** (`aiclient2api/docker-compose.yml`):
```bash
cd aiclient2api
docker compose up -d
# 启动: aiclient2api (3000)
# 需要配置 configs/provider_pools.json 指向后端
```

**b. 仅 Redis**:
```bash
docker run -d --name ai-os-redis -p 6379:6379 redis:7.2-alpine
# 或使用各服务自带的 Redis
```

**特点**:
- 灵活部署单个服务
- 适合微服务架构
- 需要手动配置服务间依赖

---

## 部署场景选择指南

| 你的需求 | 推荐部署方式 |
|---------|------------|
| 前端开发、调试 | 本地开发环境 |
| 后端开发、调试 | 本地开发环境 (仅 Python/Go) |
| 生产环境部署 | Docker 全栈生产 |
| GPU 大模型推理 | GPU 加速环境 |
| 独立 Nginx 服务 | Nginx 30000 systemd |
| 仅后端 API 服务 | 后端独立部署 |
| 测试单个服务 | 单服务独立部署 |

---

## 服务架构

```
用户 → Nginx Frontend (30000) — B端管控面板
         ↓ (B端管控路径)
     aiclient2api (3000) — 开源项目+GPU插件, Node后端
         ↓ (C端推理路径: provider → Go)
     go-vllm-api (35001) — vLLM限流代理
     app-controller (35000) — Python 管控 (引擎启停/模型管理)
         ↓
     vLLM (8000) — 模型推理
     Redis (6379) — 缓存 / 队列
```

---

## 端口对照

详见 [端口参考手册](./port-reference.md)。

| 服务 | 开发端口 | Docker 端口 | 说明 |
|------|---------|-------------|------|
| 前端 Vite/Nginx | 30001 | 30000→80 | 开发 Vite / 生产 Nginx |
| Python B端 FastAPI | 35000 | 35000 | 引擎管控+模型管理 (Frontend/插件入口) |
| Go vLLM限流代理 go-vllm-api | 35001 | 35001 | vLLM限流代理 (aiclient2api provider路由目标) |
| aiclient2api | 3000 | 3000 | 开源项目+GPU插件 (Node后端, Docker部署) |
| Redis | 6379 | 6379 | 缓存 / 队列 |
| vLLM | 8000 | 8000 (容器内) | 模型推理，不对外暴露 |

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PORT` | 35000 | Python 后端端口 |
| `GO_PORT` | 35001 | Go 后端端口 |
| `CLIENT_PORT` | 3000 | aiclient2api 端口 |
| `REDIS_URL` | redis://localhost:6379 | Redis 连接 |
| `SECRET_KEY` | — | 安全密钥 (必填) |
| `LOG_LEVEL` | INFO | 日志级别 |
| `MODEL_BASE_PATH` | /mnt/pve_models | 模型存储路径 |

---

## 常用运维命令

```bash
# Docker 全栈
docker compose up -d              # 启动所有服务
docker compose down               # 停止所有服务
docker compose ps                 # 查看状态
docker compose logs -f            # 查看日志
docker compose logs -f <service>  # 查看单个服务日志

# Nginx systemd 服务
sudo systemctl status nginx-30000.service
sudo systemctl restart nginx-30000.service
sudo journalctl -u nginx-30000.service -f

# 健康检查
curl http://localhost:35000/health
curl http://localhost:35001/health
curl http://localhost:3000/health
curl http://localhost:30000
```

---

> 更新于 2026-04-26
