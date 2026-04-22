# AI Flow 项目指南

> **ai-os** - 多模块 AI 操作系统（Vue 3 + FastAPI）

---

## 🎯 项目愿景

构建一个模块化的 AI 操作系统，包含：
- **frontend**: Vue 3 前端界面
- **app-controller**: Python FastAPI 后端服务
- **aiclient2api**: API 网关层

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
├── app-controller/        # Python FastAPI
│   ├── core/             # 核心模块
│   ├── api/              # API 路由
│   ├── main.py           # 入口文件
│   └── config.yaml       # 配置
│
├── aiclient2api/          # API 网关
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
pnpm dev              # 启动开发服务器 (http://localhost:5173)
pnpm build            # 生产构建
pnpm lint             # 代码检查
```

### 后端开发
```bash
cd app-controller
python -m venv venv   # 创建虚拟环境
source venv/bin/activate
pip install -r requirements.txt
python main.py        # 启动服务 (http://localhost:8000)
```

### Docker 部署
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

### 后端
- **框架**: FastAPI
- **运行时**: Python 3.11+
- **配置**: YAML
- **测试**: Pytest

---

## 📝 开发规范

详细规范见:
- **[.codeflicker/rules.md](./.codeflicker/rules.md)** - 开发规则
- **[docs/agent/conventions.md](./docs/agent/conventions.md)** - 编码约定

---

## 🔗 相关文档

- **API 文档**: `app-controller/API.md`
- **集成指南**: `app-controller/AICLIENT_INTEGRATION.md`
- **行为准则**: `app-controller/CODE_OF_CONDUCT.md`

---

## 💡 使用 AI Flow

本项目已配置 AI Flow，可以:
1. 运行 `/ai-flow` 执行完整需求交付流程
2. 运行 `/rd-asset-review` 提取研发资产
3. 运行 `/tech-solution` 生成技术方案

---

> 自动生成于 2026-04-22 | AI Flow v0.4.16
