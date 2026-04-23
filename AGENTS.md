# AI Flow 项目指南

> **ai-os** - 多模块 AI 操作系统（Vue 3 + FastAPI + Go）

---

## 🎯 项目愿景

构建一个模块化的 AI 操作系统，包含：
- **frontend**: Vue 3 前端界面 (端口 30000)
- **app-controller**: Python FastAPI 后端服务 (端口 35000)
- **go-vllm-api**: Go 后端服务 (端口 35001)
- **aiclient2api**: API 网关层 (端口 3000, Docker部署)

---

## 📦 项目结构

```
ai-os/
├── frontend/              # Vue 3 + Vite + TypeScript
│   ├── src/
│   │   ├── components/   # Vue 组件
│   │   ├── views/        # 页面视图
│   │   ├── api/          # API 调用
│   │   ├── stores/       # Pinia 状态
│   │   ├── composables/  # Vue Composables
│   │   └── router/       # 路由配置
│   └── package.json
│
├── app-controller/        # Python FastAPI (端口 35000)
│   ├── core/             # 核心模块
│   ├── api/              # API 路由
│   ├── main.py           # 入口文件
│   └── config.yaml       # 配置
│
├── go-vllm-api/           # Go 后端 (端口 35001)
│   ├── cmd/server/       # 入口
│   ├── internal/         # 内部模块
│   └── configs/          # 配置
│
├── aiclient2api/          # API 网关 (端口 3000, Docker)
│   └── configs/
│
├── .codeflicker/          # AI Flow 配置
│   ├── config.json       # 项目配置
│   ├── rules.md          # 开发规则
│   └── snippets/         # 代码片段
│
└── docs/
    ├── agent/            # 开发约定
    ├── research/         # 研发资产
    ├── tasks/            # 任务文档
    └── installation/     # 安装文档
```

---

## 🚀 快速开始

### 前端开发
```bash
cd frontend
pnpm install          # 安装依赖
pnpm dev              # 启动开发服务器 (http://localhost:30000)
pnpm build            # 生产构建
pnpm lint             # 代码检查
```

### Python 后端开发
```bash
cd app-controller
python -m venv venv   # 创建虚拟环境
source venv/bin/activate
pip install -r requirements.txt
python main.py        # 启动服务 (http://localhost:35000)
```

### Go 后端开发
```bash
cd go-vllm-api
go run cmd/server/main.go --port 35001  # 启动服务 (http://localhost:35001)
```

### aiclient2api (Docker部署)
```bash
# 参考 https://github.com/justlovemaki/AIClient-2-API 的 Docker 方式部署
cd aiclient2api
docker-compose up -d  # 启动 (http://localhost:3000)
```

### Docker 全栈部署
```bash
docker-compose up -d  # 启动所有服务
```

---

## 🛠️ 技术栈

### 前端
- **框架**: Vue 3.5 + TypeScript
- **构建**: Vite 6
- **样式**: Tailwind CSS 4
- **状态**: Pinia 3
- **路由**: Vue Router 5
- **HTTP**: Axios
- **图标**: Lucide Vue Next

### Python 后端
- **框架**: FastAPI
- **运行时**: Python 3.11+
- **配置**: YAML
- **测试**: Pytest

### Go 后端
- **框架**: Gin
- **运行时**: Go 1.26+
- **配置**: YAML
- **代理**: vLLM Proxy

---

## 🔌 端口映射

| 服务 | 端口 | 说明 |
|------|------|------|
| frontend | 30000 | Vue 3 前端 |
| app-controller | 35000 | Python FastAPI 后端 |
| go-vllm-api | 35001 | Go 后端 |
| aiclient2api | 3000 | API 网关 (Docker部署) |
| Redis | 6379 | 缓存/队列 |
| vLLM | 8000 | 模型推理 (容器内) |

---

## 📝 开发规范

详细规范见:
- **[.codeflicker/rules.md](./.codeflicker/rules.md)** - 开发规则
- **[docs/agent/conventions.md](./docs/agent/conventions.md)** - 编码约定

---

## 🔗 相关文档

- **API 文档**: `app-controller/API.md`
- **集成指南**: `app-controller/AICLIENT_INTEGRATION.md`
- **端口参考**: `docs/deployment/port-reference.md`

---

## 💡 使用 AI Flow

本项目已配置 AI Flow，可以:
1. 运行 `/ai-flow` 执行完整需求交付流程
2. 运行 `/rd-asset-review` 提取研发资产
3. 运行 `/tech-solution` 生成技术方案

---

> 自动生成于 2026-04-23 | AI Flow v0.4.16
