# 架构设计

> ai-os 多模块架构说明

---

## 系统架构

> **核心设计**: 双路径分层 — C端推理走 aiclient2api Node → Go 限流代理 → 推理引擎；B端管控走 Frontend/插件 → Python → 引擎&模型管理

```
┌──────────────────────────────────────────────────────────────────┐
│                          用户界面层                               │
│                                                                   │
│  ┌────────────────────────┐    ┌───────────────────────────────┐ │
│  │    Vue 3 Frontend      │    │     aiclient2api              │ │
│  │    管理面板 (B端入口)   │    │     开源项目 + GPU 插件       │ │
│  │    dev:30001/prod:30000│    │     localhost:3000 (Docker)   │ │
│  └───────────┬────────────┘    └───────────┬───────────────────┘ │
└──────────────┼─────────────────────────────┼─────────────────────┘
               │                             │
      ┌────────┴────────┐          ┌─────────┴──────────┐
      │  B端管控路径     │          │  C端推理路径        │
      │  管理/管控请求   │          │  Provider 配置     │
      ▼                 │          ▼                    │
┌────────────────────────┴──────┐ ┌┴──────────────────────────────┐
│    Python B端 (管控平台)       │ │  aiclient2api Node 后端       │
│    app-controller :35000      │ │  自身 Node.js 服务            │
│                                │ │  鉴权 + 转发 + 路由           │
│  推理引擎控制:                  │ └──────────┬───────────────────┘
│  · 启停 / 切换 (vLLM↔SGLang)  │            │
│  模型管理:                      │            │ provider.baseURL
│  · 切换 / 下载 / 搜索          │            │ → go-vllm-api:35001
│  GPU显存校验 / 模型池           │            ▼
│  WebSocket / 配置热加载         │ ┌──────────────────────────────┐
└─────────────┬──────────────────┘ │  Go vLLM 限流代理            │
              │                    │  go-vllm-api :35001          │
              │ 进程管理            │  限流 / SSE流式 / 并发控制    │
              │ (subprocess)        │  排队 / 配置热加载            │
              ▼                    └──────────┬───────────────────┘
┌──────────────────────────────────────────────────────────────────┐
│                          推理层                                   │
│  vLLM Instance (:8000)                                           │
│  SGLang Instance (:8000)                                         │
│  llama.cpp (:8001/8002)                                          │
└──────────────────────────────────────────────────────────────────┘
                                                  │
                                                  ▼
                            ┌──────────────────────────────────────┐
                            │          基础设施层                  │
                            │  Redis :6379 (限流Key + 缓存数据)    │
                            └──────────────────────────────────────┘
```

**两条核心路径**

| 路径 | 流量 | 入口 → 终点 | 职责 |
|------|------|-------------|------|
| **C端推理** | 用户推理请求 | aiclient2api(Node:3000) → provider → go-vllm-api(:35001) → 推理引擎(:8000) | 鉴权转发、限流排队、SSE流式 |
| **B端管控** | 管理员操作 | Frontend(:30000) + GPU插件 → Python B端(:35000) → 推理引擎/模型管理 | 引擎启停切换、模型下载切换、显存校验 |

---

## 架构边界定义

| 项目 | 定位 | 访问端 | 核心职责 |
|------|------|--------|----------|
| **aiclient2api** (Node后端) | C端推理入口 | C端用户/客户端 | 鉴权、转发、provider配置路由到Go限流代理 |
| **Go 限流代理** (go-vllm-api) | vLLM流量限流网关 | aiclient2api Node后端 | 协议转发、SSE流式、限流排队、并发控制、配置热加载 |
| **Python B端** (app-controller) | 后台管控平台 | Frontend/GPU插件(管理员) | 推理引擎启停/切换、模型切换/下载/搜索、GPU监控、显存校验、WebSocket广播 |

---

## 模块说明

### Frontend (Vue 3) - 端口 30001 / 30000

