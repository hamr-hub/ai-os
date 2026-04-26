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

### 解决的问题

| 问题类型 | 具体表现 | 解决方案 |
|----------|----------|----------|
| **可靠性问题** | vLLM 未启动时，Node.js 请求长时间挂起超时 | Python 后端自动截断请求并返回错误 |
| **显存溢出** | 并发请求过多导致 GPU 显存不足 | Redis 队列实现并发控制，保护显存 |
| **资源浪费** | 模型持续运行占用显存 | 根据请求自动启动/停止模型 |
| **缺乏监控** | 无法实时了解 GPU 和模型状态 | WebSocket 实时状态推送 |
| **模型切换慢** | 每次切换模型需要手动启停 | 预加载/常驻策略，秒级切换 |

### 核心优势

| 特性 | 描述 |
|------|------|
| 🎯 **可靠性保障** | vLLM 未启动时，Python 后端自动截断请求并报错，避免 Node.js 挂起超时 |
| 🎯 **流量削峰** | Redis 队列实现并发控制，保护 GPU 显存 |
| 🎯 **自动管理** | 根据请求自动启动/停止模型，节省资源 |
| 🎯 **无缝对接** | 通过自定义渠道配置，原有的用户分组、额度扣费、对话历史直接可用 |
| 🎯 **实时监控** | WebSocket 推送 GPU 状态和模型状态到前端 |
| 🎯 **健康检查** | 综合健康评分（0-100），支持告警机制 |
| 🎯 **自动评测** | 内置模型功能性测试与性能基准测试（TPS、延迟、通过率） |

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
# 安装/同步服务单元
sudo ./scripts/install_systemd_services.sh --enable

# 启动服务
sudo systemctl enable redis
sudo systemctl enable ai-controller
sudo systemctl enable go-vllm-api
sudo systemctl start redis
sudo systemctl start ai-controller
sudo systemctl start go-vllm-api

# 查看状态
sudo systemctl status ai-controller
journalctl -u go-vllm-api -f
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
   - Base URL：`http://localhost:35001/v1`
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
| `/v1/test/model/{name}` | POST | 运行模型评测 |
| `/v1/test/reports` | GET | 获取所有评测报告 |
| `/health` | GET | 健康检查 |

---

## 🛠️ 常用命令

```bash
# 查看 GPU 状态
curl http://localhost:35000/manage/gpu

# 启动模型
curl -X POST http://localhost:35000/manage/models/Gemma-4-31B/start

# 健康检查
curl http://localhost:35000/health

# 查看队列
curl http://localhost:35000/manage/queue
```

---

## 📊 监控与告警

### 健康评分

系统会计算综合健康评分（0-100）：

| 分数范围 | 状态 | 说明 |
|----------|------|------|
| 90-100 | healthy | 健康 |
| 70-89 | degraded | 降级 |
| 50-69 | warning | 警告 |
| 0-49 | critical | 严重 |

### Prometheus 指标

服务暴露 `/metrics` 端点，提供以下指标：
- 请求总数和错误率
- 请求延迟分布
- GPU 内存使用情况
- GPU 温度
- 模型状态
- 队列长度

### WebSocket 监控

连接 `ws://localhost:35000/ws/monitor` 获取实时状态推送。

---

## ⚙️ 配置说明

### 模型配置示例

```yaml
models:
  Gemma-4-31B:
    service: vllm-gemma        # systemd 服务名
    port: 8000                 # vLLM 监听端口
    required_memory: 40GB      # 模型所需显存
    preload: true              # 是否预加载（启动时自动加载）
    keep_alive: true           # 是否保持运行（不因空闲停止）
    model_path: /mnt/models/Gemma-4-31B
    supports_images: false     # 是否支持图像输入
    description: "模型描述"

settings:
  concurrency_limit: 32              # 并发请求限制
  min_available_memory: 4GB          # 最小可用显存阈值
  request_timeout: 120               # 请求超时（秒）
  idle_timeout: 600                  # 空闲超时（秒）
  gpu_memory_utilization: 0.92       # GPU 显存利用率
```

### 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `REDIS_URL` | redis://localhost:6379 | Redis 连接地址 |
| `PORT` | 35000 | 服务端口 |
| `LOG_LEVEL` | INFO | 日志级别 |
| `MODEL_BASE_PATH` | /mnt/pve_models | 模型存储路径 |

---

## 🔧 故障排查

### 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| GPU 不可用 | 驱动未安装或 CUDA 版本不兼容 | 检查 nvidia-smi，更新驱动 |
| 模型启动失败 | 显存不足 | 关闭其他模型，增加 min_available_memory |
| Redis 连接失败 | Redis 未启动 | 启动 Redis 服务 |
| 服务无法启动 | 端口被占用 | 修改 PORT 环境变量 |

### 日志查看

```bash
# 查看 AI Controller 日志
tail -f app-controller/logs/ai_controller.log

# 查看 systemd 日志
journalctl -u ai-controller -f

# 查看 Docker 日志
docker-compose logs -f ai-controller
```

---

## 📈 性能优化

### 显存管理策略

- **保守模式**：`default_memory_strategy: conservative`（显存利用率 0.8）
- **平衡模式**：`default_memory_strategy: balanced`（显存利用率 0.9）
- **激进模式**：`default_memory_strategy: aggressive`（显存利用率 0.95）

### 并发控制

根据 GPU 显存和模型大小调整 `concurrency_limit` 参数：
- 70B 模型：建议 2-4 并发
- 30B 模型：建议 4-8 并发
- 10B 模型：建议 8-16 并发

---

## 📄 许可证

MIT License

---

## 📞 联系方式

如有问题或建议，欢迎提交 Issue 或 PR。

---

**项目版本**: v1.0  
**最后更新**: 2026-04-21  
**适用平台**: Linux (NVIDIA GPU)
