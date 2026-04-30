# PRD: ai-os LLM 推理架构平台

> 产品需求文档 - Go 网关(C端流量) + Python B端(管控) + Vue3 前端

---

## 1. 基本信息

| 字段 | 值 |
|------|-----|
| **项目** | ai-os |
| **版本** | v1.0 |
| **状态** | 已实现 |
| **负责人** | - |

---

## 2. 产品概述

### 2.1 产品定位

**ai-os** 是一个多模块 AI 操作系统，管理 GPU 加速 LLM 推理服务的全生命周期。核心架构为 **Go 网关(C端流量入口) + Python B端(管控平台)**，通过 Nginx 统一路由，Docker Compose 一键部署。

### 2.2 目标用户

| 用户类型 | 使用场景 | 核心诉求 |
|----------|----------|----------|
| C端开发者/客户端 | 调用推理API | OpenAI兼容、低延迟、流式输出、稳定可靠 |
| 管理员/运维 | 后台管控 | 模型切换、GPU监控、配置管理、实时状态 |
| AI Agent用户 | 工具调用对话 | Agent循环、工具执行、流式响应 |

### 2.3 核心价值

1. **C端透明接入**: 兼容 OpenAI 协议，客户端无需修改代码
2. **B端全链路管控**: 4阶段原子切换+回滚+实时进度，零风险操作
3. **双后端解耦**: Go 专注流量(高性能)，Python 专注管理(灵活)，互不干扰
4. **一键部署**: Docker Compose 5服务编排，GPU直通，健康自检

---

## 3. 架构边界定义

| 项目 | 定位 | 访问端 | 核心职责 | 端口 |
|------|------|--------|----------|------|
| **Go 网关** | 高并发流量入口 | C端用户/客户端 | 协议转发、SSE流式、限流排队、并发控制、配置热加载 | 35001 |
| **Python B端** | 后台管控平台 | 管理员/运维 | 原子切换、配置管理、模型管理、GPU监控、WebSocket广播 | 35000 |
| **前端** | 管理界面 | 管理员/运维 | 仪表盘、模型管理、GPU监控、Agent对话、基准测试 | 30001/30000 |
| **aiclient2api** | API网关 | 外部客户端 | 转发+鉴权+流量控制 | 3000 |
| **Nginx** | 反向代理 | 所有 | 路由分发、SSE无缓冲、WebSocket长连接 | 80 |

---

## 4. 功能规格

### 4.1 Go 网关 (C端流量入口)

#### 功能点 1: OpenAI 协议转发

- **描述**: 兼容 OpenAI 官方 API 协议，客户端可通过标准 SDK 直接接入
- **优先级**: P0
- **验收标准**:
  - [ ] `GET /v1/models` 返回可用模型列表，含运行状态和路径校验
  - [ ] `POST /v1/chat/completions` 支持流式和非流式对话
  - [ ] `POST /v1/embeddings` 支持向量嵌入
  - [ ] `POST /v1/images/generations` 支持图片生成
  - [ ] 模型名 "default" 自动映射到当前默认模型
  - [ ] 多模态模型自动识别图片输入并校验

#### 功能点 2: SSE 流式处理

- **描述**: 长连接流式响应转发，防 goroutine 泄漏，防连接超时
- **优先级**: P0
- **验收标准**:
  - [ ] `stream=true` 时返回 `text/event-stream` 响应
  - [ ] 256缓冲 channel 读取，不阻塞 goroutine
  - [ ] 10秒无活动自动注入 heartbeat（`: heartbeat\n\n`）
  - [ ] 客户端断开自动退出流式循环（context cancel）
  - [ ] 流式结束发送 `[DONE]` 哨兵
  - [ ] 自动注入 `stream_options.include_usage` 解析 token 用量
  - [ ] Nginx 配置 `proxy_buffering off` + `X-Accel-Buffering: no`

#### 功能点 3: 限流排队

- **描述**: 多层级流量控制，保障推理服务稳定
- **优先级**: P0
- **验收标准**:
  - [ ] IP QPS 限流: Redis 计数器，60秒窗口，100次/窗口(可配置)
  - [ ] 并发 slot 控制: `AcquireRequest`/`ReleaseRequest`，超过并发上限返回 429
  - [ ] 排队等待: `WaitForSlot` 30秒超时，等待期间不拒绝
  - [ ] localhost/127.0.0.1 免限流
  - [ ] `/v1/chat/completions` 等4个推理路径限流，管理路径不限
  - [ ] 响应头 `X-RateLimit-Limit` / `X-RateLimit-Remaining`

#### 功能点 4: 模型自动调度

- **描述**: 请求到达时自动启动模型，确保可用性
- **优先级**: P0
- **验收标准**:
  - [ ] `ensureModelReady`: 模型未运行时自动调用 `StartModel`
  - [ ] `WaitUntilReady`: 启动后探针轮询（指数退避 2s→5s，最长 600s）
  - [ ] 模型切换中返回 503 + retry_after
  - [ ] 预加载模型: `PreloadModels` + `PreloadWatcherLoop` 保活
  - [ ] 默认模型: `GetDefaultModel`/`GetCurrentModelName` 兜底
  - [ ] `MarkModelSelected` 记录使用时间用于 keep-alive 决策

#### 功能点 5: 配置热加载

- **描述**: 运行时配置变更无需重启服务
- **优先级**: P1
- **验收标准**:
  - [ ] fsnotify 文件监听自动触发 `applyRuntimeConfig`
  - [ ] SIGHUP 信号触发 `reloadRuntimeConfig`
  - [ ] `POST /manage/config/reload` 手动触发
  - [ ] `PUT /manage/config` 直接更新配置并保存
  - [ ] 热加载覆盖: Scheduler + VLLMManager + LlamaCppManager

#### 功能点 6: Python 代理联动

- **描述**: Go 代理模型切换操作到 Python B端，保持架构边界清晰
- **优先级**: P1
- **验收标准**:
  - [ ] `proxyPythonManage()` 代理 `/manage/switch/atomic` 到 Python
  - [ ] `PYTHON_BACKEND_URL` 环境变量可配置 Python 地址
  - [ ] `broadcastStatusLoop` 每 2s 轮询 Python 切换状态转发给 Go WS 客户端
  - [ ] `/manage/models/aggregated` 代理到 Python 获取聚合模型信息

#### 功能点 7: 可观测性

- **描述**: 全面监控指标和健康检查
- **优先级**: P1
- **验收标准**:
  - [ ] `GET /health` 5秒缓存健康检查（status + health_score + current_model）
  - [ ] `GET /health/detailed` GPU + 指标 + 缓存分解详情
  - [ ] `GET /metrics` Prometheus 格式指标
  - [ ] RequestID 中间件自动生成 UUID
  - [ ] Zap 结构化日志记录每个请求（method/path/status/duration）

---

### 4.2 Python B端 (管控平台)

#### 功能点 8: 4阶段原子模型切换

- **描述**: 安全的模型切换流程，支持回滚和实时进度广播
- **优先级**: P0
- **验收标准**:
  - [ ] Phase 1: 停止旧服务（graceful shutdown）
  - [ ] Phase 2: 强制清理进程（确保端口释放）
  - [ ] Phase 3: 启动新服务（vLLM restart with 新模型路径）
  - [ ] Phase 4: 冒烟测试（readiness probe + 可选 benchmark）
  - [ ] 任意 Phase 失败触发回滚（恢复前模型）
  - [ ] UUID session 追踪，WebSocket 广播进度
  - [ ] 支持取消: `request_cancel()` 中断进行中的切换
  - [ ] 支持 3 种 action: switch / start / stop

#### 功能点 9: 配置管理

- **描述**: 版本控制、热更新、双向同步
- **优先级**: P0
- **验收标准**:
  - [ ] YAML 配置热加载: fsnotify + SIGHUP
  - [ ] `_on_config_changed` 回调清缓存+更新 Scheduler
  - [ ] `GET /manage/config` 读取当前配置
  - [ ] `PUT /manage/config` 更新并持久化配置
  - [ ] `POST /manage/config/reload` 手动触发重载

#### 功能点 10: 模型管理

