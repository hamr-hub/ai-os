# AI Controller 技术方案文档

## 1. 需求分析

根据业务需求，系统需要实现以下核心功能：

| 需求点 | 描述 | 优先级 | 来源 |
|--------|------|--------|------|
| 模型热切换 | 支持秒级模型切换，引入预加载/常驻策略 | 高 | 用户需求 |
| 显存碎片回收 | 通过 vLLM API 参数动态调整显存利用率 | 高 | 用户需求 |
| Redis 队列 | 实现流量削峰的并发控制 | 高 | 用户需求 |
| WebSocket 监控 | 实时推送 GPU 状态到前端 | 高 | 用户需求 |

## 2. 当前架构分析

### 2.1 系统架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                        API Gateway (FastAPI)                        │
├──────────────┬──────────────┬──────────────┬───────────────────────┤
│  /v1/chat/   │ /manage/     │ /ws/monitor  │   Middleware          │
│  completions │ models/queue │ (WebSocket)  │ (RateLimit, Timeout)  │
└──────────────┴──────────────┴──────────────┴──────────┬────────────┘
                                                       │
          ┌─────────────────────────────────────────────┼─────────────────────┐
          ▼                                             ▼                     ▼
┌───────────────────┐                     ┌───────────────────┐   ┌─────────────────┐
│   Scheduler       │                     │   GPUMonitor      │   │ ConfigWatcher   │
│  (模型调度器)      │                     │   (GPU监控)        │   │ (配置热更新)     │
├───────────────────┤                     ├───────────────────┤   └─────────────────┘
│ • 预加载策略      │                     │ • nvidia-smi解析  │
│ • 模型热切换      │                     │ • 显存使用监控    │
│ • 空闲超时管理    │                     │ • GPU状态采集    │
└─────────┬────────┘                     └────────┬──────────┘
          │                                       │
          ▼                                       ▼
┌───────────────────┐                     ┌───────────────────┐
│   RateLimiter     │                     │   SystemController│
│  (Redis队列)       │                     │   (系统控制)        │
├───────────────────┤                     ├───────────────────┤
│ • 并发控制        │                     │ • systemctl管理  │
│ • 任务队列        │                     │ • 服务启停        │
│ • 请求状态追踪    │                     │ • 进程监控        │
└───────────────────┘                     └───────────────────┘
          │
          ▼
┌───────────────────┐
│     Redis         │
│   (队列存储)       │
└───────────────────┘
```

### 2.2 核心组件职责

| 组件 | 职责 | 关键方法 | 文件位置 |
|------|------|----------|----------|
| **Scheduler** | 模型调度与热切换 | `start_model`, `switch_model`, `_preload_model` | `core/scheduler.py` |
| **GPUMonitor** | GPU状态监控 | `get_gpu_status`, `get_memory_usage` | `core/monitor.py` |
| **RateLimiter** | 流量控制与队列管理 | `enqueue_request`, `dequeue_request`, `is_available` | `core/rate_limiter.py` |
| **SystemController** | 系统服务管理 | `start_service`, `stop_service`, `is_service_running` | `core/sys_ctl.py` |
| **VLLMProxy** | vLLM API代理 | `chat_completion`, `optimize_memory`, `flush_cache` | `api/proxy_vllm.py` |
| **WebSocketManager** | WebSocket连接管理 | `connect`, `disconnect`, `broadcast` | `core/websocket_manager.py` |
| **MetricsCollector** | 指标收集 | `record_request`, `get_metrics`, `get_health_score` | `core/metrics.py` |
| **ConfigWatcher** | 配置热更新 | `load_config`, `start_watching`, `_notify_callbacks` | `core/config_watcher.py` |

### 2.3 数据流分析

**请求处理流程：**
```
客户端请求 → RateLimitMiddleware → TimeoutMiddleware → API Handler
                                              │
                                              ▼
                                   Scheduler.acquire_request()
                                              │
                                  ┌───────────┴───────────┐
                                  ▼                       ▼
                            模型已运行?               模型未运行
                                  │                       │
                                  ▼                       ▼
                            直接转发请求          start_model()
                                  │                       │
                                  └───────────┬───────────┘
                                              ▼
                                   VLLMProxy.chat_completion()
                                              │
                                              ▼
                                   Scheduler.release_request()
                                              │
                                              ▼
                                    返回响应给客户端
```

**WebSocket监控流程：**
```
客户端连接 → WebSocketManager.connect()
                 │
                 ▼
        broadcast_status_loop() (定时任务, 每秒)
                 │
                 ├── GPUMonitor.get_gpu_status()
                 ├── Scheduler.get_model_status()
                 └── RateLimiter.get_all_queue_status()
                 │
                 ▼
        WebSocketManager.broadcast()
                 │
                 ▼
            所有连接客户端
