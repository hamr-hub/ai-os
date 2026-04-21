# AI Controller - vLLM 本地模型控制层

基于 Python FastAPI 的控制层服务，用于管理本地大语言模型，提供 GPU 资源监控、智能调度和队列管理功能。

---

## 📋 项目背景

### 问题分析

在使用 AIClient-2-API 作为前端入口时，发现以下核心问题：

| 问题类型 | 具体表现 | 影响 |
|----------|----------|------|
| **可靠性问题** | vLLM 未启动时，Node.js 请求长时间挂起超时 | 用户体验差，服务不可用 |
| **显存溢出** | 并发请求过多导致 GPU 显存不足 | 服务崩溃，需要手动重启 |
| **资源浪费** | 模型持续运行占用显存 | 成本高，无法充分利用硬件 |
| **缺乏监控** | 无法实时了解 GPU 和模型状态 | 问题发现滞后，排查困难 |
| **模型切换慢** | 每次切换模型需要手动启停 | 效率低，响应延迟 |

### 解决方案

本项目实现**"外壳解耦，内核驱动"**的架构方案：

1. **保留 AIClient-2-API 作为入口/UI**：不修改原有代码，通过 Git 持续更新
2. **新增 Python 控制层作为核心大脑**：实现智能调度、资源监控和队列管理
3. **无缝对接**：通过自定义渠道配置，原有用户分组、额度扣费、对话历史全部直接可用

### 核心功能

| 功能 | 描述 |
|------|------|
| 🎯 **可靠性保障** | vLLM 未启动时自动截断请求并返回错误，避免挂起 |
| 🎯 **流量削峰** | Redis 队列实现并发控制，保护 GPU 显存 |
| 🎯 **自动管理** | 根据请求自动启动/停止模型，节省资源 |
| 🎯 **模型热切换** | 支持秒级模型切换，引入预加载/常驻策略 |
| 🎯 **显存优化** | 动态调整显存利用率，支持缓存清理 |
| 🎯 **实时监控** | WebSocket 推送 GPU 和模型状态 |

---

## 🏗️ 架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                     AIClient-2-API (Node.js)                   │  ← 入口层：鉴权、UI、协议转发
└───────────────────────────┬─────────────────────────────────────┘
                            │ OpenAI 协议 (/v1/chat/completions)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   AI Controller (FastAPI)                      │  ← 控制层：调度、监控、队列
│  ┌──────────────┬──────────────┬──────────────┐               │
│  │  Scheduler  │  RateLimiter │ GPUMonitor   │               │
│  │ (智能调度)   │ (Redis队列)  │ (显存监控)   │               │
│  └──────┬───────┴──────┬───────┴──────┬───────┘               │
│         │              │              │                        │
└─────────┼──────────────┼──────────────┼───────────────────────┘
          │              │              │
          ▼              ▼              ▼
   ┌────────────┐ ┌────────────┐ ┌────────────┐
   │ systemctl  │ │   Redis    │ │ nvidia-smi │  ← 基础设施层
   │(服务启停)  │ │  (队列存储) │ │ (显存采集) │
   └──────┬─────┘ └────────────┘ └────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      vLLM Instance                             │  ← 推理层：实际模型推理
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 快速开始

### 前置条件

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | >= 3.10 | 运行环境 |
| NVIDIA GPU | - | 支持 CUDA |
| vLLM | >= 0.5.0 | 模型推理引擎 |
| Redis | >= 7.0 | 队列存储（可选） |
| Systemd | - | 模型服务管理（Linux） |

### 安装步骤

**方式一：一键安装**

```bash
cd app-controller
./setup.sh
```

**方式二：手动安装**

```bash
cd app-controller
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 配置模型

编辑 `config.yaml` 配置你的模型：

```yaml
models:
  Gemma-4-31B-Abliterated:
    service: vllm              # systemd 服务名
    port: 8000                 # vLLM 监听端口
    required_memory: 40GB      # 模型所需显存
    preload: true              # 是否预加载（启动时自动加载）
    keep_alive: true           # 是否保持运行（不因空闲停止）
    model_path: /mnt/pve_models/Gemma-4-31B-Abliterated
    supports_images: false     # 是否支持图像输入
    description: "Gemma 4 31B 模型（去审查版）"

