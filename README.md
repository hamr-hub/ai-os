# AI OS - vLLM 本地模型控制平台

基于 AIClient-2-API + Python FastAPI 的本地大语言模型管理平台，实现"外壳解耦，内核驱动"的架构方案。

---

## 📋 项目背景

### 架构设计

```
┌──────────────────────────┐
│   AIClient-2-API        │  ← (1) 入口层：鉴权、UI、协议转发（原封不动）
│    (Node.js)            │
└──────────┬──────────────┘
           │ OpenAI 协议
           ▼
┌──────────────────────────┐
│   AI Controller         │  ← (2) 控制层：逻辑调度、资源监控、队列管理
│    (FastAPI/Python)     │
└──────────┬──────────────┘
           │
     ┌─────┴─────┬───────────┐
     ▼           ▼           ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│  Redis   │ │nvidia-smi│ │systemctl │  ← (3) 基础设施层
│ (队列)   │ │(显存监控) │ │(模型启停)│
└──────────┘ └──────────┘ └──────────┘
           │
           ▼
┌──────────────────────────┐
│     vLLM Instance       │  ← (4) 推理层：实际模型推理
└──────────────────────────┘
```

### 核心优势

| 特性 | 描述 |
|------|------|
| 🎯 **可靠性保障** | vLLM 未启动时，Python 后端自动截断请求并报错，避免 Node.js 挂起超时 |
| 🎯 **流量削峰** | Redis 队列实现并发控制，保护 GPU 显存 |
| 🎯 **自动管理** | 根据请求自动启动/停止模型，节省资源 |
| 🎯 **无缝对接** | 通过自定义渠道配置，原有的用户分组、额度扣费、对话历史直接可用 |

---

## 📁 项目结构

```
/root/ai-os/
├── aiclient2api/          # AIClient-2-API 原项目（保持原样）
│   └── (Node.js 代码)
│
├── app-controller/        # Python 控制层（核心大脑）
│   ├── main.py            # FastAPI 入口
│   ├── config.yaml        # 模型配置
│   ├── requirements.txt   # Python 依赖
│   ├── Makefile           # 构建命令
│   ├── core/              # 核心模块
│   │   ├── scheduler.py   # 智能调度器
│   │   ├── monitor.py     # GPU 监控
│   │   └── sys_ctl.py     # 系统控制
│   └── api/
│       └── proxy_vllm.py  # vLLM 请求代理
│
├── systemd/               # Systemd 服务配置
│   ├── ai-controller.service    # Python 控制层服务
│   ├── vllm-gemma.service       # Gemma 模型服务
│   ├── vllm-llama.service       # Llama 模型服务
│   └── vllm-aiclient.service    # 默认 vLLM 服务
│
├── config.yaml            # 全局配置（映射表：模型名 -> 服务名 -> 端口）
├── LICENSE                # MIT 许可证
└── README.md              # 项目说明
```

---

## 🚀 快速开始

### 前置条件

| 依赖 | 说明 |
|------|------|
| Python >= 3.10 | 运行环境 |
| Node.js >= 18 | AIClient-2-API |
| NVIDIA GPU | 支持 CUDA |
| vLLM >= 0.5.0 | 模型推理引擎 |
| Redis >= 7.0 | 队列存储 |

### 安装步骤

**1. 安装 AIClient-2-API**

```bash
cd /root/ai-os/aiclient2api
npm install
```

**2. 安装 Python 控制层**

```bash
cd /root/ai-os/app-controller
./setup.sh
```

**3. 配置模型**

编辑 `/root/ai-os/config.yaml`：

```yaml
models:
  Gemma-4-31B:
    service: vllm-gemma
    port: 8000
    required_memory: 40GB
    preload: true
    keep_alive: true
    model_path: /mnt/models/Gemma-4-31B

settings:
  concurrency_limit: 32
  min_available_memory: 4GB
```

**4. 启动服务**

```bash
# 启动 Redis
redis-server &

# 启动 Python 控制层
cd app-controller
./start.sh

# 启动 AIClient-2-API
cd aiclient2api
npm start
```

### 使用 systemd 部署

```bash
# 安装服务
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload

# 启动服务
sudo systemctl enable redis
sudo systemctl enable ai-controller
sudo systemctl start redis
sudo systemctl start ai-controller

# 查看状态
sudo systemctl status ai-controller
journalctl -u ai-controller -f
```

### 使用一键启动脚本

```bash
cd /root/ai-os
./start.sh
```

### 使用 Docker Compose 部署

```bash
cd /root/ai-os
docker-compose up -d

# 查看日志
docker-compose logs -f ai-controller

# 停止服务
docker-compose down
```

---

## 🔌 与 AIClient-2-API 集成

### 配置自定义渠道

在 AIClient-2-API 管理界面添加渠道：

1. 进入「渠道管理」→「添加渠道」
2. 配置：
   - 类型：Custom / OpenAI
   - Base URL：`http://localhost:5000/v1`
   - API Key：任意值（本地验证）

### 模型自动同步

Python 控制层会自动将配置的模型列表同步到 AIClient-2-API，无需手动配置。

---

## 📡 API 接口

### OpenAI 兼容接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/v1/chat/completions` | POST | 聊天补全（支持流式） |
| `/v1/models` | GET | 获取模型列表 |
| `/v1/embeddings` | POST | 向量生成 |

### 管理接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/manage/gpu` | GET | GPU 状态 |
| `/manage/models` | GET | 模型状态 |
| `/manage/models/{name}/start` | POST | 启动模型 |
| `/manage/models/{name}/stop` | POST | 停止模型 |
| `/manage/queue` | GET | 队列状态 |
| `/health` | GET | 健康检查 |

---

## 🛠️ 常用命令

```bash
# 查看 GPU 状态
curl http://localhost:5000/manage/gpu

# 启动模型
curl -X POST http://localhost:5000/manage/models/Gemma-4-31B/start

# 健康检查
curl http://localhost:5000/health

# 查看队列
curl http://localhost:5000/manage/queue
```

---

## 📊 监控与告警

- **健康评分**：0-100 分，实时评估系统状态
- **Prometheus**：`/metrics` 端点导出监控指标
- **WebSocket**：`/ws/monitor` 实时状态推送

---

## 📄 许可证

MIT License

---

## 📞 联系方式

如有问题或建议，欢迎提交 Issue 或 PR。