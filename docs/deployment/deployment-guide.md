# 部署指南总览

AI OS 支持多种部署场景，可根据环境选择对应的 Docker Compose 配置。

## 部署场景

| 场景 | 说明 | 文档 |
|------|------|------|
| 开发环境 | 前后端独立运行，热更新 | [开发环境部署](./docker-compose-dev.md) |
| 生产环境 | 全栈容器化部署 (4 服务) | [生产环境部署](./docker-compose-prod.md) |
| GPU 环境 | GPU 加速推理 + vLLM | [GPU 环境部署](./docker-compose-gpu.md) |

## 端口对照表

| 服务 | 开发端口 | Docker 端口 | 说明 |
|------|---------|-------------|------|
| 前端 Vite | 30000 | 8080→80 | 开发模式 Vite dev server；生产模式 Nginx |
| 后端 FastAPI | 35000 (proxy) / 5000 (.env) | 5000 | Vite 代理到 35000，.env 和 Docker 使用 5000 |
| aiclient2api | 3000 | 3000 | API 网关层 |
| Redis | 6379 | 6379 | 缓存 / 消息队列 |
| vLLM | 8000 | 8000 (容器内) | 模型推理服务，Docker 内部访问 |

> **注意**：开发环境中 Vite 配置代理 `/api` 和 `/v1` 到 `localhost:35000`，如果后端实际监听 5000 端口，需确保代理目标正确或后端监听 35000。

## 快速启动

### 生产环境一键部署

```bash
# 克隆项目
git clone <repo-url> && cd ai-os

# 配置环境变量
cp .env.example .env
# 编辑 .env 修改 SECRET_KEY、REDIS_URL 等

# 启动所有服务
docker compose up -d

# 查看状态
docker compose ps

# 查看日志
docker compose logs -f
```

### 开发环境

```bash
# 终端 1: 启动后端
cd app-controller
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python main.py

# 终端 2: 启动前端
cd frontend
pnpm install
pnpm dev
```

## 服务架构

```
用户 → 前端 (8080/30000)
         ↓
     aiclient2api (3000) — API 网关 / 鉴权
         ↓
     app-controller (5000) — 业务逻辑
         ↓
     vLLM (8000) — 模型推理
         ↓
     Redis (6379) — 缓存 / 队列
```

## 环境变量

核心配置项（详见 `.env`）：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `HOST` | 0.0.0.0 | 监听地址 |
| `PORT` | 5000 | 后端端口 |
| `CLIENT_PORT` | 3000 | aiclient2api 端口 |
| `REDIS_URL` | redis://localhost:6379 | Redis 连接 |
| `SECRET_KEY` | your-secret-key-here | 安全密钥 |
| `LOG_LEVEL` | INFO | 日志级别 |
| `MODEL_BASE_PATH` | /mnt/pve_models | 模型存储路径 |

## 健康检查

各服务均提供健康检查端点：

```bash
# 后端
curl http://localhost:5000/health

# aiclient2api
curl http://localhost:3000/health

# Redis
docker exec ai-os-redis redis-cli ping
```

## 常用运维命令

```bash
# 重启单个服务
docker compose restart ai-controller

# 查看服务日志
docker compose logs -f ai-controller

# 重新构建并启动
docker compose up -d --build

# 停止所有服务
docker compose down

# 清理数据卷（慎用）
docker compose down -v
```