**核心模块**
```
frontend/src/
├── components/      # UI 组件
│   ├── AgentChatWindow.vue    # Agent对话窗口(流式SSE)
│   ├── LineChart.vue          # Chart.js图表封装
│   ├── Sidebar.vue            # 侧边导航
│   ├── TopBar.vue             # 顶栏
│   ├── ToastContainer.vue     # 通知容器
│   └── cards/                 # Dashboard数据卡片
│       ├── GpuMetricsCard.vue
│       ├── HealthAlertCard.vue
│       ├── RequestQueueCard.vue
│       ├── RunningModelsCard.vue
│       ├── SystemStatusCard.vue
│       ├── TokenUsageCard.vue
│       ├── VLLMMetricsCard.vue
├── views/           # 页面
│   ├── Dashboard.vue          # 主仪表盘
│   ├── MonitorView.vue        # GPU/系统监控详情
│   ├── ModelManagement.vue    # 模型管理(启停/切换/预加载)
│   ├── AgentView.vue          # AI Agent对话
│   ├── ModelBenchmarks.vue    # 模型基准测试
│   ├── DocsView.vue           # 文档查看器
│   ├── GPUManage.vue          # GPU管理
├── api/             # API调用封装
│   ├── client.ts              # 双axios实例(manage+v1) + SSE流式
│   └── utils/sse.ts           # 通用SSE解析器(fetch+ReadableStream)
├── stores/          # Pinia状态管理
│   ├── server.ts              # 后端选择(go/python/auto) + 连接探测
│   ├── app.ts                 # 全局状态 + Toast通知
│   ├── agentChat.ts           # 多会话Agent对话管理
│   ├── gpu.ts                 # GPU状态
├── composables/     # 组合式函数
│   ├── useGPU.ts               # GPU数据轮询
│   ├── useGPUHistory.ts        # GPU历史数据
│   ├── useGPUChartDatasets.ts  # GPU图表数据集
│   ├── useModelSwitch.ts       # 模型切换进度(WebSocket+轮询回退)
│   ├── useModels.ts            # 模型列表+默认模型
│   ├── useSystemData.ts        # 系统状态轮询
│   ├── useTokenStats.ts        # Token使用统计
│   ├── useTokenHistory.ts      # Token历史
│   ├── usePolling.ts           # 通用轮询工具
│   ├── useMarkdown.ts          # Markdown渲染
├── router/          # 路由配置 (hash-free createWebHistory)
└── types/           # TypeScript类型定义
```

**Nginx代理路由**
- `/` → aiclient2api (:3000)
- `/manage/` → frontend (:30000)
- `/api/manage/*` → Python (:35000) `/manage/*`
- `/api/health*` → Go (:35001) `/health*`
- `/api/*` → Python (:35000) `/manage/*`
- `/v1/test/*` → Python (:35000) `/v1/test/*`
- `/v1/*` → Go (:35001) `/v1/*` (SSE无缓冲)
- `/ws/*` → Python (:35000) `/ws/*` (WebSocket, 86400s超时)
- `/health` → Go (:35001) `/health`

---

### Go vLLM 限流代理 (C端推理网关) - 端口 35001

**项目定位**: vLLM限流代理网关，接收来自aiclient2api Node后端的provider路由流量，兼容OpenAI官方协议。

**核心模块**
```
go-vllm-api/
├── cmd/server/main.go         # 入口(338行): 初始化+路由+信号处理+广播循环
├── internal/
│   ├── config/
│   │   ├── config.go          # AppConfig/ModelConfig/Settings/VLLM/LlamaCpp/Discovery
│   │   └── watcher.go         # fsnotify文件监听+SIGHUP回调
│   ├── handler/
│   │   ├── v1/chat.go         # OpenAI兼容接口(569行): SSE流式+非流式+并发控制
│   │   ├── manage/manage.go   # 管理接口(1508行): 60+路由+Python代理
│   │   ├── health/health.go   # 健康检查+Prometheus指标
│   │   ├── ws/ws.go           # WebSocket管理/模型切换广播
│   │   ├── agent/agent.go     # Agent系统(工具调用+流式)
│   ├── proxy/vllm.go          # VLLMProxy(321行): HTTP代理+SSE channel缓冲+心跳
│   ├── service/
│   │   ├── scheduler.go       # 核心调度器(1023行): 模型生命周期+并发+排队+预加载
│   │   ├── vllm_manager.go    # vLLM服务管理: 启停+模型发现+端口+readiness探针
│   │   ├── llama_cpp_manager.go # llama.cpp服务管理: GGUF启停+进程守护
│   │   ├── gpu_monitor.go     # GPU监控: NVML+nvidia-smi+vLLM指标采集
│   │   ├── sysctl.go          # SystemController: systemd服务控制
│   │   ├── rate_limiter.go    # Redis限流器: IP QPS+并发slot+排队
│   │   ├── metrics_collector.go # 指标收集: 请求/Token/GPU
│   │   ├── ws_manager.go      # WebSocket频道管理+广播
│   │   ├── cache.go           # TTL缓存(Redis)
│   │   ├── cache_updater.go   # 后台缓存刷新循环
│   │   ├── model_testing.go   # 模型测试框架
│   │   ├── system.go          # 系统状态(CPU/内存/磁盘 via gopsutil)
│   ├── middleware/
│   │   ├── cors.go            # CORS跨域
│   │   ├── error.go           # 统一错误处理
│   │   ├── ratelimit.go       # IP限流(Redis-backed)+超时
│   │   ├── tracking.go        # RequestID+请求追踪日志
│   ├── model/                 # 请求/响应结构体
│   ├── repository/redis.go    # Redis客户端封装(go-redis/v9)
│   ├── tools/                 # Agent工具系统: Registry+Executor+Definitions
│   └── pkg/
│       ├── logger/            # Zap结构化日志
│       ├── prometheus/        # Prometheus指标导出
│       ├── response/          # 统一响应格式
│       ├── utils/image.go     # 图片校验/解码
└── configs/config.yaml        # 配置文件(186行)
```

