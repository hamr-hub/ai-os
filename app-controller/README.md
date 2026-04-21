# AI Controller - 本地 LLM 模型管理服务

基于 Python FastAPI 的控制层服务，用于管理本地大语言模型，提供 GPU 资源监控、智能调度和队列管理功能。

---

## 📋 项目意图

### 背景
AIClient-2-API 是一个优秀的 API 代理服务，提供了完善的鉴权、用户管理和 UI 界面。但是它本身不包含大模型，也没有能力控制本地 GPU 资源。

### 核心目标
本项目旨在实现**"外壳解耦，内核驱动"**的架构方案：

1. **保留 AIClient-2-API 作为入口/UI**：不修改原有代码，通过 Git 持续更新
2. **新增 Python 控制层作为核心大脑**：实现智能调度、资源监控和队列管理
3. **无缝对接**：通过自定义渠道配置，原有用户分组、额度扣费、对话历史全部直接可用

### 解决的问题
- 🎯 **可靠性保障**：如果 vLLM 未启动，Python 后端会截断请求并报错，避免 Node.js 侧长时间挂起超时
- 🎯 **流量削峰**：利用并发控制保护 GPU，防止显存溢出
- 🎯 **自动管理**：根据请求自动启动/停止模型，节省资源

---

## 🏗️ 架构设计

```
┌──────────────────────────┐
│   AIClient-2-API        │  ← 入口层：鉴权、UI、协议转发
│     (Node.js)           │
└──────────┬──────────────┘
           │ OpenAI 协议
           ▼
┌──────────────────────────┐
│   AI Controller         │  ← 控制层：逻辑调度、资源监控、队列管理
│    (FastAPI/Python)     │
└──────────┬──────────────┘
           │
     ┌─────┴─────┐
     ▼           ▼
┌──────────┐ ┌──────────┐
│ nvidia-smi│ │ systemctl│  ← 基础设施层：显存采集、模型启停
└──────────┘ └──────────┘
           │
           ▼
┌──────────────────────────┐
│     vLLM Instance       │  ← 推理层：实际模型推理
└──────────────────────────┘
```

---

## 🚀 快速开始

### 前置条件
- Python 3.10+
- NVIDIA GPU（支持 CUDA）
- vLLM 已安装
- Redis（可选，用于队列和缓存）
- Systemd（用于模型服务管理，Linux 系统）

### 一键安装

```bash
cd app-controller
./setup.sh
```

### 手动安装

```bash
cd app-controller
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 配置模型

编辑 `config.yaml` 配置你的模型：

```yaml
models:
  gemma-2-9b:
    service: vllm-gemma    # systemd 服务名
    port: 8000             # vLLM 监听端口
    required_memory: 12GB  # 模型所需显存
    preload: false         # 是否预加载
    keep_alive: true       # 是否保持运行
    model_path: /path/to/model
    supports_images: false
    description: "模型描述"

settings:
  concurrency_limit: 4         # 并发请求限制
  min_available_memory: 2GB    # 最小可用显存阈值
  request_timeout: 120         # 请求超时（秒）
  model_start_timeout: 120     # 模型启动超时（秒）
  gpu_memory_utilization: 0.92 # GPU 显存利用率
```

### 启动服务

**方式一：使用脚本**
```bash
./start.sh
```

**方式二：使用 Makefile**
```bash
make run
```

**方式三：直接运行**
```bash
python main.py
```

服务将在 `http://localhost:5000` 启动

### 使用 systemd 部署

```bash
sudo cp systemd/ai-controller.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ai-controller
sudo systemctl start ai-controller
```

---

## 🔌 API 接口

### OpenAI 兼容接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/v1/chat/completions` | POST | 聊天补全（支持流式和图像） |
| `/v1/images/generations` | POST | 图像生成 |
| `/v1/embeddings` | POST | Embedding 向量生成 |
| `/v1/models` | GET | 获取可用模型列表 |

### 管理接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/manage/gpu` | GET | GPU 详细状态 |
| `/manage/gpu/summary` | GET | GPU 摘要（含历史） |
| `/manage/gpu/history` | GET | GPU 历史记录 |
| `/manage/models` | GET | 所有模型状态 |
| `/manage/models/summary` | GET | 模型汇总（适合UI） |
| `/manage/models/{name}/info` | GET | 单个模型详情 |
| `/manage/models/{name}/start` | POST | 启动模型 |
| `/manage/models/{name}/stop` | POST | 停止模型 |
| `/manage/models/{name}/switch` | POST | 切换模型 |
| `/manage/preload/status` | GET | 预加载状态 |
| `/manage/preload/{name}/enable` | POST | 启用预加载 |
| `/manage/preload/{name}/disable` | POST | 禁用预加载 |
| `/manage/queue` | GET | 队列状态 |
| `/manage/config` | GET | 当前配置 |
| `/manage/config/reload` | POST | 重新加载配置 |
| `/manage/metrics` | GET | 服务指标 |
| `/manage/system/status` | GET | 系统状态（CPU/内存/磁盘） |
| `/health` | GET | 健康检查 |
| `/health/detailed` | GET | 详细健康检查 |
| `/metrics` | GET | Prometheus 指标 |
| `/api/v1/status` | GET | Node.js 集成状态检查 |