settings:
  concurrency_limit: 32              # 并发请求限制
  min_available_memory: 4GB          # 最小可用显存阈值
  request_timeout: 120               # 请求超时（秒）
  model_start_timeout: 120           # 模型启动超时（秒）
  idle_timeout: 600                  # 空闲超时（秒），超时后自动停止非常驻模型
  gpu_memory_utilization: 0.92       # GPU 显存利用率
  default_memory_strategy: balanced  # 显存策略：conservative/balanced/aggressive

vllm:
  service_name: vllm
  start_script: /root/ai-suite/start_vllm.sh
  model_base_path: /mnt/pve_models
  default_port: 8000
```

### 启动服务

**开发模式**
```bash
./start.sh
```

**使用 Makefile**
```bash
make run      # 运行服务
make dev      # 开发模式（自动重载）
make prod     # 生产模式
```

**直接运行**
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

# 查看状态和日志
sudo systemctl status ai-controller
journalctl -u ai-controller -f
```

---

## 🔌 与 AIClient-2-API 集成

### 配置自定义渠道

在 AIClient-2-API 中添加自定义渠道，指向 AI Controller：

1. 登录 AIClient-2-API 管理界面
2. 进入「渠道管理」→「添加渠道」
3. 配置如下：
   - 渠道名称：`AI Controller`
   - 渠道类型：`OpenAI`
   - API 地址：`http://localhost:5000/v1`
   - API Key：任意值（当前版本不校验）
4. 保存并启用渠道

### 模型映射

AI Controller 会自动同步可用模型列表到 AIClient-2-API，无需手动配置。

---

## 📡 API 接口

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
| `/manage/models` | GET | 所有模型状态 |
| `/manage/models/{name}/info` | GET | 单个模型详情 |
| `/manage/models/{name}/start` | POST | 启动模型 |
| `/manage/models/{name}/stop` | POST | 停止模型 |
| `/manage/models/{name}/switch` | POST | 切换模型（自动管理显存） |
| `/manage/queue` | GET | 队列状态 |
| `/manage/config` | GET | 当前配置 |
| `/manage/config/reload` | POST | 重新加载配置 |
| `/health` | GET | 健康检查 |
| `/health/detailed` | GET | 详细健康检查 |
| `/metrics` | GET | Prometheus 指标 |
| `/api/v1/status` | GET | Node.js 集成状态检查 |

### WebSocket

| 接口 | 说明 |
|------|------|
| `/ws/monitor` | 实时监控推送（每秒更新） |

---

## 📁 项目结构

```
app-controller/
├── main.py                  # FastAPI 入口
├── config.yaml              # 模型配置文件
├── requirements.txt         # Python 依赖列表
├── Makefile                 # 构建和运维命令
├── setup.sh                 # 安装脚本
├── start.sh                 # 启动脚本
├── stop.sh                  # 停止脚本
├── API.md                   # 详细 API 文档
├── TECHNICAL_DESIGN.md      # 技术设计文档
├── core/
│   ├── config.py            # 配置管理
│   ├── config_watcher.py    # 配置热更新监控
│   ├── monitor.py           # GPU 监控
│   ├── scheduler.py         # 智能调度器
│   ├── sys_ctl.py           # 系统控制
│   ├── rate_limiter.py      # 速率限制器
│   ├── metrics.py           # 指标收集器
│   ├── prometheus_exporter.py # Prometheus 导出器
│   ├── websocket_manager.py  # WebSocket 管理器
│   ├── redis_client.py      # Redis 客户端
│   └── logger.py            # 日志配置
├── middleware/
│   ├── error_handler.py     # 错误处理
│   ├── rate_limit.py        # 速率限制中间件
│   └── timeout_handler.py   # 超时处理
├── api/
│   └── proxy_vllm.py        # vLLM 代理
├── scripts/
│   ├── install_vllm_aiclient_service.sh
│   └── start_vllm_aiclient.sh
└── systemd/
    └── ai-controller.service
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

---

## 🛠️ 常用命令

```bash
make install      # 安装依赖
make run          # 运行服务
make dev          # 开发模式
make prod         # 生产模式
make test         # 运行测试
make lint         # 代码检查
make status       # 检查服务状态
make gpu          # 获取 GPU 状态
make models       # 获取模型状态
make health       # 健康检查
make logs         # 查看日志
make restart      # 重启服务
make preload-all  # 预加载所有模型
```

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