# AI Flow 项目指南

> **ai-os** - 多模块 AI 操作系统 (Vue 3 + Node + FastAPI + Go)

---

## 项目结构

```
ai-os/
├── frontend/              # Vue 3 前端 — B端管控面板 (开发 30001 / 生产 30000)
├── aiclient2api/          # 开源项目 + GPU插件 — C端推理入口 (Node后端, 端口 3000)
├── app-controller/        # Python FastAPI B端 — 引擎/模型管控 (端口 35000)
├── go-vllm-api/           # Go Gin — vLLM限流代理 (端口 35001)
├── .codeflicker/          # AI Flow 配置
└── docs/                  # 项目文档
```

**两条核心路径**:
- **C端推理**: aiclient2api(Node) → provider → go-vllm-api → 推理引擎
- **B端管控**: Frontend/插件 → Python → 引擎启停/模型管理

---

## 快速开始

```bash
# 前端
cd frontend && pnpm install && pnpm dev              # http://localhost:30001

# Python 后端
cd app-controller && pip install -r requirements.txt && python main.py  # http://localhost:35000

# Go 后端
cd go-vllm-api && go run cmd/server/main.go --port 35001  # http://localhost:35001

# 网关 (Docker)
cd aiclient2api && docker compose up -d              # http://localhost:3000

# 全栈 Docker
docker compose up -d

# Nginx 30000 (systemd 服务)
sudo systemctl enable --now nginx-30000.service      # http://localhost:30000
```

---

## 详细文档

| 主题 | 文档 |
|------|------|
| 架构设计 | [docs/agent/architecture.md](./docs/agent/architecture.md) |
| 编码约定 | [.codeflicker/rules.md](./.codeflicker/rules.md) + [docs/agent/conventions.md](./docs/agent/conventions.md) |
| 开发命令 | [docs/agent/development_commands.md](./docs/agent/development_commands.md) |
| 部署指南 | [docs/deployment/deployment-guide.md](./docs/deployment/deployment-guide.md) |
| Nginx 30000 部署 | [docs/deployment/nginx-30000-deployment.md](./docs/deployment/nginx-30000-deployment.md) |
| 端口参考 | [docs/deployment/port-reference.md](./docs/deployment/port-reference.md) |
| API 文档 | [app-controller/API.md](./app-controller/API.md) |
| 研发资产 | [docs/research/rd-assets.md](./docs/research/rd-assets.md) |

---

## AI Flow

1. `/ai-flow` - 完整需求交付流程
2. `/rd-asset-review` - 提取研发资产
3. `/tech-solution` - 生成技术方案

## 部署与验证信息（用于每次测试/部署）

- 部署服务器：`root@ubuntu.hamr.top`，SSH 端口 `27144`
- 仓库路径：`/root/ai-os`
- 服务访问入口：`http://ubuntu.hamr.top:27160/`
- 默认登录密码：`admin123`
- 更新方式：本地更新并推送后，服务器端可直接拉取代码并重启服务

---

> 更新于 2026-04-24
