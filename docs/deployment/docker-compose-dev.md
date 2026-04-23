# 开发环境部署

## 架构说明

开发环境采用前后端独立运行模式，支持热更新和快速调试。

```
前端 Vite (30000) → proxy /api/manage → Python FastAPI (35000)
                                → proxy /v1, /health → Go go-vllm-api (35001)
                                → aiclient2api (3000, Docker部署)
                                → Redis (6379)
```

## 前置条件

- Node.js >= 18
- Python >= 3.11
- Go >= 1.26
- pnpm >= 8
- Redis (本地或 Docker)

## 端口配置

| 服务 | 端口 | 配置位置 |
|------|------|---------|
| 前端 Vite | 30000 | `frontend/vite.config.ts` → `server.port` |
| Python 后端 FastAPI | 35000 | `.env` → `PORT` |
| Go 后端 go-vllm-api | 35001 | `go-vllm-api/cmd/server/main.go` |
| aiclient2api | 3000 | `.env` → `CLIENT_PORT` (Docker部署) |
| Redis | 6379 | `.env` → `REDIS_URL` |

## 启动步骤

### 1. 启动 Redis

```bash
# Docker 方式
docker run -d --name ai-os-redis \
  -p 6379:6379 \
  redis:7.2-alpine

# 或使用已有的 Redis 实例
# 修改 .env 中 REDIS_URL
```

### 2. 启动 Python 后端

```bash
cd app-controller

# 创建虚拟环境
python -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动服务（默认 35000 端口）
python main.py
```

### 3. 启动 Go 后端

```bash
cd go-vllm-api

# 启动服务（默认 35001 端口）
go run cmd/server/main.go --port 35001
```

### 4. 启动前端

```bash
cd frontend

# 安装依赖
pnpm install

# 启动开发服务器（端口 30000）
pnpm dev
```

### 5. 启动 aiclient2api（Docker方式）

参考 https://github.com/justlovemaki/AIClient-2-API 的 Docker 方式：

```bash
cd aiclient2api
docker compose up -d
```

## 访问地址

- 前端页面：http://localhost:30000
- Python 后端 API 文档：http://localhost:35000/docs
- Go 后端健康检查：http://localhost:35001/health
- aiclient2api：http://localhost:3000

## 环境变量配置

编辑项目根目录 `.env`：

```bash
# Python 后端端口
PORT=35000

# Go 后端端口
GO_PORT=35001

# aiclient2api端口
CLIENT_PORT=3000

# Redis
REDIS_URL=redis://localhost:6379
REDIS_DB=0

# 日志
LOG_LEVEL=DEBUG

# 开发模式
ALLOWED_ORIGINS=*
```

## 调试技巧

### 前端调试

- 安装 Vue DevTools 浏览器插件
- 浏览器访问 http://localhost:30000，打开 DevTools

### Python 后端调试

- FastAPI 自动文档：http://localhost:35000/docs
- 启用 debug 日志：`LOG_LEVEL=DEBUG python main.py`
- 热更新：`uvicorn main:app --reload --port 35000`

### Go 后端调试

- 健康检查：http://localhost:35001/health
- 热更新：修改代码后重启 `go run`

### API 代理调试

Vite 开发代理配置：

```typescript
// frontend/vite.config.ts
server: {
  port: 30000,
  proxy: {
    '/api/manage': {
      target: 'http://localhost:35000',  // Python 后端
      changeOrigin: true,
    },
    '/api': {
      target: 'http://localhost:35000',  // Python 后端
      changeOrigin: true,
    },
    '/v1': {
      target: 'http://localhost:35001',  // Go 后端
      changeOrigin: true,
    },
    '/health': {
      target: 'http://localhost:35001',  // Go 后端
      changeOrigin: true,
    },
  }
}
```

## 端口冲突排查

```bash
# 检查端口占用
lsof -i :30000   # 前端
lsof -i :35000   # Python 后端
lsof -i :35001   # Go 后端
lsof -i :3000    # aiclient2api
lsof -i :6379    # Redis

# 释放端口
kill -9 <PID>
```

## 仅 Python 后端开发

如只需开发 Python 后端，可使用 `app-controller/docker-compose.yml`：

```bash
cd app-controller
docker compose up -d
```

此方式仅启动 Python 后端和 Redis，端口 35000 + 6379。
