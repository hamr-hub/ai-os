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

**技术栈**
- Vue 3.5 + TypeScript
- Vite 6 构建工具
- Pinia 状态管理
- Vue Router 5
- Tailwind CSS

**核心模块**
```
frontend/src/
├── components/    # UI 组件
├── views/         # 页面视图
├── api/           # API 调用
├── stores/        # 状态管理
├── composables/   # 组合式函数
├── router/        # 路由配置
└── types/         # 类型定义
```

**代理路由**
- `/api/manage/*` → Python 后端 (35000)
- `/api/*` → Python 后端 (35000)
- `/v1/*` → Go 后端 (35001)
- `/health` → Go 后端 (35001)

**状态管理**
- `useAppStore`: 全局应用状态
- `useUserStore`: 用户信息
- `useToastStore`: Toast 通知

---

### App Controller (Python FastAPI) - 端口 35000

**技术栈**
- Python 3.11+
- FastAPI
- Pydantic 数据验证
- Uvicorn ASGI

**核心模块**
```
app-controller/
├── core/          # 核心业务逻辑
├── api/           # API 路由
├── main.py        # 入口文件
└── config.yaml    # 配置文件
```

**API 设计**
- RESTful 风格
- JSON 响应格式
- 统一错误处理
- 管理接口 `/manage/*`

---

### Go VLLM API (Go Gin) - 端口 35001

**技术栈**
- Go 1.26+
- Gin Web Framework
- vLLM Proxy
- WebSocket

**核心模块**
```
go-vllm-api/
├── cmd/server/     # 入口
├── internal/       # 内部模块
│   ├── config/    # 配置
│   ├── handler/   # 请求处理
│   ├── proxy/     # vLLM 代理
│   ├── service/   # 业务逻辑
│   └── middleware/ # 中间件
└── configs/       # 配置文件
```

**API 设计**
- OpenAI 兼容接口 `/v1/*`
- 管理接口 `/manage/*`
- WebSocket `/ws/*`
- 健康检查 `/health`

---

### AIClient2API (网关) - 端口 3000 (Docker部署)

**职责**
- API 转发到 go-vllm-api (35001)
- 请求鉴权
- 流量控制

参考 https://github.com/justlovemaki/AIClient-2-API 的 Docker 方式部署。

```
aiclient2api/
├── configs/       # 配置文件
├── docker-compose.yml
└── data/          # 数据目录
```

---

## 数据流

### 请求流程
```
User Action
    ↓
Vue Component
    ↓
API Module (axios) → Vite/Nginx proxy
    ↓                          ↓
/api/manage → app-controller (35000)
/v1 → go-vllm-api (35001)
    ↓
aiclient2api (3000) → go-vllm-api (35001)
    ↓
Response
```

### 状态管理流程
```
Component
    ↓ dispatch action
Pinia Store
    ↓ async API call
Backend
    ↓ response
Store Update
    ↓ reactive
Component Re-render
```

---

## 端口映射

| 服务 | 端口 | 说明 |
|------|------|------|
| frontend | 30000 | Vue 3 前端 |
| app-controller | 35000 | Python FastAPI 后端 |
| go-vllm-api | 35001 | Go 后端 |
| aiclient2api | 3000 | API 网关 (Docker部署) |
| Redis | 6379 | 缓存/队列 |
| vLLM | 8000 | 模型推理 (容器内) |

---

## 技术决策

### 为什么选择 Vue 3?
- Composition API 提供更好的逻辑复用
- TypeScript 支持完善
- 性能优于 Vue 2
- 生态成熟 (Pinia, Router)

### 为什么选择 FastAPI?
- 异步支持原生
- 自动 API 文档
- 类型安全 (Pydantic)
- 性能优秀

### 为什么增加 Go 后端?
- 高性能 HTTP 代理
- 低延迟 vLLM 请求转发
- WebSocket 实时推送更高效
- 与 Python 后端职责分离

### 为什么多模块?
- 前后端分离
- API 网关统一管理
- 独立部署扩展
- 技术栈灵活

---

## 部署架构

### 开发环境
```bash
# 前端
cd frontend && pnpm dev        # http://localhost:30000

# Python 后端
cd app-controller && python main.py  # http://localhost:35000

# Go 后端
cd go-vllm-api && go run cmd/server/main.go --port 35001  # http://localhost:35001

# 网关 (Docker)
cd aiclient2api && docker-compose up -d  # http://localhost:3000
```

### 生产环境 (Docker)
```yaml
# docker-compose.yml
services:
  frontend:
    ports:
      - "30000:80"         # 前端
  
  ai-controller:
    ports:
      - "35000:35000"     # Python 后端
  
  go-vllm-api:
    ports:
      - "35001:35001"     # Go 后端
  
  aiclient:
    ports:
      - "3000:3000"       # API 网关
```

---

> 更新于 2026-04-23