- **描述**: 模型全生命周期管理
- **优先级**: P0
- **验收标准**:
  - [ ] 自动扫描 `/mnt/pve_models` 发现模型（config.json/tokenizer）
  - [ ] `GET /manage/models` 返回模型列表含运行状态
  - [ ] `GET /manage/models/aggregated` 返回聚合模型组（含 vllm_params/model_groups）
  - [ ] 模型 vLLM 参数配置读写（GPU利用率/最大长度/chunked prefill/attention backend/tool call parser）
  - [ ] 默认模型设置: `POST /manage/default-model/:name`
  - [ ] 预加载管理: enable/disable/keep-alive
  - [ ] 模型测试框架: benchmark + comparative analysis

#### 功能点 11: GPU 监控

- **描述**: 实时 GPU 状态采集和可视化
- **优先级**: P1
- **验收标准**:
  - [ ] NVML 直连采集 GPU 状态（利用率/温度/功耗/显存）
  - [ ] nvidia-smi CLI 解析补充信息
  - [ ] vLLM metrics 抓取（running/waiting requests, cache usage, TTFT/TPOT, throughput）
  - [ ] `GET /manage/gpu/enhanced` 增强信息（进程/PID/显存碎片）
  - [ ] `GET /manage/gpu/processes` GPU 进程列表
  - [ ] GPU 历史数据 5 秒间隔存储到 Redis
  - [ ] WebSocket 每 2s 广播 GPU summary + 模型状态

#### 功能点 12: WebSocket 实时通信

- **描述**: 实时状态推送，前端无需轮询
- **优先级**: P1
- **验收标准**:
  - [ ] `/ws/monitor` 频道: GPU summary + 模型状态 每 2s 广播
  - [ ] `/ws/model-switch` 频道: 切换进度 + session 详情实时推送
  - [ ] 新连接建立时立即推送当前状态（状态同步）
  - [ ] Nginx 配置 proxy_read_timeout 86400s

#### 功能点 13: Agent 系统

- **描述**: AI Agent 工具调用循环，支持流式对话
- **优先级**: P2
- **验收标准**:
  - [ ] OpenAI function schema 兼容的工具注册
  - [ ] Agent 循环: 检测 tool_calls → 执行工具 → 流式回传结果 → 重复直到无 tool_calls
  - [ ] SSE 流式: `tool_calls_start` / `tool_executing` / `tool_result` / `tool_calls_end` 事件
  - [ ] 工具类别: 模型管理、GPU监控、系统控制、vLLM管理
  - [ ] `POST /manage/agent/chat` 支持流式和非流式
  - [ ] 对话历史管理: 多会话+消息记录

#### 功能点 14: 多引擎支持 (vLLM + SGLang)

- **描述**: 统一管理 vLLM 和 SGLang 推理引擎，支持动态切换引擎类型
- **优先级**: P1
- **验收标准**:
  - [ ] LLMServiceManager 统一进程管理: subprocess.Popen 替代 systemd，支持 vLLM 和 SGLang 双引擎
  - [ ] SGLang 引擎启动/停止/重启: 命令行参数构造 + 进程生命周期管理
  - [ ] GPUMemoryChecker 显存检测: torch.cuda 精准查询可用显存，替代 nvidia-smi 估算
  - [ ] 模型加载前显存校验: required_memory vs 可用显存，不足时拒绝启动并告警
  - [ ] 动态引擎切换: vLLM ↔ SGLang 一键切换（卸载旧引擎 → 校验显存 → 启动新引擎）
  - [ ] 动态模型切换: 卸载旧模型 → 校验显存 → 加载新模型（跨引擎通用）
  - [ ] LLMEngineScheduler 统一调度: 整合 scheduler.py + model_switch_orchestrator.py + vllm_manager.py
  - [ ] 引擎状态查询: `GET /manage/engines/status` 返回各引擎类型运行状态

#### 功能点 15: 多源模型下载

- **描述**: 支持 3 大主流模型平台下载，国内无感加速，断点续传，下载完成自动入库并支持一键加载
- **优先级**: P1
- **验收标准**:
  - [ ] 支持 HuggingFace下载: `huggingface_hub.snapshot_download`，自动配置国内镜像 `hf-mirror.com`
  - [ ] 支持 ModelScope下载: `modelscope.snapshot_download`，无需代理，国内首选
  - [ ] 支持 OpenXLab下载: `openxlab.model.download`，商汤平台
  - [ ] 断点续传: 下载中断后重试自动续传（`resume_download=True`）
  - [ ] 下载进度追踪: WebSocket实时推送下载进度(百分比/速度/剩余时间/已下载大小)
  - [ ] 磁盘空间前置校验: 预估模型大小 vs 可用磁盘，85%水位告警/95%终止
  - [ ] 下载完成自动入库: 模型池 `model_pool` 自动注册，无需手动扫描
  - [ ] 下载后一键加载: 下载完成 → 显存校验 → LLMServiceManager 加载到引擎
  - [ ] `POST /manage/models/download` 启动下载任务（参数: model_name, source, save_dir可选）
  - [ ] `GET /manage/models/download/:task_id/status` 查询下载进度
  - [ ] `DELETE /manage/models/download/:task_id` 取消下载任务
  - [ ] `GET /manage/models/downloads` 列出所有下载任务（含历史）
  - [ ] WebSocket `/ws/download` 实时推送下载进度事件

#### 功能点 16: 跨平台模型搜索

- **描述**: 关键词一键搜索 HuggingFace/ModelScope/OpenXLab 全平台模型，自动解析参数和量化，返回估算显存
- **优先级**: P1
- **验收标准**:
  - [ ] HuggingFace搜索: `huggingface_hub.list_models(search=keyword, limit=20)`，返回模型ID+标签
  - [ ] ModelScope搜索: `Model.search(keyword, limit=20)`，默认首选(国内速度最快)
  - [ ] 自动解析模型参数: 从模型名提取参数大小(7B/8B/13B/72B/235B等)，映射为整数参数值
  - [ ] 自动解析量化类型: 从模型名提取量化(4bit/int4/8bit/int8/fp16/GGUF/AWQ/GPTQ)
  - [ ] 搜索结果含估算显存: `GPUMemoryManager.estimate_model_memory(size, quant)` 自动计算所需显存
  - [ ] 显存估算公式: 4bit=参数×0.7GB/8bit=参数×1.1GB/fp16=参数×2.0GB/GGUF按文件大小 + 1GB安全冗余
  - [ ] 搜索结果含显存可行性: 标注当前可用显存是否足够运行该模型(✅可运行/❌显存不足)
  - [ ] `GET /manage/models/search?keyword=xxx&source=modelscope&limit=20` 跨平台搜索
  - [ ] `GET /manage/models/search?keyword=xxx&source=all` 搜索全平台（聚合3个平台结果去重）
  - [ ] 搜索结果排序: 按模型大小/量化/显存需求/显存可行性可排序

#### 功能点 17: GPU 显存智能优选

- **描述**: 实时检测 GPU 可用显存，自动筛选可运行模型，智能排序推荐最优模型，一键下载加载
- **优先级**: P1
- **验收标准**:
  - [ ] `GPUMemoryManager.get_gpu_info()` 实时查询GPU显存(总/已用/可用)，优先torch.cuda精准检测，降级nvidia-smi
  - [ ] `GPUMemoryManager.estimate_model_memory()` 自动估算模型显存需求(参数×量化系数+1GB冗余)
  - [ ] 显存估算公式: 4bit=0.7倍/8bit=1.1倍/fp16=2.0倍 + 1GB安全冗余
  - [ ] `select_best_model()` 显存优选: 过滤可用显存不足模型 → 按模型大小降序 → 推荐最大可运行模型
  - [ ] 显存不足时拒绝启动并告警: 提示可用显存 + 建议可运行模型列表
  - [ ] 一键下载加载链路: 显存优选推荐 → 下载模型 → 显存校验 → 加载引擎 → 验证就绪
  - [ ] `POST /manage/gpu/memory-check/:model` 指定模型显存可行性校验
  - [ ] `GET /manage/gpu/recommend?keyword=xxx&source=modelscope` 显存优选推荐接口
  - [ ] 前端显存优选面板: 展示可用显存 → 推荐模型 → 一键下载加载

#### 功能点 18: 模型池统一管理