### 图像接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/v1/images/validate` | POST | 验证 Base64 图像 |
| `/v1/images/upload` | POST | 上传图像文件 |
| `/v1/images/info` | GET | 图像服务信息 |
| `/v1/images/generations` | POST | OpenAI 兼容图像生成 |

### WebSocket

| 接口 | 说明 |
|------|------|
| `/ws/monitor` | 实时监控推送 |

---

## 📁 项目结构

```
app-controller/
├── main.py                  # FastAPI 入口，定义 API 路由
├── config.yaml              # 模型配置文件
├── requirements.txt         # Python 依赖列表
├── Makefile                 # 构建和运维命令
├── API.md                   # 详细 API 文档
├── setup.sh                 # 安装脚本
├── start.sh                 # 启动脚本
├── stop.sh                  # 停止脚本
├── .gitignore               # Git 忽略规则
├── core/
│   ├── __init__.py
│   ├── config.py            # 配置管理（Pydantic）
│   ├── config_watcher.py    # 配置文件热更新监控
│   ├── monitor.py           # GPU 监控（nvidia-smi）
│   ├── scheduler.py         # 智能调度器
│   ├── sys_ctl.py           # 系统控制（systemd）
│   ├── rate_limiter.py      # 速率限制器
│   ├── metrics.py           # 指标收集器
│   ├── prometheus_exporter.py # Prometheus 导出器
│   ├── websocket_manager.py  # WebSocket 管理器
│   ├── redis_client.py      # Redis 客户端
│   ├── logger.py            # 日志配置
│   └── structured_logger.py # 结构化日志
├── middleware/
│   ├── __init__.py
│   ├── error_handler.py     # 错误处理中间件
│   ├── rate_limit.py        # 速率限制中间件
│   └── timeout_handler.py   # 超时处理中间件
├── api/
│   ├── __init__.py
│   └── proxy_vllm.py        # vLLM 代理
└── systemd/
    └── ai-controller.service # Systemd 服务配置
```

---

## ✨ 核心特性

1. **智能模型启动**：收到请求时自动检查并启动模型
2. **显存保护**：剩余显存不足时返回 503 错误，防止炸显存
3. **Systemd 集成**：通过 systemctl 可靠地管理模型生命周期
4. **流式响应支持**：完整支持 SSE 流式输出
5. **灵活配置**：通过 YAML 文件轻松配置多个模型
6. **实时监控**：提供 GPU 状态和模型状态 API
7. **模型预加载**：支持模型预加载和自动启动策略
8. **并发控制**：Redis 支持的并发请求队列
9. **健康检查**：综合健康评分和告警机制
10. **Prometheus 集成**：完整的监控指标导出
11. **WebSocket 推送**：实时 GPU 和模型状态推送
12. **结构化日志**：JSON 格式的结构化日志输出

---

## 🛠️ 开发说明

### 使用 Makefile

```bash
make install      # 安装依赖
make run          # 运行服务
make dev          # 开发模式（自动重载）
make prod         # 生产模式
make test         # 运行测试
make lint         # 代码检查
make format       # 代码格式化
make status       # 检查服务状态
make gpu          # 获取 GPU 状态
make models       # 获取模型状态
make health       # 健康检查
make logs         # 查看日志
make restart      # 重启服务
make preload-all  # 预加载所有模型
```

### 核心模块职责

| 模块 | 职责 |
|------|------|
| `core/monitor.py` | 读取 nvidia-smi 获取 GPU 实时数据 |
| `core/sys_ctl.py` | 执行 systemctl 命令控制服务启停 |
| `core/scheduler.py` | 智能调度：显存检查、模型启停、切换 |
| `core/rate_limiter.py` | Redis 支持的并发控制和队列管理 |
| `core/metrics.py` | 服务指标收集和聚合 |
| `core/prometheus_exporter.py` | Prometheus 指标导出 |
| `core/websocket_manager.py` | WebSocket 连接管理和广播 |
| `core/config_watcher.py` | 配置文件热更新 |
| `api/proxy_vllm.py` | vLLM 请求代理和重试 |

---

## 📊 监控与告警

### 健康评分

系统会计算综合健康评分（0-100）：
- **90-100**: healthy（健康）
- **70-89**: degraded（降级）
- **50-69**: warning（警告）
- **0-49**: critical（严重）

### Prometheus 指标

服务暴露 `/metrics` 端点，提供以下指标：
- 请求总数和错误率
- 请求延迟分布
- GPU 内存使用情况
- GPU 温度
- 模型状态
- 队列长度

---

## 📄 许可证

MIT License

---

## 📞 联系方式

如有问题或建议，欢迎提交 Issue 或 PR。

详细 API 文档请参考 [API.md](API.md)。
