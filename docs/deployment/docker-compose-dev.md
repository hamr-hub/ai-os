# 开发环境部署

## 架构说明

开发环境采用前后端独立运行模式，支持热更新和快速调试。

```
前端 Vite (30000) → proxy /api → 后端 FastAPI (5000/35000)
                                → aiclient2api (3000)
                                → Redis (6379)
```

## 前置条件

- Node.js >= 18
- Python >= 3.11
- pnpm >= 8
- Redis (本地或 Docker)

## 端口配置

| 服务 | 端口 | 配置位置 |
|------|------|---------|
| 前端 Vite | 30000 | `frontend/vite.config.ts` → `server.port` |
| API 代理 | 35000 | `frontend/vite.config.ts` → `server.proxy` |
| 后端 FastAPI | 5000 | `.env` → `PORT` |
| aiclient2api | 3000 | `.env` → `CLIENT_PORT` |
| Redis | 6379 | `.env` → `REDIS_URL` |

> **重要**：Vite 代理将 `/api` 和 `/v1` 转发到 `localhost:35000`，而后端默认监听 5000。如需一致，修改 `vite.config.ts` 中 `proxy.target` 或让后端监听 35000。

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

### 2. 启动后端

```bash
cd app-controller

# 创建虚拟环境
python -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动服务（默认 5000 端口）
python main.py

# 或指定端口
PORT=35000 python main.py
```

### 3. 启动前端

```bash
cd frontend

# 安装依赖
pnpm install

# 启动开发服务器（端口 30000）
pnpm dev
```

### 4. 启动 aiclient2api（可选）

```bash
cd aiclient2api

# Docker 方式
docker compose up -d

# 或 Node.js 直接运行
npm install --only=production
npm start
```

## 访问地址

- 前端页面：http://localhost:30000
- 后端 API 文档：http://localhost:5000/docs（或 35000）
- aiclient2api：http://localhost:3000

## 环境变量配置

编辑项目根目录 `.env`：

```bash
# 后端端口（注意与 Vite proxy 一致）
PORT=5000

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

### 后端调试

- FastAPI 自动文档：http://localhost:5000/docs
- 启用 debug 日志：`LOG_LEVEL=DEBUG python main.py`
- 热更新：`uvicorn main:app --reload --port 5000`

### API 代理调试

Vite 开发代理配置：

```typescript
// frontend/vite.config.ts
server: {
  port: 30000,
  proxy: {
    '/api': {
      target: 'http://localhost:35000',  // 确认后端实际端口
      changeOrigin: true,
    },
    '/v1': {
      target: 'http://localhost:35000',
      changeOrigin: true,
    },
  }
}
```

## 端口冲突排查

```bash
# 检查端口占用
lsof -i :30000   # 前端
lsof -i :5000    # 后端
lsof -i :3000    # aiclient2api
lsof -i :6379    # Redis

# 释放端口
kill -9 <PID>
```

## 仅后端开发

如只需开发后端，可使用 `app-controller/docker-compose.yml`：

```bash
cd app-controller
docker compose up -d
```

此方式仅启动后端和 Redis，端口 5000 + 6379。