**核心功能模块详解**

| 模块 | 实现 | 关键特性 |
|------|------|----------|
| **协议转发** | V1Handler + VLLMProxy | 兼容/v1/chat/completions等OpenAI接口; 模型自动启动+readiness探针 |
| **SSE流式** | gin.Stream() + channel(256缓冲) | 10s心跳防超时; usage解析; [DONE]哨兵; 客户端断开自动退出 |
| **限流排队** | RateLimiter(Redis) + Scheduler并发 | IP QPS限流; 全局并发slot; 优先级排队(WaitForSlot); 429响应 |
| **配置热加载** | fsnotify + SIGHUP信号 | 文件变更自动回调; 信号触发reloadRuntimeConfig; /manage/config/reload API |
| **Python代理** | proxyPythonManage() | 切换操作代理到Python; PYTHON_BACKEND_URL环境变量; broadcastStatusLoop轮询切换状态 |
| **模型发现** | VLLMManager.ScanModels() | 自动扫描/mnt/pve_models; config.json/tokenizer识别; GGUF扫描; MergeDiscoveredModels |
| **可观测** | Prometheus+结构化日志+健康评分 | /metrics端点; health_score综合评分; 请求追踪(RequestID) |

**SSE流式核心流程**
```
Client POST /v1/chat/completions (stream=true)
  → V1Handler.ChatCompletions
    → Scheduler.AcquireRequest (并发slot)
    → Scheduler.ensureModelReady (自动启动+探针)
    → VLLMProxy.StreamChatCompletion (HTTP→vLLM)
      → streamReader goroutine
        → bufio.Scanner逐行读取
        → heartbeat注入(10s无活动)
        → StreamEvent channel(缓冲256)
    → gin.Stream() 写入SSE事件
      → usage解析(prompt/completion tokens)
      → [DONE]哨兵发送
    → defer: ReleaseRequest + metrics.RecordRequest
```

---

### Python B端 (管控平台) - 端口 35000

**项目定位**: LLM服务管控中心，面向管理员/运维，模型/引擎全生命周期管理，与Go网关双向同步配置。