```

## 3. 可行方案对比

### 3.1 模型热切换方案

| 方案 | 实现方式 | 优势 | 劣势 | 适用场景 |
|------|----------|------|------|----------|
| **方案A: 预加载常驻** | 启动时预加载指定模型，持续运行 | 秒级响应，无启动延迟 | 显存占用高 | 高频访问模型 |
| **方案B: 按需启动** | 请求时启动，空闲超时停止 | 显存占用低 | 首次请求延迟高 | 低频访问模型 |
| **方案C: 混合策略** | 部分模型预加载，部分按需启动 | 平衡响应速度与显存 | 配置复杂 | 混合访问模式 |

**当前实现：方案C（混合策略）**

### 3.2 显存管理方案

| 方案 | 实现方式 | 优势 | 劣势 |
|------|----------|------|------|
| **方案A: 静态配置** | 固定显存利用率参数 | 简单稳定 | 无法动态调整 |
| **方案B: 动态调整** | 根据负载实时调整 | 资源利用率高 | 复杂度高 |
| **方案C: 定时优化** | 定期执行缓存清理 | 平衡稳定性与效率 | 响应不够及时 |

**当前实现：方案B + 方案C（动态调整 + 定时优化）**

### 3.3 队列实现方案

| 方案 | 实现方式 | 优势 | 劣势 |
|------|----------|------|------|
| **方案A: Redis List** | 使用Redis列表实现FIFO队列 | 简单高效，持久化 | 需要Redis依赖 |
| **方案B: 内存队列** | 使用Python队列实现 | 无外部依赖 | 不持久化，重启丢失 |
| **方案C: 优先级队列** | 支持任务优先级 | 灵活调度 | 复杂度高 |

**当前实现：方案A（Redis List）**

### 3.4 WebSocket推送方案

| 方案 | 实现方式 | 优势 | 劣势 |
|------|----------|------|------|
| **方案A: 定时广播** | 固定间隔推送状态 | 实现简单 | 可能有无效推送 |
| **方案B: 事件驱动** | 状态变化时推送 | 精准推送 | 需要事件机制 |
| **方案C: 按需订阅** | 客户端订阅感兴趣的事件 | 带宽友好 | 复杂度高 |

**当前实现：方案A（定时广播，每秒）**

## 4. 当前实现细节

### 4.1 模型热切换实现

```python
# 核心机制：
1. 预加载机制：服务启动时自动加载 preload=true 的模型
2. 热切换机制：switch_model() 自动释放空闲模型显存并启动目标模型
3. 空闲超时：release_request() 触发 _check_idle_timeout() 检查空闲时间
4. 常驻保护：keep_alive=true 的模型不会因空闲超时停止
```

**配置示例：**
```yaml
models:
  gemma-2-9b:
    service: vllm-gemma
    port: 8000
    required_memory: 12GB
    preload: true      # 启动时预加载
    keep_alive: true   # 持续运行不停止
```

### 4.2 显存碎片回收实现

```python
# 核心方法：
1. flush_cache(): 清除vLLM缓存
2. set_gpu_memory_utilization(): 设置显存利用率(0.8-0.95)
3. optimize_memory(): 根据策略自动优化
   - conservative: 0.8 (保守模式)
   - balanced: 0.9 (平衡模式)
   - aggressive: 0.95 (激进模式)
```

### 4.3 Redis队列实现

```python
# 核心数据结构：
1. active_requests:{model}: 当前活跃请求数 (Counter)
2. queue:{model}: 等待队列 (List)
3. request:{request_id}: 请求详情 (Hash/String)

