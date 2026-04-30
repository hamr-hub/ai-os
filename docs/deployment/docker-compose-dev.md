# 开发环境部署

## 架构

```
B端管控: 前端 Vite (30001) → proxy /api/manage → Python FastAPI /manage/* (35000) [引擎/模型管控]
                                → proxy /ws → Python WebSocket (35000) [GPU监控/切换进度]
C端推理: aiclient2api (3000, Docker部署) → provider → Go go-vllm-api (35001) → 推理引擎(:8000)
基础设施: Redis (6379) [缓存/限流]

两条核心路径:
  C端推理: aiclient2api(Node) → provider → go-vllm-api → 推理引擎
  B端管控: Frontend/插件 → Python → 引擎启停/模型管理
```

端口配置详见 [端口参考](./port-reference.md)。

## 前置条件

- Node.js >= 18, pnpm >= 8
- Python >= 3.11
- Go >= 1.26
- Redis (本地或 Docker)

## 启动步骤

### 1. Redis
```bash
docker run -d --name ai-os-redis -p 6379:6379 redis:7.2-alpine
# 或使用已有 Redis 实例，修改 .env 中 REDIS_URL
```

### 2. Python 后端
```bash
cd app-controller
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python main.py    # http://localhost:35000
```

### 3. Go 后端
```bash
cd go-vllm-api
go run cmd/server/main.go --port 35001    # http://localhost:35001
```

### 4. 前端
```bash
cd frontend
pnpm install && pnpm dev    # http://localhost:30001
```

### 5. aiclient2api (开源项目+GPU插件, Node后端)
```bash
cd aiclient2api && docker compose up -d    # http://localhost:3000
# provider_pools.json 中 OPENAI_BASE_URL 指向 go-vllm-api:35001
```

## 调试

- Vue DevTools 浏览器插件
- FastAPI 自动文档: http://localhost:35000/docs
- Python 热更新: `uvicorn main:app --reload --port 35000`
- Go 热更新: 修改代码后重启 `go run`

### Vite 代理配置

```typescript
// frontend/vite.config.ts
server: {
  port: 30001,
  proxy: {
    '/api/manage': { target: 'http://localhost:35000', changeOrigin: true },
    '/api/health': { target: 'http://localhost:35001', changeOrigin: true, rewrite: () => '/health' },
    '/api': {
      target: 'http://localhost:35000',
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api/, '/manage'),
    },
    '/v1': { target: 'http://localhost:35001', changeOrigin: true },
    '/health': { target: 'http://localhost:35001', changeOrigin: true },
  }
}
```

### 仅 Python 后端开发

```bash
cd app-controller && docker compose up -d    # 仅启动 Python + Redis
```

---

> 更新于 2026-04-24