**核心模块**
```
app-controller/
├── main.py                    # 入口(265行): lifespan管理+路由注册+中间件+信号处理
├── core/
│   ├── config.py              # YAML配置加载
│   ├── config_watcher.py      # fsnotify+SIGHUP+回调(_on_config_changed)
│   ├── deps.py                # 依赖注入容器(单例): 所有服务实例+HTTP超时配置
│   ├── scheduler.py           # 任务调度: 模型启停+并发+排队+预加载+默认模型
│   ├── vllm_manager.py        # vLLM管理: 模型路径解析+聚合模型组+启停+配置热更新
│   ├── model_switch_orchestrator.py  # 4阶段原子切换(958行)
│   │                           # Phase1: 停止旧服务 / Phase2: 强制清理进程
│   │                           # Phase3: 启动新服务 / Phase4: 冒烟测试
│   │                           # 回滚: 任意Phase失败→恢复前模型
│   │                           # Session: UUID追踪+WebSocket进度+取消支持
│   ├── llm_service_manager.py # [重构新增] 统一引擎进程管理(subprocess.Popen)
│   │                           # 替代sys_ctl.py systemd方案，支持vLLM+SGLang双引擎
│   │                           # 进程生命周期: start/stop/restart/status/健康检查
│   │                           # 进程异常自动重启(3次→告警)
│   ├── gpu_memory_checker.py  # [重构新增] torch.cuda显存精准检测
│   │                           # 模型加载前安全校验(85%水位线)
│   │                           # torch.cuda不可用时降级nvidia-smi
│   ├── llm_engine_scheduler.py # [重构新增] 统一调度器
│   │                           # 整合scheduler+orchestrator+vllm_manager
│   │                           # dynamic_switch(): 5阶段(含显存校验)
│   │                           # dynamic_engine_switch(): vLLM↔SGLang一键切换
│   │                           # search_models/select_best_model/download_and_load(全流程自动化)
│   ├── multi_source_model_hub.py # [新增] 多源模型仓库管理器
│   │                           # HuggingFace/ModelScope/OpenXLab搜索+下载
│   │                           # 国内镜像加速(hf-mirror.com); 断点续传
│   │                           # 自动解析模型参数/量化类型
│   ├── model_pool_manager.py  # [新增] 模型池自动管理器
│   │                           # 已下载+本地扫描模型统一入库
│   │                           # 一键加载(显存校验→引擎启动)
│   │                           # 删除前运行状态校验
│   ├── monitor.py             # GPU监控: NVML+nvidia-smi+增强信息+进程
│   ├── vllm_metrics.py        # vLLM指标采集(Prometheus格式解析)
│   ├── sys_ctl.py             # systemd服务控制(启停重启) [重构后移除]
│   ├── websocket_manager.py   # WebSocket频道管理+广播
│   ├── metrics.py             # 请求/Token指标收集
│   ├── prometheus_exporter.py # Prometheus指标导出
│   ├── rate_limiter.py        # 内存限流器(IP QPS)
│   ├── redis_client.py        # Redis客户端封装
│   ├── cache_service.py       # TTL缓存(Redis)
│   ├── cache_updater.py       # 后台缓存刷新循环
│   ├── model_testing.py       # 模型测试框架
│   ├── structured_logger.py   # JSON结构化日志
├── middleware/
│   ├── error_handler.py       # 统一错误处理(ControllerException)
│   ├── rate_limit.py          # IP限流中间件(内存计数器)
│   ├── timeout_handler.py     # 请求超时中间件
├── routes/
│   ├── v1.py                  # OpenAI兼容接口(SSE流式+非流式)
│   ├── manage.py              # 管理接口(镜像Go路由+Python独有路由)
│   ├── health.py              # 健康检查+Prometheus指标
│   ├── websocket.py           # WebSocket端点
│   ├── agent.py               # Agent系统(工具调用+流式)
└── config.yaml                # 配置文件(292行): 13模型+vllm_params+model_groups
```

**核心功能模块详解**

| 模块 | 实现 | 关键特性 |
|------|------|----------|
| **原子切换** | ModelSwitchOrchestrator(958行) | 4Phase+回滚+session追踪+WS广播+取消; 支持switch/start/stop三种action |
| **配置管理** | YAML+fsnotify+SIGHUP | 双向热更新(文件+信号); /manage/config CRUD+reload API |
| **模型管理** | 自动扫描+预加载+默认模型 | vllm_params配置(GPU利用率/最大长度/chunked prefill); model_groups正则分组 |
| **GPU监控** | NVML+nvidia-smi+vLLM指标 | 增强信息(进程/PID/显存碎片); vLLM指标(TTFT/TPOT/缓存命中率) |
| **WebSocket** | ws_manager+广播循环 | /ws/monitor(每2s GPU+模型); /ws/model-switch(切换进度); 连接时状态同步 |
| **Agent系统** | 工具注册+执行+流式对话 | OpenAI function schema兼容; 工具调用循环+结果流式回传 |
| **多引擎管理** | LLMServiceManager+LLMEngineScheduler | subprocess进程管理(vLLM+SGLang); 动态引擎切换; 显存校验(GPUMemoryChecker); 5阶段含显存校验 |
| **多源模型仓库** | MultiSourceModelHub | HuggingFace/ModelScope/OpenXLab搜索+下载; 国内镜像加速; 断点续传; 自动解析参数/量化 |
| **模型池管理** | ModelPoolManager | 已下载+本地扫描统一入库; 一键加载(显存校验→引擎); 删除前状态校验 |
| **GPU显存优选** | GPUMemoryManager | 显存精准检测(torch.cuda); 自动估算模型显存需求; 智能筛选推荐最优模型 |

