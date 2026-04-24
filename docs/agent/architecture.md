# 架构设计

> ai-os 多模块架构说明

---

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                     用户界面层                            │
│                    Vue 3 Frontend                        │
│                  (localhost:30000)                        │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP/WebSocket
              ┌──────┴──────┐
              ▼             ▼
┌──────────────────┐ ┌───────────────────────────────────┐
│  API 网关层       │ │        业务逻辑层                  │
│  aiclient2api    │ │  app-controller (FastAPI) :35000   │
│  (localhost:3000)│ │  go-vllm-api (Go) :35001          │
└──────────────────┘ └──────────────┬────────────────────┘
                                    │
                                    ▼
                     ┌──────────────────────────────────┐
                     │        推理层                      │
                     │     vLLM Instance (:8000)         │
                     └──────────────────────────────────┘
```

---

## 模块说明

### Frontend (Vue 3) - 端口 30000

**核心模块**
```
frontend/src/
├── components/    # UI 组件 (AgentChatWindow, LineChart, Sidebar, TopBar, GpuMetricsCard)
├── views/         # 页面 (Dashboard, AgentView, DocsView, ModelManagement, MonitorView, ModelBenchmarks)
├── api/           # API 调用封装 (client.ts)
├── stores/        # 状态管理 (app.ts, agentChat.ts, server.ts)
├── composables/   # 组合式函数 (useGPU, useGPUHistory, useMarkdown, useModels, useSystemData, useTokenHistory, useTokenStats)
├── router/        # 路由配置
└── types/         # 类型定义
```

**代理路由**
- `/api/manage/*` → Python 后端 (35000)
- `/api/*` → Python 后端 (35000)
- `/v1/*` → Go 后端 (35001)
- `/health` → Go 后端 (35001)

---

### App Controller (Python FastAPI) - 端口 35000

**核心模块**
```
app-controller/
├── core/          # 核心业务逻辑
│   ├── config.py          # 配置管理
│   ├── monitor.py         # 系统监控
│   ├── metrics.py         # 性能指标
│   ├── vllm_manager.py    # vLLM 管理
│   ├── vllm_metrics.py    # vLLM 指标采集
│   ├── redis_client.py    # Redis 客户端
│   ├── scheduler.py       # 任务调度
│   ├── rate_limiter.py    # 限流器
│   ├── cache_service.py   # 缓存服务
│   ├── websocket_manager.py  # WebSocket
│   └── ...
├── api/           # API 路由
├── main.py        # 入口文件
└── config.yaml    # 配置文件
```

管理接口 `/manage/*`：模型管理、GPU 监控、系统状态、缓存等。

---

### Go VLLM API (Go Gin) - 端口 35001

**核心模块**
```
go-vllm-api/
├── cmd/server/     # 入口
├── internal/
│   ├── config/    # 配置
│   ├── handler/   # 请求处理 (manage/, v1/)
│   ├── proxy/     # vLLM 代理
│   ├── service/   # 业务逻辑
│   └── middleware/ # 中间件
└── configs/       # 配置文件
```

OpenAI 兼容接口 `/v1/*`，管理接口 `/manage/*`，健康检查 `/health`。

---

### AIClient2API (网关) - 端口 3000 (Docker部署)

API 转发 + 鉴权 + 流量控制，配置中 `OPENAI_BASE_URL` 指向 Go 后端 (35001)。

---

## 数据流

```
User → Vue Component → API Module → Vite/Nginx proxy
    ↓                          ↓
/api/manage → app-controller (35000)
/v1 → go-vllm-api (35001)
aiclient2api (3000) → go-vllm-api (35001)
    ↓
vLLM (8000) → Response
```

---

## 端口与技术栈

详见 [端口参考](../deployment/port-reference.md) 和 [编码约定](./conventions.md)。

---

> 更新于 2026-04-24