- **描述**: 搜索/下载的模型自动入库，与本地扫描模型统一管理，支持模型池查询和一键加载
- **优先级**: P1
- **验收标准**:
  - [ ] 模型自动入库: 下载完成自动注册到 `model_pool`，无需手动扫描
  - [ ] 搜索结果入库: 用户选择搜索结果时自动注册到 `model_pool`（含模型元信息）
  - [ ] 本地扫描入库: 现有 `/mnt/pve_models` 扫描结果自动同步到 `model_pool`
  - [ ] 模型池统一查询: `GET /manage/models/pool` 返回全部模型（含来源/大小/量化/显存/本地路径/下载状态）
  - [ ] 模型池一键加载: `POST /manage/models/pool/:model_key/load` 从模型池选择模型一键加载到引擎
  - [ ] 模型池删除: `DELETE /manage/models/pool/:model_key` 从模型池移除（可选删除本地文件）
  - [ ] 模型池与config.yaml双向同步: 模型池变更自动更新配置文件

---

### 4.3 前端 (管理界面)

#### 功能点 19: Dashboard 仪表盘

- **描述**: 一站式概览 GPU、模型、系统状态
- **优先级**: P1
- **验收标准**:
  - [ ] GPU 概览卡片（利用率/温度/功耗/显存）
  - [ ] 运行模型卡片（模型名/状态/端口/活跃请求）
  - [ ] 系统状态卡片（CPU/内存/磁盘）
  - [ ] 健康告警卡片（health_score + 降级状态）
  - [ ] 请求队列卡片（排队数/并发数/限制）
  - [ ] Token 使用卡片（prompt/completion/total）
  - [ ] vLLM 指标卡片（TTFT/TPOT/缓存命中率/吞吐量）

#### 功能点 20: 模型管理页

- **描述**: 模型启停、切换、预加载操作
- **优先级**: P0
- **验收标准**:
  - [ ] 模型列表展示（名称/状态/端口/配置/预加载标记）
  - [ ] 一键切换模型（触发 4 阶段原子切换）
  - [ ] 切换进度实时显示（WebSocket + 轮询回退）
  - [ ] 预加载开关（enable/disable/keep-alive）
  - [ ] 默认模型设置
  - [ ] 后端切换（Go/Python/Auto 三模式）

#### 功能点 21: GPU 监控详情页

- **描述**: GPU 详细监控和历史趋势图表
- **优先级**: P1
- **验收标准**:
  - [ ] 实时 GPU 指标折线图（Chart.js）
  - [ ] GPU 历史趋势图（利用率/温度/功耗/显存）
  - [ ] GPU 进程列表
  - [ ] vLLM 推理指标展示

#### 功能点 22: Agent 对话页

- **描述**: AI Agent 交互式对话
- **优先级**: P2
- **验收标准**:
  - [ ] 多会话管理（新建/切换/删除）
  - [ ] SSE 流式对话输出
  - [ ] 工具调用可视化（执行状态+结果展示）
  - [ ] Markdown 渲染（marked + highlight.js + dompurify）

---

## 5. 接口清单

### 5.1 C端推理接口 (Go :35001)

| 方法 | 路径 | 功能 | 流式 |
|------|------|------|------|
| GET | `/v1/models` | 模型列表 | - |
| GET | `/v1/models/:name` | 模型详情 | - |
| POST | `/v1/chat/completions` | 对话推理 | SSE |
| POST | `/v1/embeddings` | 向量嵌入 | - |
| POST | `/v1/images/validate` | 图片校验 | - |
| POST | `/v1/images/upload` | 图片上传 | - |
| GET | `/v1/images/info` | 图片服务信息 | - |
| POST | `/v1/images/generations` | 图片生成 | - |
| GET | `/v1/status` | API综合状态 | - |

### 5.2 管理接口 (Go :35001 / Python :35000 镜像)

| 方法 | 路径 | 功能 | 权威源 |
|------|------|------|--------|
| GET | `/manage/gpu` | GPU状态 | 双端 |
| GET | `/manage/gpu/summary` | GPU摘要 | 双端 |
| GET | `/manage/gpu/history` | GPU历史 | 双端 |
| GET | `/manage/gpu/enhanced` | GPU增强信息 | 双端 |
| GET | `/manage/gpu/processes` | GPU进程 | 双端 |
| GET | `/manage/models` | 模型列表 | 双端 |
| GET | `/manage/models/summary` | 模型摘要 | 双端 |
| GET | `/manage/models/aggregated` | 聚合模型 | **Python** |
| POST | `/manage/switch/atomic` | 原子切换 | **Python** |
| GET | `/manage/switch/status` | 切换进度 | **Python** |
| DELETE | `/manage/switch/cancel` | 取消切换 | **Python** |
| GET | `/manage/default-model` | 默认模型 | 双端 |
| POST | `/manage/default-model/:name` | 设置默认模型 | 双端 |
| GET | `/manage/queue` | 排队状态 | 双端 |
| GET | `/manage/preload` | 预加载列表 | 双端 |
| POST | `/manage/preload/:name` | 预加载模型 | 双端 |
| GET | `/manage/config` | 当前配置 | 双端 |
| PUT | `/manage/config` | 更新配置 | 双端 |
| POST | `/manage/config/reload` | 重载配置 | 双端 |
| GET | `/manage/service/status` | 服务状态 | 双端 |
| POST | `/manage/service/restart` | 重启服务 | 双端 |
| GET | `/manage/monitor/all` | 聚合仪表盘 | 双端 |
| GET | `/manage/metrics` | 指标数据 | 双端 |
| GET | `/manage/metrics/health-detail` | 健康详情 | 双端 |

### 5.3 Python 独有接口

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/manage/models/:name/vllm-config` | 模型 vLLM 配置读取 |
| PUT | `/manage/models/:name/vllm-config` | 模型 vLLM 配置写入 |
| GET | `/manage/models/:name/vllm-params` | 模型运行参数读取 |
| PUT | `/manage/models/:name/vllm-params` | 模型运行参数写入 |
| GET | `/manage/vllm/default-config` | 默认 vLLM 配置 |
| GET | `/manage/engines/status` | 各引擎类型运行状态(vLLM/SGLang/llama.cpp) |
| POST | `/manage/engines/switch` | 动态引擎切换(vLLM↔SGLang) |
| GET | `/manage/engines/config` | 引擎全局配置读取 |
| PUT | `/manage/engines/config` | 引擎全局配置写入 |
| GET | `/manage/gpu/memory-check` | 显存精准检测(torch.cuda) |
| POST | `/manage/gpu/memory-check/:model` | 指定模型显存可行性校验 |
| GET | `/manage/gpu/recommend?keyword=xxx&source=modelscope` | 显存优选推荐(自动筛选可运行模型) |

### 5.3b 模型搜索与下载接口 (Python 独有)

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/manage/models/search?keyword=xxx&source=modelscope&limit=20` | 跨平台模型搜索(HF/ModelScope/OpenXLab/all聚合) |
| GET | `/manage/gpu/recommend?keyword=xxx&source=modelscope` | 显存优选推荐(自动筛选可运行模型) |
| GET | `/manage/gpu/memory-check` | 显存精准检测(torch.cuda) |
| POST | `/manage/gpu/memory-check/:model` | 指定模型显存可行性校验 |
| POST | `/manage/models/download` | 启动模型下载任务(指定平台+模型名+保存目录) |
| GET | `/manage/models/download/:task_id/status` | 下载任务进度查询(百分比/速度/剩余时间) |
| DELETE | `/manage/models/download/:task_id` | 取消下载任务 |
| GET | `/manage/models/downloads` | 列出所有下载任务(含历史) |
| GET | `/manage/models/pool` | 模型池列表(已下载+本地扫描) |
| GET | `/manage/models/pool/:name` | 模型池单模型详情(含来源/显存估算/量化) |
| POST | `/manage/models/pool/:name/load` | 模型池模型一键加载(下载完成→显存校验→引擎加载) |
| DELETE | `/manage/models/pool/:name` | 从模型池删除模型(校验运行状态) |

### 5.4 WebSocket 接口

| 路径 | 功能 | 广播频率 |
|------|------|----------|
| `/ws/monitor` | GPU+模型实时状态 | 2秒 |
| `/ws/model-switch` | 切换进度实时推送 | 事件触发 |
| `/ws/download` | 下载进度实时推送(百分比/速度/剩余时间) | 事件触发 |

