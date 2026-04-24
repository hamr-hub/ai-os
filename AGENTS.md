# AI Flow 项目指南

> **ai-os** - 多模块 AI 操作系统 (Vue 3 + FastAPI + Go)

---

## 项目结构

```
ai-os/
├── frontend/              # Vue 3 前端 (端口 30000)
├── app-controller/        # Python FastAPI 后端 (端口 35000)
├── go-vllm-api/           # Go Gin 后端 (端口 35001)
├── aiclient2api/          # API 网关 (端口 3000, Docker部署)
├── .codeflicker/          # AI Flow 配置
└── docs/                  # 项目文档
```

---

## 快速开始

```bash
# 前端
cd frontend && pnpm install && pnpm dev              # http://localhost:30000

# Python 后端
cd app-controller && pip install -r requirements.txt && python main.py  # http://localhost:35000

# Go 后端
cd go-vllm-api && go run cmd/server/main.go --port 35001  # http://localhost:35001

# 网关 (Docker)
cd aiclient2api && docker compose up -d              # http://localhost:3000

# 全栈 Docker
docker compose up -d
```

---

## 详细文档

| 主题 | 文档 |
|------|------|
| 架构设计 | [docs/agent/architecture.md](./docs/agent/architecture.md) |
| 编码约定 | [.codeflicker/rules.md](./.codeflicker/rules.md) + [docs/agent/conventions.md](./docs/agent/conventions.md) |
| 开发命令 | [docs/agent/development_commands.md](./docs/agent/development_commands.md) |
| 部署指南 | [docs/deployment/deployment-guide.md](./docs/deployment/deployment-guide.md) |
| 端口参考 | [docs/deployment/port-reference.md](./docs/deployment/port-reference.md) |
| API 文档 | [app-controller/API.md](./app-controller/API.md) |
| 研发资产 | [docs/research/rd-assets.md](./docs/research/rd-assets.md) |

---

## AI Flow

1. `/ai-flow` - 完整需求交付流程
2. `/rd-asset-review` - 提取研发资产
3. `/tech-solution` - 生成技术方案

---

> 更新于 2026-04-24