# 队列操作：
1. enqueue_request(): 入队，返回request_id
2. dequeue_request(): 出队，获取请求详情
3. cancel_request(): 取消排队中的请求
4. get_request_status(): 查询请求状态
```

### 4.4 WebSocket监控实现

```python
# 推送数据结构：
{
    "type": "status_update",
    "timestamp": "2024-01-01T12:00:00",
    "gpu": {
        "status": "available",
        "gpu_count": 1,
        "primary": {
            "name": "NVIDIA RTX 4090",
            "total_memory": 24GB,
            "used_memory": 12GB,
            "available_memory": 12GB,
            "temperature": 65,
            "utilization": 80
        }
    },
    "models": {
        "gemma-2-9b": {"running": true, "port": 8000, "active_requests": 2},
        "llama-3-8b": {"running": false, "port": 8001, "active_requests": 0}
    },
    "queue": {
        "gemma-2-9b": {"active_requests": 2, "queue_length": 0},
        "llama-3-8b": {"active_requests": 0, "queue_length": 3}
    }
}
```

## 5. 优化建议

### 5.1 架构优化

| 优化点 | 当前状态 | 建议方案 | 预期收益 |
|--------|----------|----------|----------|
| **模型预热** | 仅支持启动时预加载 | 添加动态预热接口 | 支持运行时预热 |
| **智能调度** | 固定并发限制 | 基于显存动态调整 | 提高资源利用率 |
| **优雅降级** | 直接拒绝请求 | 队列缓冲 + 超时 | 提升用户体验 |
| **分布式部署** | 单体部署 | 多节点负载均衡 | 高可用扩展 |

### 5.2 性能优化

| 优化点 | 当前状态 | 建议方案 | 预期收益 |
|--------|----------|----------|----------|
| **缓存策略** | 无请求缓存 | 添加响应缓存 | 降低重复计算 |
| **连接池** | 每次创建连接 | 使用HTTP连接池 | 减少连接开销 |
| **异步处理** | 部分异步 | 全链路异步 | 提高吞吐量 |

### 5.3 可观测性优化

| 优化点 | 当前状态 | 建议方案 | 预期收益 |
|--------|----------|----------|----------|
| **指标采集** | 基础指标 | 添加Prometheus导出 | 支持监控告警 |
| **分布式追踪** | 无 | 添加OpenTelemetry | 支持链路追踪 |
| **日志结构化** | 文本日志 | JSON结构化日志 | 便于日志分析 |

## 6. 未来改进方向

### 6.1 短期目标（1-3个月）

1. **模型池化**：支持多个同类型模型实例的负载均衡
2. **智能显存管理**：基于预测的动态显存分配
3. **请求优先级**：支持不同优先级的请求调度

### 6.2 中期目标（3-6个月）

1. **多GPU支持**：支持多GPU环境的模型分布
2. **弹性伸缩**：根据负载自动调整模型实例数
3. **故障转移**：支持模型服务的自动故障恢复

### 6.3 长期目标（6-12个月）

1. **集群管理**：支持多节点集群部署
2. **模型版本管理**：支持模型版本控制和灰度发布
3. **自动扩缩容**：基于Kubernetes的自动扩缩容

## 7. API 接口清单

### 7.1 模型服务接口

| 端点 | 方法 | 功能 | 认证 |
|------|------|------|------|
| `/v1/models` | GET | 获取可用模型列表 | 否 |
| `/v1/chat/completions` | POST | 聊天补全请求 | 否 |
| `/v1/embeddings` | POST | 嵌入向量请求 | 否 |

### 7.2 管理接口

| 端点 | 方法 | 功能 | 认证 |
|------|------|------|------|
| `/manage/gpu` | GET | 获取GPU状态 | 否 |
| `/manage/models` | GET | 获取模型状态 | 否 |
| `/manage/models/{name}/start` | POST | 启动模型 | 否 |
| `/manage/models/{name}/stop` | POST | 停止模型 | 否 |
| `/manage/models/{name}/switch` | POST | 模型热切换 | 否 |
| `/manage/queue` | GET | 获取队列状态 | 否 |
| `/manage/queue/details` | GET | 获取队列详情 | 否 |
| `/manage/queue/{name}` | DELETE | 清空队列 | 否 |
| `/manage/memory/optimize` | POST | 显存优化 | 否 |
| `/manage/metrics` | GET | 获取监控指标 | 否 |
| `/health` | GET | 健康检查 | 否 |

### 7.3 WebSocket接口

| 端点 | 功能 | 认证 |
|------|------|------|
| `/ws/monitor` | 实时监控状态推送 | 否 |

## 8. 配置说明

### 8.1 模型配置

```yaml
models:
  {model_name}:
    service: string        # systemd服务名
    port: int              # 监听端口
    required_memory: str   # 所需显存 (如: 12GB)
    preload: bool          # 是否预加载
    keep_alive: bool       # 是否常驻
```

### 8.2 全局设置

```yaml
settings:
  concurrency_limit: int   # 并发限制
  min_available_memory: str # 最小可用显存
  request_timeout: int     # 请求超时(秒)
  model_start_timeout: int # 模型启动超时(秒)
  preload_timeout: int     # 预加载超时(秒)
  idle_timeout: int        # 空闲超时(秒)
  memory_flush_interval: int # 显存清理间隔(秒)
  default_memory_strategy: str # 默认显存策略
```

## 9. 部署建议

### 9.1 依赖要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | >= 3.10 | 运行环境 |
| FastAPI | >= 0.110.0 | Web框架 |
| uvicorn | >= 0.29.0 | ASGI服务器 |
| redis | >= 5.0.1 | 队列存储 |
| pydantic | >= 2.6.0 | 数据验证 |
| httpx | >= 0.27.0 | HTTP客户端 |

### 9.2 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| REDIS_URL | redis://localhost:6379 | Redis连接地址 |
| PORT | 5000 | 服务端口 |
| LOG_LEVEL | INFO | 日志级别 |

### 9.3 启动方式

**开发模式：**
```bash
python main.py
```

**生产模式：**
```bash
uvicorn main:app --host 0.0.0.0 --port 5000 --workers 4
```

**Docker部署：**
```bash
docker-compose up -d
```

---

**文档版本**: v1.0  
**生成日期**: 2026-04-15  
**适用项目**: AI Controller