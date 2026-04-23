# 端口参考手册

## 端口总览

### 开发环境

| 服务 | 端口 | 协议 | 配置位置 | 说明 |
|------|------|------|---------|------|
| 前端 Vite | 30000 | HTTP | `frontend/vite.config.ts` | 开发服务器，热更新 |
| 后端 FastAPI | 5000 | HTTP | `.env` → `PORT` | 后端默认监听端口 |
| Vite 代理目标 | 35000 | HTTP | `frontend/vite.config.ts` | `/api` 和 `/v1` 代理到此端口 |
| aiclient2api | 3000 | HTTP | `.env` → `CLIENT_PORT` | API 网关 |
| Redis | 6379 | TCP | `.env` → `REDIS_URL` | 缓存 / 队列 |
| vLLM | 8000 | HTTP | `app-controller/config.yaml` | 模型推理（容器内） |

### 生产环境 (Docker)

| 服务 | 对外端口 | 容器端口 | 协议 | 说明 |
|------|---------|---------|------|------|
| 前端 Nginx | 8080 | 80 | HTTP | 用户访问入口 |
| 后端 FastAPI | 5000 | 5000 | HTTP | API 服务 |
| aiclient2api | 3000 | 3000 | HTTP | API 网关 |
| Redis | 6379 | 6379 | TCP | 缓存服务 |

## 端口差异说明

### 前端端口差异

| 环境 | 前端端口 | 服务器 |
|------|---------|--------|
| 开发 | 30000 | Vite Dev Server |
| 生产 | 8080 | Nginx |

### 后端端口差异

开发环境存在两种配置：
- `.env` 中 `PORT=5000`
- `vite.config.ts` 中代理到 `localhost:35000`

**解决方案**（二选一）：
1. 后端监听 35000：`PORT=35000 python main.py`
2. 修改 Vite 代理：`target: 'http://localhost:5000'`

### vLLM 端口

vLLM 在 Docker 内监听 8000 端口，不对外暴露。通过 `app-controller` 内部访问。
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

# 在 Nginx 中代理后端（需注意：当前配置使用 localhost）
# 生产环境建议改为服务名：
# proxy_pass http://ai-controller:5000/;
```

## 端口冲突排查

### 检查端口占用

```bash
# macOS / Linux
lsof -i :<PORT>
netstat -tlnp | grep <PORT>

# 示例
lsof -i :30000    # 前端
lsof -i :5000    # 后端
lsof -i :6379    # Redis
```

### 常见冲突

| 端口 | 常见占用 | 解决方案 |
|------|---------|---------|
| 30000 | 其他 Vite 项目 | 修改 `vite.config.ts` → `server.port` |
| 5000 | macOS AirPlay | 关闭 AirPlay 或修改后端端口 |
| 3000 | Node.js 项目 | 修改 `.env` → `CLIENT_PORT` |
| 6379 | 其他 Redis 实例 | 停止旧实例或修改端口映射 |
| 8080 | 其他 Web 服务 | 修改 `docker-compose.yml` 端口映射 |

### macOS AirPlay 端口 5000 冲突

macOS Monterey+ 的 AirPlay Receiver 占用 5000 端口：

```bash
# 关闭 AirPlay Receiver
# 系统设置 → 通用 → AirDrop 与 Handoff → AirPlay Receiver → 关闭

# 或修改后端端口
PORT=5001 python main.py
```

## 自定义端口

### 修改前端端口

```typescript
// frontend/vite.config.ts
server: {
  port: 30001,  // 自定义端口
}
```

### 修改后端端口

```bash
# .env
PORT=5001

# 或启动时指定
PORT=5001 python main.py
```

### 修改 Docker 端口映射

```yaml
# docker-compose.yml
frontend:
  ports:
    - "9090:80"           # 对外暴露 9090

ai-controller:
  ports:
    - "5001:5000"         # 对外暴露 5001，容器内仍为 5000
```

> **注意**：修改容器内部端口需要同步修改 Dockerfile 中的 `EXPOSE` 和应用监听端口。

## aiclient2api 特殊配置

`aiclient2api/docker-compose.yml` 使用 `network_mode: host`，直接使用宿主机网络：

```yaml
aiclient:
  network_mode: host    # 直接使用宿主网络
  ports:
    - "3000:3000"        # host 模式下 ports 无实际效果
```

> 此模式下端口 3000 直接在宿主机暴露，不受 Docker 网络隔离。根目录的 `docker-compose.yml` 使用标准 bridge 网络模式。