### 5.5 健康检查接口

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/health` | 基础健康检查(5秒缓存) |
| GET | `/health/detailed` | 详细健康(GPU+指标+缓存分解) |
| GET | `/metrics` | Prometheus 指标 |
| GET | `/metrics/metadata` | 指标元数据 |

### 5.6 Agent 接口

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/manage/agent/tools` | 工具列表 |
| GET | `/manage/agent/tools/:name` | 工具详情 |
| POST | `/manage/agent/execute` | 执行工具 |
| POST | `/manage/agent/execute/:name` | 执行指定工具 |
| POST | `/manage/agent/chat` | Agent对话(SSE流式) |
| GET | `/manage/agent/history` | 对话历史 |
| DELETE | `/manage/agent/history` | 清除历史 |

---

## 6. 非功能性需求

### 6.1 性能要求

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 推理首字节延迟(TTFT) | < 500ms | 含模型启动时间(已运行时) |
| SSE 心跳间隔 | 10秒 | 防连接超时 |
| WebSocket 广播频率 | 2秒 | GPU+模型状态 |
| 限流窗口 | 60秒/100请求 | IP QPS 默认值 |
| 并发 slot | 可配置 | config.yaml settings.max_concurrent |
| 健康检查缓存 | 5秒 | 避免频繁计算 |

### 6.2 可靠性要求

| 指标 | 实现 |
|------|------|
| 模型切换回滚 | 任意Phase失败自动恢复前模型 |
| 服务优雅下线 | SIGINT/SIGTERM → 10s graceful shutdown |
| 配置热加载 | fsnotify + SIGHUP 双通道 |
| 模型自动启动 | ensureModelReady + WaitUntilReady 探针 |
| Redis 故障降级 | Redis 不可用时限流放行，缓存跳过 |

### 6.3 部署要求

| 指标 | 实现 |
|------|------|
| 一键部署 | docker-compose up -d (5服务) |
| GPU 直通 | NVIDIA GPU docker capability |
| 健康自检 | curl /health (30s间隔) |
| 日志管理 | json-file driver, max-size 50m, max-file 5 |
| 配置持久化 | config.yaml 挂载宿主机 |
| 模型持久化 | /mnt/pve_models 挂载宿主机 |

### 6.4 模型下载与搜索要求

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 下载断点续传 | 支持 | resume_download=True，中断后自动续传 |
| 下载磁盘校验 | 85%/95%水位 | 85%告警，95%终止下载 |
| 国内下载速度 | ModelScope ≥10MB/s | 默认首选ModelScope，HF自动配置镜像 |
| 搜索响应时间 | <5s | 关键词搜索5条结果 |
| 显存估算精度 | 误差<10% | 参数×量化系数+1GB冗余 |
| 模型池入库延迟 | <1s | 下载完成后自动入库，无需手动 |
| 显存优选延迟 | <3s | 从搜索结果筛选+排序推荐 |

---

## 7. 全链路潜在问题与解决方案

基于 Go C端网关 + Python B端管理 + vLLM/SGLang 推理引擎的分层架构，从 7 个核心维度梳理全链路风险。

### 7.1 流量网关层（Go）

| # | 潜在问题 | 根因 | 现有实现 | 需完善方案 |
|---|----------|------|----------|------------|
| 1 | SSE 长连接占满并发槽位，goroutine 泄漏 | 流式请求长期占 slot；客户端断开时 goroutine 无 context 绑定不退出 | `context.WithCancel` 已绑定；`defer ReleaseRequest` 释放 slot；`gin.Stream` 退出循环 | **分级并发**: 普通/流式请求分开设 max；**超时兜底**: 流式最大30min；**僵尸巡检**: 清理空闲>5min连接 |
| 2 | 限流精度不足，大 token 请求打爆 GPU | GPU 负载与输入 token 强相关，单 QPS 限流无法保护 GPU | Redis IP QPS 限流(60s窗口) + Scheduler并发 slot | **双维度限流**: IP 维度同时限制 QPS + 每分钟总输入 token；**自适应限流**: GPU显存/利用率>85%自动降额；**前置拦截**: 输入超 max_model_len 直接拒绝 |
| 3 | 上游引擎故障请求堆积致网关 OOM | 请求超时未释放，持续堆积 | VLLMProxy 60s request timeout / 120s stream header timeout | **熔断**: 连续10请求失败触发熔断，5s快速拒绝；**队列长度限制**: max_queue_size 拒绝超额请求 |
| 4 | 客户端伪造 IP 绕过限流 | 仅用 `X-Forwarded-For`，可伪造 | `c.ClientIP()` Gin默认取 RemoteAddr，localhost/127.0.0.1/::1白名单 | **可信代理优先级**: RemoteAddr优先，配置可信代理段才读 X-Forwarded-For；**内网地址过滤**: 防伪造白名单IP |
| 5 | SSE 流式截断卡顿 | 反向代理默认缓冲 | Nginx `proxy_buffering off` + `X-Accel-Buffering: no` 已配置 | 已完善，无需额外修改 |

### 7.2 B端管理与配置同步层

| # | 潜在问题 | 根因 | 现有实现 | 需完善方案 |
|---|----------|------|----------|------------|
| 1 | Go/Python 配置不一致 | Go 离线时同步失败无重试 | fsnotify 双向独立热加载，无主动同步机制 | **双向校验**: 修改后立即调 Go `/manage/config` 校验一致性；**指数退避重试**: 1s/3s/10s 3次；**版本号**: config 增加 version 字段，10s心跳校验；**本地兜底**: Go 优先加载本地 config.yaml |
| 2 | 多管理员竞态覆盖配置 | 无分布式锁，后提交覆盖先提交 | `PUT /manage/config` 全量覆盖 | **配置项粒度更新**: 支持单字段修改；**乐观锁**: 校验 version 不匹配拒绝更新；**操作日志**: 记录操作人/时间/前后值 |
| 3 | 非法配置致服务崩溃 | 配置无校验，非法值直接写入 | YAML 加载无 Schema 校验 | **JSON Schema 校验**: 预设格式+取值范围校验；**兜底默认值**: 非法字段自动替换默认值；**预加载校验**: 先测试再持久化 |
| 4 | 配置热加载读写冲突 | 半加载状态致业务异常 | Go: `sync.RWMutex` 保护 Scheduler cfg；Python: 无显式锁 | Go 已有读写锁，完善原子替换机制 |

### 7.3 底层推理引擎层

| # | 潜在问题 | 根因 | 现有实现 | 需完善方案 |
|---|----------|------|----------|------------|
| 1 | 模型热切换请求丢失 | 切换时旧引擎下线，已有请求失败 | 4阶段原子切换(停止→清理→启动→验证)；503 + retry_after 中断期 | **优雅切换**: 给旧引擎30s优雅期；**失败重试**: 非流式请求幂等重试到新引擎 |
| 2 | 热切换显存泄漏 | vLLM unload_model 未完全释放显存 | Phase 2 强制清理进程(kill + 等待端口释放) | 进程级隔离已实现(vLLM单实例重启)，但需**显存校验**: 加载前检查剩余显存是否满足 |
| 3 | 引擎进程异常退出无自动恢复 | 崩溃后无重启 | systemd托管vLLM服务 | **健康检查**: B端每5s调用 `/health`，3次失败告警+自动重启(systemd已有) |
| 4 | 多引擎同时启动显存超额 | vLLM+SGLang同时占用超GPU上限 | 同一时间只运行一个vLLM实例(单实例模式) | **显存预算控制**: 启动前校验总显存占用；**互斥启动**: 当前已实现(单实例) |

### 7.4 模型管理与文件系统层

