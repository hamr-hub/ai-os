# 端口参考手册

## 端口总览

| 服务 | 开发端口 | Docker 端口 | 说明 |
|------|---------|-------------|------|
| 前端 Vite/Nginx | 30001 | 30000 | 开发 Vite / 生产 Nginx |
| Python B端 app-controller | 35000 | 35000 | 管控平台 `/manage/*` + `/ws/*` + Agent |
| Go 网关 go-vllm-api | 35001 | 35001 | C端推理 `/v1/*` + `/health` |
| aiclient2api | 3000 | 3000 | API 网关 (Docker部署) |
| Redis | 6379 | 6379 | 缓存 / 限流 / 历史 / 排队 |
| vLLM | 8000 | 8000 (容器内) | 推理引擎，不对外暴露 |
| llama.cpp | 8001/8002 | 8001/8002 (容器内) | GGUF推理，不对外暴露 |
| Nginx 反向代理 | 80 | 80 | 统一入口路由分发 |

## Nginx 路由规则

| 路径 | 代理目标 | 后端 | 特殊配置 |
|------|---------|------|----------|
| `/` | aiclient(:3000) | aiclient2api | - |
| `/manage/` | frontend(:30000) | Vue3前端 | - |
| `/api/manage/*` | Python(:35000) `/manage/*` | Python B端 | proxy_buffering off |
| `/api/health` | Go(:35001) `/health` | Go 网关 | - |
| `/api/health/detailed` | Go(:35001) `/health/detailed` | Go 网关 | - |
| `/api/*` | Python(:35000) `/manage/*` | Python B端 | proxy_buffering off |
| `/v1/test/*` | Python(:35000) `/v1/test/*` | Python B端 | - |
| `/v1/*` | Go(:35001) `/v1/*` | Go 网关 | proxy_buffering off + SSE |
| `/ws/*` | Python(:35000) `/ws/*` | Python B端 | upgrade + 86400s超时 |
| `/health` | Go(:35001) `/health` | Go 网关 | - |

## vLLM 端口

vLLM 在容器内监听 8000 端口，不对外暴露。通过 `go-vllm-api` 和 `app-controller` 内部代理访问。同一时间只运行一个 vLLM 模型实例，模型切换通过重启 vLLM 服务并变更 model_path 实现。

llama.cpp 服务按模型分配独立端口(8001/8002等)，每个 GGUF 模型独立进程。

## Go-Python 内部通信

Go 网关代理以下操作到 Python B端（环境变量 `PYTHON_BACKEND_URL`，默认 `http://192.168.7.103:35000`）:

| Go 路由 | 代理到 Python 路由 | 说明 |
|----------|---------------------|------|
| `/manage/switch/atomic` | `/manage/switch/atomic` | 原子模型切换 |
| `/manage/switch/status` | `/manage/switch/status` | 切换进度查询 |
| `/manage/switch/cancel` | `/manage/switch/cancel` | 取消切换 |
| `/manage/models/aggregated` | `/manage/models/aggregated` | 聚合模型信息 |
| `/manage/models/*/start/stop/switch` | `/manage/switch/atomic` | 启停/切换(均代理) |

Go 的 `broadcastStatusLoop` 每 2s 轮询 Python `/manage/switch/status` 获取切换进度，转发给 Go WebSocket 客户端。

## Docker 网络

所有服务运行在 `ai-os-network` (bridge) 中，容器间通信使用 Docker 服务名：
- `REDIS_URL=redis://redis:6379`
- Go→Python: `PYTHON_BACKEND_URL=http://ai-controller:35000`

## 端口冲突排查

```bash
lsof -i :<PORT>    # 检查占用
kill -9 <PID>      # 释放端口
```

常见冲突：

| 端口 | 常见占用 | 解决方案 |
|------|---------|----------|
| 30001 | 其他 Vite 项目 | 修改 `vite.config.ts` → `server.port` |
| 35000 | 其他 Python 服务 | 修改 `.env` → `PORT` 或 `--port` 参数 |
| 35001 | 其他 Go 服务 | 修改启动 `--port` 参数 |
| 3000 | Node.js 项目 | 修改 `.env` → `CLIENT_PORT` |
| 6379 | 其他 Redis | 停止旧实例或修改端口映射 |

## 自定义端口

```typescript
// 前端: frontend/vite.config.ts → server.port
```

```bash
# Python 后端: python main.py --port 35000
# Go 后端: go run cmd/server/main.go --port 35001 --config configs/config.yaml
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

> **注意**: 开发环境使用 `http://localhost:35001/v1`，Docker 环境使用服务名 `http://go-vllm-api:35001/v1`。

---

> 更新于 2026-04-30