**Python独有路由(vs Go)**
```
GET  /manage/models/:name/vllm-config     # 模型vLLM配置读写
PUT  /manage/models/:name/vllm-config
GET  /manage/models/:name/vllm-params     # 模型运行参数读写
PUT  /manage/models/:name/vllm-params
GET  /manage/vllm/default-config          # 默认vLLM配置
GET  /manage/engines/status               # 各引擎运行状态(vLLM/SGLang/llama.cpp)
POST /manage/engines/switch               # 动态引擎切换(vLLM↔SGLang)
GET  /manage/engines/config               # 引擎全局配置
PUT  /manage/engines/config               # 引擎全局配置写入
GET  /manage/gpu/memory-check             # 显存精准检测(torch.cuda)
POST /manage/gpu/memory-check/:model      # 模型显存可行性校验
GET  /manage/gpu/recommend?keyword=xxx    # 显存优选推荐(自动筛选可运行模型)
GET  /manage/models/search?keyword=xxx    # 跨平台模型搜索(HF/ModelScope/OpenXLab)
POST /manage/models/download              # 启动模型下载任务
GET  /manage/models/download/:task_id/status # 下载进度查询
GET  /manage/models/pool                  # 模型池列表(已下载+本地扫描)
POST /manage/models/pool/:name/load       # 模型池一键加载
```

---

### AIClient2API (开源项目+GPU插件) - 端口 3000 (Docker部署)

**项目定位**: 开源AI客户端项目，自带Node.js后端，C端推理流量入口。内置GPU监控插件(gpu-monitor-switch)，注入UI脚本到管理面板。

**架构角色**: 用户界面层成员，与Vue 3 Frontend并列。Node后端通过provider配置(baseURL → go-vllm-api:35001)将推理请求路由到Go限流代理。

**两条路径**:
- **C端推理**: aiclient2api Node后端 → provider → go-vllm-api → 推理引擎
- **B端管控**: GPU插件 → Python B端(:35000) → 引擎/模型管理

---

### Go-Python交互机制

```
aiclient2api Node后端 → Go (provider配置):
  provider.baseURL = "http://go-vllm-api:35001"
  Node后端通过provider配置将推理请求路由到Go限流代理

Go → vLLM/SGLang (推理代理):
  /v1/chat/completions → VLLMProxy → 推理引擎(:8000) SSE流式转发

Python → 推理引擎 (进程管理):
  subprocess.Popen → vLLM/SGLang 进程启停/重启/健康检查
  3次自动重启 → 崩溃恢复兜底

Python → 模型 (下载/切换):
  MultiSourceModelHub → HuggingFace/ModelScope/OpenXLab 搜索+下载
  ModelSwitchOrchestrator → 4阶段原子切换(含回滚)

配置同步 (Python独立管理):
  config.yaml变更 → fsnotify检测 → _on_config_changed回调 → 服务更新
  SIGHUP信号 → reloadRuntimeConfig → 同上
```

---

## 数据流

```
B端管控流:
用户 → Vue Frontend / GPU插件 → Nginx(:30000)
    → /api/manage → Python(:35000)     # API轮询: 引擎启停/切换, 模型切换/下载, 显存校验
    → /ws          → Python(:35000)     # WebSocket服务端推送: GPU监控, 切换进度, 模型状态实时更新

C端推理流:
用户 → aiclient2api(:3000) → aiclient2api Node 后端
    → provider.baseURL → Go(:35001)     # 限流代理
    → /v1          → Go(:35001) → 推理引擎(:8000)  # SSE流式推理

Go(35001) → vLLM(:8000)                # 推理代理
Go(35001) → Python(35000)               # 切换操作代理
Python(35000) → 推理引擎(:8000)          # 进程管理(subprocess)

Redis(:6379) ← Go/Python                # 限流Key + 缓存数据
```

---

## 端口与技术栈

详见 [端口参考](../deployment/port-reference.md) 和 [编码约定](./conventions.md)。

---

## 架构风险与应对

### 流量层风险

| 风险 | 根因 | 现有防护 | 需完善 |
|------|------|----------|--------|
| SSE 长连接占满并发槽位 | 流式请求长期占slot，客户端断开goroutine不退出 | context绑定+defer释放+heartbeat 10s | 分级并发(普通/流式分开max); 流式最大30min超时; 僵尸连接5min清理 |
| 限流精度不足，大token打爆GPU | GPU负载与输入token强相关 | Redis IP QPS + Scheduler并发slot | 双维度限流(QPS+每分钟token); GPU>85%自适应降额; 超max_model_len前置拦截 |
| 上游引擎故障请求堆积 | 请求超时未释放持续堆积 | VLLMProxy 60s/120s timeout | 连续10失败触发熔断5s快速拒绝; 队列长度上限 |
| 客户端伪造IP绕过限流 | 仅X-Forwarded-For可伪造 | Gin ClientIP()取RemoteAddr; localhost白名单 | 可信代理优先级; 内网地址过滤防伪造白名单 |