| # | 潜在问题 | 根因 | 现有实现 | 需完善方案 |
|---|----------|------|----------|------------|
| 1 | 正在使用的模型被误删 | 删除前未校验模型状态 | 无删除模型接口(仅启停/切换) | **状态强校验**: 若增加删除接口，必须校验运行状态；**软删除**: 标记待删除→引用释放→物理删除 |
| 2 | 大模型下载中断无法续传 | 下载工具未开断点续传 | 无模型下载功能(仅本地扫描) | **断点续传**: 若增加下载功能，设置 `resume_download=True`；**分片下载+进度持久化** |
| 3 | 模型下载致磁盘满 | 未校验磁盘剩余空间 | 无下载功能，仅扫描本地 | **前置空间校验**: 预估大小校验磁盘；**水位告警**: 85%告警/95%终止下载 |
| 4 | 模型扫描加载恶意文件 | 无文件类型校验 | ScanModels 仅识别 config.json/safetensors/tokenizer | 已白名单校验，补充：**取消执行权限**(模型目录 chmod -x)；**哈希校验**(若下载) |

### 7.5 全链路高可用

| # | 潜在问题 | 根因 | 现有实现 | 需完善方案 |
|---|----------|------|----------|------------|
| 1 | 全链路单点故障 | Go/Python/引擎均为单点部署 | 单实例 docker-compose | **网关集群**: Go多实例+Nginx负载均衡；**引擎主备**: 主备切换；**配置共享存储** |
| 2 | 无请求链路追踪 | 无统一 Request-ID 串联 | RequestID 中间件(UUUID) + Zap日志 | **全链路透传**: Request-ID 透传到引擎(Bearer header)；**耗时埋点**: 记录转发/推理/排队各环节耗时；**对接 OpenTelemetry** |
| 3 | 流量突增无削峰 | 突发高并发直接透传 GPU | Scheduler 并发 slot + WaitForSlot 排队 | **请求队列削峰**: 已实现排队机制；补充**流量整形**: 令牌桶突发限制；**过载保护**: GPU>90%拒低优先级 |

### 7.6 安全与权限

| # | 潜在问题 | 根因 | 现有实现 | 需完善方案 |
|---|----------|------|----------|------------|
| 1 | B端管理接口无鉴权 | 未做登录鉴权 | CORS + IP限流 + 请求追踪 | **JWT鉴权**: 管理员账号+JWT Token；**RBAC**: 超管/运维/只读角色；**操作审计日志** |
| 2 | Go 网关管理接口被非法访问 | 仅 localhost 白名单 | CORS全开 + localhost限流免白名单 | **双重鉴权**: 管理接口 IP白名单 + 内网限制；**读写分离**: 修改接口仅允许本地回环 |
| 3 | OpenAI 接口无鉴权 | 网关层无 API Key 校验 | 无鉴权中间件 | 根据需求决策，暂不实现(内网场景) |

### 7.7 运维与可观测性

| # | 潜在问题 | 根因 | 现有实现 | 需完善方案 |
|---|----------|------|----------|------------|
| 1 | 无统一监控告警 | 未对接 Prometheus+Grafana | `/metrics` Prometheus端点已存在；`/health/detailed` 健康评分 | **对接 Grafana**: 导入dashboard模板；**告警规则**: 引擎离线/成功率<99%/P99>5s/GPU>90%/磁盘>85% |
| 2 | 日志不规范 | 关键信息缺失 | Zap JSON结构化日志(RequestID/method/path/status/duration) | 已完善，补充：**日志轮转**: docker json-file driver已配置 |
| 3 | 无自动化故障恢复 | 需人工介入 | systemd托管+优雅下线+回滚 | **自愈脚本**: 引擎崩溃→自动重启(3次→告警)；配置不一致→自动全量同步；显存不足→卸载空闲模型 |

---

## 8. Python 统一引擎+模型管理重构计划

### 8.1 重构目标

将现有分散的引擎管理模块（`vllm_manager.py` + `sys_ctl.py` + `scheduler.py` + `model_switch_orchestrator.py`）重构为统一的 LLM 引擎管理体系，并新增多源模型下载、跨平台搜索、GPU 显存智能优选、模型池自动管理，实现从搜索→下载→显存优选→加载→推理的全流程自动化。

**核心链路**: 搜索模型 → 显存优选推荐 → 下载入库 → 一键加载 → vLLM/SGLang引擎推理

### 8.2 重构范围

| 现有模块 | 职责 | 重构去向 |
|----------|------|----------|
| `vllm_manager.py` | 模型扫描 + vLLM systemd 管理 | → `LLMServiceManager` (进程管理) + `ModelDiscovery`(模型扫描保留) |
| `sys_ctl.py` | systemd systemctl 调用 | → `LLMServiceManager` (subprocess.Popen 直接进程管理) |
| `scheduler.py` | YAML配置 + fsnotify + 排队 + 并发slot | → `LLMEngineScheduler` (统一调度入口) |
| `model_switch_orchestrator.py` | 4阶段原子切换 + session + WS广播 | → `LLMEngineScheduler.dynamic_switch()` (统一切换流程) |
| `gpu_monitor.py` | NVML + nvidia-smi GPU状态 | → 保留，新增 `GPUMemoryChecker` (显存精准检测补充) |
| *(全新增)* | 多源模型下载+搜索+模型池 | → `MultiSourceModelHub` (搜索+下载) + `ModelPoolManager` (模型池管理) |

### 8.3 新增模块设计

#### LLMServiceManager — 统一进程管理器

替代现有 systemd (`sys_ctl.py`) + vLLM启停 (`vllm_manager.py`)，改用 `subprocess.Popen` 直接管理引擎进程。

```python
class LLMServiceManager:
    """统一管理 vLLM / SGLang 进程生命周期"""

    def start_service(self, engine_type: str, model_path: str, port: int, params: dict) -> subprocess.Popen
    def stop_service(self, process: subprocess.Popen, timeout: int = 30) -> bool
    def restart_service(self, engine_type: str, model_path: str, port: int, params: dict) -> subprocess.Popen
    def get_service_status(self) -> dict  # {engine_type, pid, port, model, uptime, health}
    def build_command(self, engine_type: str, model_path: str, port: int, params: dict) -> list[str]

    # vLLM 命令构造
    # python -m vllm.entrypoints.openai.api_server --model <path> --port <port> ...
    # SGLang 命令构造
    # python -m sglang.launch_server --model-path <path> --port <port> ...
```

**关键特性**:
- `subprocess.Popen` 直接进程管理，不再依赖 systemd
- 进程 stdout/stderr 实时捕获，写入结构化日志
- 进程健康检查: HTTP readiness probe + PID 存活检测
- 进程异常退出自动重启: 3次重试 → 告警通知
- 优雅停止: SIGINT → 10s等待 → SIGKILL 强制终止

#### GPUMemoryChecker — 显存精准检测器

新增 `torch.cuda` 精准显存检测，补充现有 `gpu_monitor.py` 的 nvidia-smi 估算。

```python
class GPUMemoryChecker:
    """torch.cuda 精准显存检测，启动前安全校验"""

    def get_available_memory(self) -> float  # GB, torch.cuda.mem_get_info()
    def get_total_memory(self) -> float      # GB
    def check_model_feasibility(self, required_memory: float) -> dict
        # {feasible: bool, available: float, required: float, safety_margin: float}
    def get_memory_info(self) -> dict  # {total, used, free, utilization_pct}
```

**关键特性**:
- `torch.cuda.mem_get_info()` 精准查询（比 nvidia-smi 估算误差 <5%）
- 模型启动前校验: `required_memory < available * 0.85`（85%安全水位线）
- 校验失败拒绝启动，返回显存不足告警 + 建议可用模型
- torch.cuda 不可用时降级到 nvidia-smi 解析
- **增强: `estimate_model_memory()`**: 根据模型参数×量化系数自动估算所需显存
  - 4bit: 参数×0.7 + 1GB冗余, 8bit: 参数×1.1 + 1GB冗余, fp16: 参数×2.0 + 1GB冗余
- **增强: `select_best_model()`**: 从搜索结果中筛选显存可运行模型，按大小降序推荐最优

#### MultiSourceModelHub — 多源模型仓库管理器

新增跨平台模型搜索+下载，支持 3 大主流源（HuggingFace / ModelScope / OpenXLab）。

