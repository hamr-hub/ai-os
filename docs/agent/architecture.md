# 架构设计

> ai-os 多模块架构说明

---

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                     用户界面层                            │
│                    Vue 3 Frontend                        │
│                  (localhost:5173)                        │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP/WebSocket
                     ▼
┌─────────────────────────────────────────────────────────┐
│                   API 网关层                              │
│                  aiclient2api                            │
│                 (localhost:3000)                         │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP
                     ▼
┌─────────────────────────────────────────────────────────┐
│                   业务逻辑层                              │
│               app-controller (FastAPI)                   │
│                  (localhost:8000)                        │
└─────────────────────────────────────────────────────────┘
```

---

## 模块说明

### Frontend (Vue 3)

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

**状态管理**
- `useAppStore`: 全局应用状态
- `useUserStore`: 用户信息
- `useToastStore`: Toast 通知

---

### App Controller (Python FastAPI)

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

---

### AIClient2API (网关)

**职责**
- API 路由转发
- 请求鉴权
- 流量控制

```
aiclient2api/
├── configs/       # 配置文件
├── python/        # Python 模块
└── docker-compose.yml
```

---

## 数据流

### 请求流程
```
User Action
    ↓
Vue Component
    ↓
API Module (axios)
    ↓
aiclient2api (Gateway)
    ↓
app-controller (FastAPI)
    ↓
Database/External API
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
cd frontend && pnpm dev

# 后端
cd app-controller && python main.py

# 网关
cd aiclient2api && docker-compose up
```

### 生产环境
```yaml
# docker-compose.yml
services:
  frontend:
    build: ./frontend
    ports:
      - "80:80"
  
  gateway:
    build: ./aiclient2api
    ports:
      - "3000:3000"
  
  backend:
    build: ./app-controller
    ports:
      - "8000:8000"
```

---

## 扩展点

### 前端扩展
- 新增页面: `views/` + Router 配置
- 新增组件: `components/`
- 新增 API: `api/` + `types/`

### 后端扩展
- 新增路由: `api/` 目录
- 新增业务: `core/` 目录

---

> 更新于 2026-04-22
