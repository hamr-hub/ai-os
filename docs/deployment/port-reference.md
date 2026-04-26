# 端口参考手册

## 端口总览

| 服务 | 开发端口 | Docker 端口 | 说明 |
|------|---------|-------------|------|
| 前端 Vite/Nginx | 30001 | 30000→80 | 开发 Vite / 生产 Nginx |
| Python 后端 FastAPI | 35000 | 35000 | 管理接口 `/manage/*` |
| Go 后端 go-vllm-api | 35001 | 35001 | 推理接口 `/v1/*` |
| aiclient2api | 3000 | 3000 | API 网关 (Docker部署) |
| Redis | 6379 | 6379 | 缓存 / 队列 |
| vLLM | 8000 | 8000 (容器内) | 模型推理，不对外暴露 |

## 前端代理路由

| 路径 | 代理目标 | 后端 |
|------|---------|------|
| `/api/manage/*` | `http://localhost:35000/manage/*` | Python FastAPI |
| `/api/*` | `http://localhost:35000/manage/*` | Python FastAPI 管理接口别名 |
| `/api/health` | `http://localhost:35001/health` | Go go-vllm-api 健康检查别名 |
| `/api/health/detailed` | `http://localhost:35001/health/detailed` | Go go-vllm-api 详细健康检查别名 |
| `/v1/*` | `http://localhost:35001/v1/*` | Go go-vllm-api |
| `/health` | `http://localhost:35001/health` | Go go-vllm-api |

## vLLM 端口

vLLM 在容器内监听 8000 端口，不对外暴露。通过 `go-vllm-api` 内部访问。所有模型共享同一端口，同一时间只能运行一个模型实例。

## Docker 网络

所有服务运行在 `ai-os-network` (bridge) 中，容器间通信使用 Docker 服务名：
- `REDIS_URL=redis://redis:6379`
- Nginx 代理使用 `ai-controller:35000`、`go-vllm-api:35001`

## 端口冲突排查

```bash
lsof -i :<PORT>    # 检查占用
kill -9 <PID>      # 释放端口
```

常见冲突：

| 端口 | 常见占用 | 解决方案 |
|------|---------|---------|
| 30001 | 其他 Vite 项目 | 修改 `vite.config.ts` → `server.port` |
| 35000 | 其他 Python 服务 | 修改 `.env` → `PORT` |
| 35001 | 其他 Go 服务 | 修改启动 `--port` 参数 |
| 3000 | Node.js 项目 | 修改 `.env` → `CLIENT_PORT` |
| 6379 | 其他 Redis | 停止旧实例或修改端口映射 |

## 自定义端口

```typescript
// 前端: frontend/vite.config.ts → server.port
```

```bash
# Python 后端: .env → PORT=35000 或 PORT=35000 python main.py
# Go 后端: go run cmd/server/main.go --port 35001
```

```yaml
# Docker: docker-compose.yml → ports 映射
# 注意: 修改容器内部端口需同步修改 Dockerfile EXPOSE 和应用监听端口
```

## aiclient2api 配置

`aiclient2api/configs/provider_pools.json` 中 `OPENAI_BASE_URL` 指向 Go 后端（注意包含 `/v1` 路径）：

```json
"OPENAI_BASE_URL": "http://192.168.7.103:35001/v1"
```

> **注意**: 开发环境使用 `http://localhost:35001/v1`，生产环境使用实际服务器 IP 或 Docker 服务名。

---

> 更新于 2026-04-24