```python
class MultiSourceModelHub:
    """多源模型仓库: 搜索+下载+国内加速"""

    def search_models(self, keyword: str, source: str = "modelscope") -> list[dict]
        # 返回 [{name, source, path, size_b, quant, required_gb}]
        # HuggingFace: huggingface_hub.list_models(search=keyword)
        # ModelScope: Model.search(keyword)  (默认首选，国内最快)
        # OpenXLab: openxlab搜索
    def download_model(self, model_info: dict) -> str  # 返回本地路径
        # HF: snapshot_download (hf-mirror.com 国内镜像)
        # MS: ms_snapshot_download (无需代理)
        # OXL: oxl_model.download
    def _parse_size(self, name: str) -> int  # 从模型名提取参数(7B/8B/13B)
    def _parse_quant(self, name: str) -> str  # 从模型名提取量化(4bit/int4/8bit/fp16)
```

**关键特性**:
- 3大平台全覆盖: ModelScope默认首选(国内速度最快), HuggingFace自动配置国内镜像(`hf-mirror.com`)
- 自动解析模型参数大小和量化类型
- 断点续传下载（`resume_download=True`）
- 下载进度 WebSocket 实时推送
- 磁盘空间前置校验（85%水位告警/95%终止）

#### ModelPoolManager — 模型池自动管理器

统一管理已下载模型+本地扫描模型，自动入库和生命周期管理。

```python
class ModelPoolManager:
    """模型池: 已下载+本地扫描模型统一管理"""

    model_pool: dict[str, dict]  # {model_key → {path, source, size, quant, required_gb, status}}

    def add_to_pool(self, model_info: dict, local_path: str) -> str  # 入库
    def remove_from_pool(self, model_key: str) -> bool  # 移除(校验运行状态)
    def get_pool_list(self) -> list[dict]  # 模型池列表
    def get_pool_detail(self, model_key: str) -> dict  # 单模型详情
    def load_from_pool(self, model_key: str, engine: str) -> bool  # 一键加载
        # 显存校验 → LLMServiceManager启动 → readiness probe
    def auto_register_local(self) -> int  # 扫描/mnt/pve_models自动入库(合并现有ScanModels)
```

**关键特性**:
- 搜索/下载的模型自动入库，无需手动扫描
- 与本地扫描模型统一管理（合并 `vllm_manager.ScanModels`）
- 一键加载: `load_from_pool()` → 显存校验 → 引擎启动
- 删除前状态校验: 运行中模型不可删除

整合 `scheduler.py` + `model_switch_orchestrator.py` + `vllm_manager.py`，提供统一调度入口。

```python
class LLMEngineScheduler:
    """统一引擎调度: 配置加载 + 模型排队 + 切换编排 + 进程管理"""

    # 配置管理(继承 scheduler.py)
    def load_config(self, config_path: str) -> dict
    def apply_runtime_config(self, new_config: dict) -> None  # fsnotify/SIGHUP回调

    # 模型调度(继承 scheduler.py + vllm_manager.py)
    def ensure_model_ready(self, model_name: str) -> bool
    def get_current_model(self) -> str
    def set_default_model(self, model_name: str) -> None

    # 引擎切换(重构 model_switch_orchestrator.py)
    def dynamic_switch(self, target_model: str, target_engine: str = None) -> dict
        # 卸载旧模型 → GPUMemoryChecker校验 → LLMServiceManager启动新引擎 → 验证
    def dynamic_engine_switch(self, target_engine: str) -> dict
        # vLLM → SGLang 或 SGLang → vLLM，模型路径保持不变
    def cancel_switch(self) -> bool

    # 模型搜索与下载(新增)
    def search_models(self, keyword: str, source: str) -> list[dict]  # 跨平台搜索
    def select_best_model(self, keyword: str, source: str) -> dict     # 显存优选推荐
    def download_and_load(self, model_info: dict, engine: str) -> dict  # 下载+入库+加载

    # 并发控制(继承 scheduler.py)
    def acquire_slot(self) -> bool
    def release_slot(self) -> None
    def get_queue_status(self) -> dict
```

**关键特性**:
- 统一调度入口，消除 scheduler/vllm_manager/orchestrator 三模块职责重叠
- `dynamic_switch()`: 5阶段（停止旧引擎 → 清理 → 显存校验 → 启动新引擎 → 冒烟测试）
- `dynamic_engine_switch()`: 同模型跨引擎切换，仅替换引擎进程
- session 追踪 + WebSocket 进度广播（继承 orchestrator）
- 取消支持 + 回滚机制（继承 orchestrator）
- fsnotify + SIGHUP 配置热更新（继承 scheduler）
- **新增链路**: `search_models()` → `select_best_model()` → `download_and_load()` 全流程自动化

### 8.4 重构实施计划

| 阶段 | 内容 | 优先级 | 预估工期 |
|------|------|--------|----------|
| Phase 1 | 新增 `GPUMemoryChecker`（torch.cuda显存检测），与现有 `gpu_monitor.py` 并行运行 | P0 | 2天 |
| Phase 2 | 新增 `LLMServiceManager`（subprocess进程管理），先仅管理 vLLM，与现有 systemd 方案双轨并行验证 | P0 | 3天 |
| Phase 3 | 新增 SGLang 引擎支持：命令构造 + 启停 + readiness probe | P1 | 2天 |
| Phase 4 | 实现 `LLMEngineScheduler`，整合 scheduler + orchestrator + vllm_manager，统一调度入口 | P0 | 5天 |
| Phase 5 | 动态引擎切换: vLLM ↔ SGLang 一键切换 + 显存校验 + WebSocket进度 | P1 | 3天 |
| Phase 6 | 移除旧模块: sys_ctl.py / vllm_manager.py 的进程管理部分，保留模型扫描功能 | P2 | 1天 |
| Phase 7 | 前端适配: 引擎类型选择UI + 切换进度展示 + 显存校验提示 | P1 | 2天 |
| Phase 8 | 新增 `MultiSourceModelHub`: HuggingFace/ModelScope/OpenXLab搜索+下载，国内镜像加速 | P1 | 3天 |
| Phase 9 | 新增 `ModelPoolManager`: 模型池统一管理(自动入库+一键加载+状态校验) | P1 | 2天 |
| Phase 10 | 新增 `GPUMemoryManager`增强: estimate_model_memory + select_best_model 显存优选 | P1 | 2天 |
| Phase 11 | 前端搜索/下载/优选UI: 模型搜索面板 + 下载进度 + 显存优选推荐 + 模型池管理 | P2 | 3天 |

### 8.5 重构风险与兜底

| 风险 | 影响 | 兜底方案 |
|------|------|----------|
| subprocess.Popen 进程管理不如 systemd 稳定 | 引擎进程异常退出无守护 | 3次自动重启 → 告警；可降级回 systemd |
| torch.cuda 依赖冲突 | GPU检测模块无法加载 | 降级到 nvidia-smi 解析（<5%误差可接受） |
| SGLang 命令行参数与 vLLM 不兼容 | 引擎切换后参数丢失 | 引擎类型→参数模板映射，适配差异 |
| 重构期间新旧模块共存冲突 | 调度逻辑不一致 | 双轨并行验证期，新旧模块互斥（config开关） |
| HuggingFace国内访问不稳定 | 下载失败或超时 | 自动切换hf-mirror.com镜像；降级到ModelScope |
| 模型参数解析不准确 | 显存估算偏差致OOM或拒绝可用模型 | 保守估算(+1GB冗余)；支持手动覆盖required_memory |
| 下载中断无法续传 | 下载任务卡死 | resume_download=True断点续传；任务超时自动取消 |
| 磁盘满致下载崩溃 | 服务无响应 | 前置空间校验(85%告警/95%终止)；水位监控 |

### 8.6 引擎配置扩展

config.yaml 新增引擎类型配置：

```yaml
models:
  <model_name>:
    model_path: "/mnt/pve_models/Qwen2.5-7B-Instruct"
    engine_type: "vllm"              # 新增: "vllm" | "sglang" | "llama_cpp"
    port: 8000
    preload: false
    keep_alive: 300
    required_memory: 14
    vllm_params:                     # vLLM 专属参数
      gpu_memory_utilization: 0.90
      max_model_len: 8192
    sglang_params:                   # SGLang 专属参数(新增)
      mem_fraction_static: 0.88
      tp_size: 1

engines:                              # 新增: 引擎全局配置
  vllm:
    command: "python -m vllm.entrypoints.openai.api_server"
    default_params:
      gpu_memory_utilization: 0.90
      max_model_len: 8192
  sglang:
    command: "python -m sglang.launch_server"
    default_params:
      mem_fraction_static: 0.88
  llama_cpp:
    command: "./llama-server"
    default_params: {}
```