### 配置层风险

| 风险 | 根因 | 现有防护 | 需完善 |
|------|------|----------|--------|
| Go/Python配置不一致 | Go离线时同步失败无重试 | fsnotify双向独立热加载 | 双向校验(修改后立即校验一致性); 指数退避重试1s/3s/10s; config version字段10s心跳校验 |
| 多管理员竞态覆盖 | 无分布式锁 | PUT全量覆盖 | 配置项粒度更新; 乐观锁version校验; 操作日志记录 |
| 非法配置致崩溃 | 配置无Schema校验 | YAML直接加载 | JSON Schema校验; 兜底默认值; 预加载测试再持久化 |

### 引擎层风险

| 风险 | 根因 | 现有防护 | 需完善 |
|------|------|----------|--------|
| 切换时请求丢失 | 旧引擎下线已有请求失败 | 4阶段原子切换; 503+retry_after中断期 | 优雅切换(30s优雅期); 非流式幂等重试 |
| 热切换显存泄漏 | unload_model不完全释放 | Phase2强制清理进程(kill+端口等待) | GPUMemoryChecker加载前显存校验(85%安全水位线) |
| 引擎崩溃无自动恢复 | 崩溃后无重启 | systemd托管vLLM | LLMServiceManager自动重启(3次→告警); subprocess进程守护 |
| 多引擎显存超额 | vLLM+SGLang同时启动 | 单实例模式(同一时间只1个vLLM) | LLMEngineScheduler显存预算控制; 启动前GPUMemoryChecker校验 |
| 跨引擎切换参数丢失 | vLLM/SGLang参数格式不同 | 仅支持vLLM参数 | 引擎类型→参数模板映射; config.yaml增加sglang_params |
| subprocess不如systemd稳定 | 进程管理依赖Python进程存活 | systemd独立守护 | 3次自动重启兜底; 可降级回systemd(config开关) |
| 引擎崩溃无自动恢复 | 崩溃后无重启 | systemd托管vLLM | B端每5s健康检查,3次失败告警+systemd自动重启 |
| 多引擎显存超额 | vLLM+SGLang同时启动 | 单实例模式(同一时间只1个vLLM) | 显存预算控制; 启动前校验总占用 |

### 高可用风险

| 风险 | 根因 | 现有防护 | 需完善 |
|------|------|----------|--------|
| 全链路单点故障 | Go/Python/引擎均为单点 | 单实例docker-compose | Go多实例+Nginx负载均衡; 引擎主备切换; 配置共享存储 |
| 无链路追踪 | 无统一ID串联 | RequestID中间件+Zap日志 | Request-ID透传引擎(header); 耗时埋点(转发/推理/排队); 对接OpenTelemetry |
| 突发流量无削峰 | 突发高并发直接透传GPU | Scheduler并发slot+排队WaitForSlot | 流量整形(令牌桶突发限制); GPU>90%拒低优先级 |

### 安全风险

| 风险 | 根因 | 现有防护 | 需完善 |
|------|------|----------|--------|
| B端接口无鉴权 | 未做登录权限 | CORS+IP限流+请求追踪 | JWT鉴权; RBAC角色; 操作审计日志 |
| 网关管理接口非法访问 | 仅localhost白名单 | localhost限流免白名单 | 管理接口IP白名单+内网限制; 修改接口仅本地回环 |

### 运维风险

| 风险 | 根因 | 现有防护 | 需完善 |
|------|------|----------|--------|
| 无统一监控告警 | 未对接Grafana | /metrics Prometheus端点; /health/detailed健康评分 | 对接Grafana dashboard; 告警规则(引擎离线/成功率/P99/GPU/磁盘) |
| 无自动化故障恢复 | 需人工介入 | systemd托管+优雅下线+切换回滚 | 自愈脚本(引擎崩溃重启; 配置不一致全量同步; 显存不足卸载空闲模型) |

> 详细PRD见 [prd.md](./prd.md) 第7节

---

> 更新于 2026-04-30
