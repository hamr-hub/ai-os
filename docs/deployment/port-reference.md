# 端口参考手册

## 端口总览

### 开发环境

| 服务 | 端口 | 协议 | 配置位置 | 说明 |
|------|------|------|---------|------|
| 前端 Vite | 30000 | HTTP | `frontend/vite.config.ts` | 开发服务器，热更新 |
| Python 后端 FastAPI | 35000 | HTTP | `.env` → `PORT` | 管理接口 `/manage/*` |
| Go 后端 go-vllm-api | 35001 | HTTP | `go-vllm-api/cmd/server/main.go` | 推理接口 `/v1/*` |
| aiclient2api | 3000 | HTTP | `.env` → `CLIENT_PORT` | API 网关 (Docker部署) |
| Redis | 6379 | TCP | `.env` → `REDIS_URL` | 缓存 / 队列 |
| vLLM | 8000 | HTTP | `app-controller/config.yaml` | 模型推理（容器内） |

### 生产环境 (Docker)

| 服务 | 对外端口 | 容器端口 | 协议 | 说明 |
|------|---------|---------|------|------|
| 前端 Nginx | 30000 | 80 | HTTP | 用户访问入口 |
| Python 后端 FastAPI | 35000 | 35000 | HTTP | 管理接口 |
| Go 后端 go-vllm-api | 35001 | 35001 | HTTP | 推理接口 |
| aiclient2api | 3000 | 3000 | HTTP | API 网关 (Docker部署) |
| Redis | 6379 | 6379 | TCP | 缓存服务 |

## 端口差异说明

### 前端端口差异

| 环境 | 前端端口 | 服务器 |
|------|---------|--------|
| 开发 | 30000 | Vite Dev Server |
| 生产 | 30000 | Nginx (容器内 80) |

### 前端代理路由

| 路径 | 代理目标 | 后端 |
|------|---------|------|
| `/api/manage` | `http://localhost:35000` | Python FastAPI |
| `/api` | `http://localhost:35000` | Python FastAPI |
| `/v1` | `http://localhost:35001` | Go go-vllm-api |
| `/health` | `http://localhost:35001` | Go go-vllm-api |

### vLLM 端口

vLLM 在 Docker 内监听 8000 端口，不对外暴露。通过 `go-vllm-api` 内部访问。
所有模型共享同一端口（8000），同一时间只能运行一个模型实例。

## Docker 网络配置

所有服务运行在 `ai-os-network` (bridge) 网络中：

```yaml
networks:
  default:
    name: ai-os-network
    driver: bridge
```

容器间通信使用服务名：

```yaml
# 在 ai-controller 中访问 Redis
REDIS_URL=redis://redis:6379

# 在 Nginx 中代理后端（使用 Docker 服务名）
# proxy_pass http://python_backend/manage/;  (upstream: ai-controller:35000)
# proxy_pass http://go_backend/v1/;          (upstream: go-vllm-api:35001)
```

## 端口冲突排查

### 检查端口占用

```bash
# macOS / Linux
lsof -i :<PORT>
netstat -tlnp | grep <PORT>

# 示例
lsof -i :30000    # 前端
lsof -i :35000    # Python 后端
lsof -i :35001    # Go 后端
lsof -i :6379     # Redis
```

### 常见冲突

| 端口 | 常见占用 | 解决方案 |
|------|---------|---------|
| 30000 | 其他 Vite 项目 | 修改 `vite.config.ts` → `server.port` |
| 35000 | 其他 Python 服务 | 修改 `.env` → `PORT` |
| 35001 | 其他 Go 服务 | 修改 `go-vllm-api/cmd/server/main.go` 默认端口 |
| 3000 | Node.js 项目 | 修改 `.env` → `CLIENT_PORT` |
| 6379 | 其他 Redis 实例 | 停止旧实例或修改端口映射 |

## 自定义端口

### 修改前端端口

```typescript
// frontend/vite.config.ts
server: {
  port: 30001,  // 自定义端口
}
```

### 修改 Python 后端端口

```bash
# .env
PORT=35000

# 或启动时指定
PORT=35000 python main.py
```

### 修改 Go 后端端口

```bash
# 启动时指定
go run cmd/server/main.go --port 35001

# 或修改 docker-compose.yml 端口映射
```

### 修改 Docker 端口映射

```yaml
# docker-compose.yml
frontend:
  ports:
    - "30000:80"           # 对外暴露 30000

ai-controller:
  ports:
    - "35000:35000"       # Python 后端

go-vllm-api:
  ports:
    - "35001:35001"       # Go 后端
```

> **注意**：修改容器内部端口需要同步修改 Dockerfile 中的 `EXPOSE` 和应用监听端口。

## aiclient2api 特殊配置

`aiclient2api` 使用 Docker 部署到 3000 端口，参考 https://github.com/justlovemaki/AIClient-2-API 的 Docker 方式部署。

`aiclient2api/configs/provider_pools.json` 中 `OPENAI_BASE_URL` 配置指向 Go 后端：

```json
"OPENAI_BASE_URL": "http://localhost:35001"
```