---

## 9. 数据模型

### 9.1 配置模型 (config.yaml)

```yaml
models:
  <model_name>:
    model_path: "/mnt/pve_models/Qwen2.5-7B-Instruct"
    service: "vllm-aiclient"          # 或 "llama_cpp"
    engine_type: "vllm"               # 新增: "vllm" | "sglang" | "llama_cpp"
    port: 8000                         # 推理端口
    preload: false                     # 是否预加载
    keep_alive: 300                    # 保活时间(秒)
    required_memory: 14                # 预估显存(GB)
    description: "Qwen2.5 7B Instruct"
    supports_images: false
    vllm_params:                       # vLLM 专属参数
      gpu_memory_utilization: 0.90
      max_model_len: 8192
      chunked_prefill_enabled: true
    sglang_params:                     # SGLang 专属参数(新增)
      mem_fraction_static: 0.88
      tp_size: 1

engines:                              # 引擎全局配置(新增)
  vllm:
    command: "python -m vllm.entrypoints.openai.api_server"
    default_params:
      gpu_memory_utilization: 0.90
      max_model_len: 8192
  sglang:
    command: "python -m sglang.launch_server"
    default_params:
      mem_fraction_static: 0.88
  llama_cpp:
    command: "./llama-server"
    default_params: {}

settings:
  max_concurrent: 100
  request_timeout: 60
  redis:
    host: "redis"
    port: 6379
    db: 0
  queue:
    enabled: true
    max_wait_time: 30

vllm:
  service_name: "vllm-aiclient"
  model_base_path: "/mnt/pve_models"
  default_gpu_utilization: 0.90

model_groups:                           # Python独有
  qwen2_5:
    pattern: "Qwen2\\.5-.*"
    description: "Qwen 2.5 系列"

discovery:
  auto_discover: true
  priority: "scan_first"
```

### 9.2 核心运行时状态

```
runningModels: map[model_name → start_time]
runningEngine: string                    # 新增: 当前引擎类型 "vllm" | "sglang" | "llama_cpp"
engineProcesses: map[engine_type → PID]  # 新增: 引擎进程PID映射
preloaded: set[model_name]
modelLastUsed: map[model_name → last_used_time]
currentModel: string
defaultModel: string
switchingInProgress: bool
```

### 9.3 切换 Session (Python)

```json
{
  "session_id": "uuid",
  "target_model": "Qwen2.5-72B-Instruct",
  "previous_model": "Qwen2.5-7B-Instruct",
  "target_engine": "vllm",
  "previous_engine": "vllm",
  "action": "switch",
  "overall_phase": "phase3",
  "phases": [
    {"phase": 1, "name": "停止旧服务", "status": "success", "progress": 100},
    {"phase": 2, "name": "强制清理进程", "status": "success", "progress": 100},
    {"phase": 2.5, "name": "显存校验", "status": "success", "progress": 100},
    {"phase": 3, "name": "启动新服务", "status": "running", "progress": 60},
    {"phase": 4, "name": "冒烟测试", "status": "pending", "progress": 0}
  ],
  "memory_check": {
    "required_memory": 28.0,
    "available_memory": 40.2,
    "feasible": true,
    "safety_margin": 12.2
  },
  "completed_successfully": false
}
```

### 9.4 模型池 (ModelPool)

```json
{
  "qwen2_5_7b_instruct": {
    "name": "Qwen2.5-7B-Instruct",
    "path": "/mnt/pve_models/Qwen2.5-7B-Instruct",
    "source": "local",
    "size_b": 7,
    "quant": "fp16",
    "required_gb": 15.0,
    "engine_type": "vllm",
    "status": "running",
    "download_time": null
  },
  "deepseek_6b_int4": {
    "name": "deepseek-ai/DeepSeek-R1-Distill-Qwen-6B-4bit",
    "path": "./models/deepseek-ai_DeepSeek-R1-Distill-Qwen-6B-4bit",
    "source": "modelscope",
    "size_b": 6,
    "quant": "4bit",
    "required_gb": 5.2,
    "engine_type": null,
    "status": "available",
    "download_time": "2026-04-30T10:30:00Z"
  }
}
```

### 9.5 下载任务 (DownloadTask)

```json
{
  "task_id": "uuid",
  "model_name": "Qwen2.5-72B-Instruct",
  "source": "modelscope",
  "status": "downloading",
  "progress_pct": 45.2,
  "download_speed": "12.5MB/s",
  "estimated_remaining": "3min 20s",
  "local_path": "./models/Qwen2.5-72B-Instruct",
  "created_at": "2026-04-30T10:00:00Z",
  "error": null,
  "resume_download": true,
  "disk_check": {
    "required_space": 28.0,
    "available_space": 45.2,
    "feasible": true
  }
}
```

### 9.6 搜索结果 (SearchResult)

```json
{
  "keyword": "qwen 4bit",
  "source": "modelscope",
  "total": 5,
  "models": [
    {
      "name": "Qwen2.5-7B-Instruct-4bit",
      "source": "ms",
      "path": "qwen/Qwen2.5-7B-Instruct-4bit",
      "size_b": 7,
      "quant": "4bit",
      "required_gb": 5.9,
      "fits_gpu": true
    }
  ],
  "gpu_info": {
    "total": 24.0,
    "free": 18.5,
    "recommended": "Qwen2.5-7B-Instruct-4bit"
  }
}
```

---

## 10. 技术栈

| 层 | 技术 | 版本 |
|----|------|------|
| 前端 | Vue 3 + TypeScript + Vite | Vite 6 |
| 前端样式 | Tailwind CSS v4 | via @tailwindcss/vite |
| 前端图表 | chart.js + vue-chartjs | - |
| 前端状态 | Pinia | - |
| Go 后端 | Gin | ReleaseMode |
| Go 日志 | Zap | 结构化 |
| Go Redis | go-redis/v9 | - |
| Go GPU | NVIDIA/go-nvml | - |
| Python 后端 | FastAPI + uvicorn | - |
| Python GPU | pynvml | - |
| Python 显存检测 | torch.cuda | GPU显存精准检测 |
| Python 模型下载(HF) | huggingface-hub | 国内镜像 hf-mirror.com |
| Python 模型下载(MS) | modelscope | 默认首选，国内最快 |
| Python 模型下载(OXL) | openxlab | 商汤平台 |
| Python HTTP | httpx | AsyncClient |
| 缓存 | Redis | 7.2-alpine |
| 反向代理 | Nginx | - |
| 部署 | Docker Compose | bridge network |

---

## 11. 全量功能验收细则

### 前置验收条件

1. 全链路服务正常启动：Go 网关(:35001)、Python B端(:35000)、vLLM 引擎(:8000)、前端页面(:30000)
2. 测试环境 GPU、磁盘、网络资源充足，无硬件瓶颈
3. 准备好测试用的小尺寸开源模型（如 Qwen2-7B-Instruct），可正常加载
4. 准备好压测工具（wrk / k6 / Postman）、OpenAI SDK 测试脚本

### 11.1 核心功能验收

#### OpenAI 协议转发功能验收

| 验收项 | 操作步骤 | 预期结果 | 状态 |
|--------|----------|----------|------|
| 非流式对话转发 | OpenAI SDK 连 Go:35001，`stream=false` 发送对话请求 | 响应符合 OpenAI 协议规范；引擎推理日志正常；内容与直连引擎一致 | [ ] |
| 流式对话转发 | OpenAI SDK `stream=true` 发送请求，监听流式响应 | 逐字返回无卡顿截断；SSE 格式规范；客户端断开时引擎自动终止无泄漏 | [ ] |
| 模型列表接口 | 调用 `/v1/models` | 返回模型列表与引擎一致；格式符合 OpenAI 规范 | [ ] |
| 模型自动启动 | 调用未运行模型的 `/v1/chat/completions` | 模型自动启动；readiness探针通过后返回推理结果 | [ ] |
| 默认模型映射 | `model=""` 或 `model="default"` 发送请求 | 自动映射到当前默认模型，正常推理 | [ ] |

#### 限流功能验收

| 验收项 | 操作步骤 | 预期结果 | 状态 |
|--------|----------|----------|------|
| IP QPS 限流 | 配置限流阈值，非白名单IP超阈值发送请求 | 超限请求返回 429；正常放行请求正常返回 | [ ] |
| 全局并发限流 | 配置 `max_concurrent`，同时发起超额并发流式连接 | 超限连接排队或返回 429；释放 slot 后新连接可建立 | [ ] |
| 白名单免限流 | 白名单IP(127.0.0.1)超阈值发送请求 | 全部正常放行，无 429 | [ ] |
| 限流响应头 | 被限流请求检查响应头 | 包含 `X-RateLimit-Limit` / `X-RateLimit-Remaining` | [ ] |

#### 原子模型切换验收

| 验收项 | 操作步骤 | 预期结果 | 状态 |
|--------|----------|----------|------|
| 模型热切换 | 引擎加载模型A，前端选择切换模型B，持续发送请求 | 4阶段执行成功；模型A卸载→模型B加载→验证通过；切换后推理正常 | [ ] |
| 切换进度实时显示 | 切换过程中观察前端 WebSocket 进度 | 进度实时更新（Phase1→Phase2→Phase3→Phase4）；百分比准确 | [ ] |
| 切换失败回滚 | 切换过程中手动制造失败(如指定不存在模型) | 自动回滚到原模型；引擎恢复正常推理 | [ ] |
| 切换取消 | 切换进行中点击取消 | 切换中断；引擎恢复原模型状态 | [ ] |
| 切换中请求处理 | 切换过程中持续发送推理请求 | 切换中请求返回 503 + retry_after；切换完成后自动恢复 | [ ] |

#### 配置管理与同步验收

| 验收项 | 操作步骤 | 预期结果 | 状态 |
|--------|----------|----------|------|
| 配置修改生效 | 前端修改限流配置并提交 | Python config.yaml 更新；Go 运行时配置热加载生效；限流规则按新配置执行 | [ ] |
| 配置热重载 | 手动修改 config.yaml，前端点击重载配置 | 运行时配置更新；服务无需重启；Go/Python 双端一致 | [ ] |
| 非法配置拦截 | 提交非法配置(如负数并发) | 返回校验失败提示；原有配置不被修改；服务运行无异常 | [ ] |
| 配置同步失败兜底 | 关闭 Go 网关，Python修改配置后重启 Go | Python 本地配置正常保存；Go 重启后自动加载本地 config.yaml | [ ] |

#### GPU 监控验收

| 验收项 | 操作步骤 | 预期结果 | 状态 |
|--------|----------|----------|------|
| GPU 实时状态 | 查看 `/manage/gpu/summary` | GPU 利用率/温度/功耗/显存准确显示 | [ ] |
| GPU 历史数据 | 查看 `/manage/gpu/history` | 5秒间隔历史数据正确；趋势图正常渲染 | [ ] |
| vLLM 指标 | 查看 `/manage/vllm/metrics` | TTFT/TPOT/缓存命中率/吞吐量/排队请求正确 | [ ] |
| WebSocket 广播 | 连接 `/ws/monitor` 观察 | 每 2s 广播 GPU + 模型状态；数据准确 | [ ] |

### 11.2 性能验收

| 验收项 | 测试条件 | 验收标准 | 状态 |
|--------|----------|----------|------|
| 转发性能损耗 | 单GPU固定模型固定并发，对比直连vs网关转发 | QPS 差异≤5%；P99延迟增加≤10ms | [ ] |
| 高并发稳定性 | 100并发持续压测30min | 无崩溃OOM goroutine泄漏；内存波动≤20%；成功率100% | [ ] |
| 长连接稳定性 | 100并发流式长连接，每连接1000token，持续1h | 无异常断开卡顿截断；内存稳定无泄漏；显存稳定 | [ ] |
| 限流性能 | 1000请求/秒持续压测 | 限流规则准确执行；网关CPU≤2核；被限流请求快速响应 | [ ] |

### 11.3 稳定性与故障恢复验收

| 验收项 | 测试步骤 | 验收标准 | 状态 |
|--------|----------|----------|------|
| 引擎故障自愈 | kill vLLM进程→观察状态→等待systemd自动重启 | 网关快速返回错误无堆积；systemd自动重启；重启后网关自动恢复转发；恢复时间≤30s | [ ] |
| 磁盘满防护 | 模型目录磁盘99%满→提交下载任务(若实现) | 下载任务终止返回错误；服务无崩溃；系统盘无影响 | [ ] |
| 长时间运行 | 7x24h持续运行有流量 | 无崩溃内存泄漏；成功率≥99.9%；无配置不一致 | [ ] |
| 优雅下线 | 发送SIGTERM给Go网关 | 10s内完成 graceful shutdown；已有请求处理完成；无强制中断 | [ ] |

### 11.4 安全验收

| 验收项 | 验收标准 | 状态 |
|--------|----------|------|
| 管理接口访问控制 | 管理接口通过 Nginx 路由隔离；非白名单IP限流拦截 | [ ] |
| 输入安全 | 所有接口输入参数有校验；无 SQL 注入/路径遍历漏洞 | [ ] |
| 文件权限 | 模型文件无全局读写权限；模型目录无执行权限 | [ ] |
| 日志追溯 | 所有操作日志完整留存；Request-ID 全链路可追溯 | [ ] |

---

## 12. 上线计划

### 12.1 部署步骤

1. `docker-compose up -d` 启动 5 服务
2. 等待 Redis healthy + ai-controller healthy
3. 验证: `curl http://localhost:35001/health` / `curl http://localhost:35000/health`
4. 验证: `curl http://localhost:35001/v1/models`
5. 前端: `http://localhost:30000`

### 12.2 回滚方案

1. `docker-compose down` 停止所有服务
2. 模型切换回滚: ModelSwitchOrchestrator 自动恢复前模型
3. 配置回滚: 还原 config.yaml → SIGHUP 信号重载
4. 单服务回滚: `docker-compose restart <service_name>`

---

## 13. 上线前最终验收 Checklist

- [ ] 全链路功能验收全部通过，无阻塞性 bug
- [ ] 性能压测达标，无性能瓶颈
- [ ] 故障恢复演练全部通过，自愈能力符合预期
- [ ] 监控告警体系搭建完成，核心指标有监控和告警
- [ ] 日志体系完善，Request-ID 全链路可追溯
- [ ] 安全合规验收通过，无高危安全漏洞
- [ ] 配置备份机制完善，可快速回滚
- [ ] 生产环境资源充足，GPU、磁盘、带宽符合业务需求
- [ ] 应急预案完善，运维人员熟悉故障处理流程

---

## 14. 附录

### 14.1 相关文档

- [架构设计](./architecture.md)
- [编码约定](./conventions.md)
- [端口参考](../deployment/port-reference.md)
- [部署指南](../deployment/deployment-guide.md)

### 14.2 历史记录

| 日期 | 版本 | 变更说明 |
|------|------|----------|
| 2026-04-30 | v1.0 | 基于现有代码完善 PRD |
| 2026-04-30 | v1.1 | 增加全链路潜在问题(7维度)、全量验收细则(4类)、上线Checklist |
| 2026-04-30 | v1.2 | 新增第8节重构计划(LLMServiceManager/GPUMemoryChecker/LLMEngineScheduler)；增加多引擎支持功能点(14)、引擎接口(5.3)、引擎配置(9.1)；更新切换Session增加显存校验阶段 |
| 2026-04-30 | v1.3 | 新增功能点15-17(多源下载/搜索/显存优选)；新增5.3b搜索下载接口(8条)；新增9.4-9.6数据模型(模型池/下载任务/搜索结果)；更新第8节融入MultiSourceModelHub+ModelPoolManager+GPUMemoryManager增强；新增6.4下载搜索要求；技术栈增加HF/MS/OXL依赖 |
| 2026-04-30 | v1.3 | 完善功能点15-17验收标准（多源下载进度追踪、跨平台搜索+显存估算、GPU显存智能优选+一键下载加载链路）；新增功能点18模型池统一管理；新增第9节数据模型扩展（ModelPool/DownloadTask/SearchResult）；新增接口5.7模型下载+搜索+显存优选+模型池系列接口 |

---

> 此文档为 ai-os 平台产品需求定义
