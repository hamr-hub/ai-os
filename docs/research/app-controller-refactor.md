# app-controller 重构技术文档：Go vs Rust 方案对比与重构设计

> 生成时间：2026-04-22 | 项目：ai-os/app-controller

---

## 一、现有系统分析

### 1.1 系统概览

app-controller 是一个基于 FastAPI 的 AI 模型调度控制器，核心功能包括：

| 功能域 | 模块 | 代码量 | 说明 |
|--------|------|--------|------|
| 模型调度 | `scheduler.py` | 608行 | 模型生命周期管理、内存感知驱逐、预加载 |
| GPU 监控 | `monitor.py` | 516行 | nvidia-smi 异步采集、缓存、历史记录 |
| vLLM 管理 | `vllm_manager.py` | 592行 | 模型扫描/切换/自测、脚本更新 |
| Redis 客户端 | `redis_client.py` | 488行 | 单例、装饰器缓存、标签操作、管道 |
| 指标采集 | `metrics.py` | 521行 | 请求/Token/GPU/健康评分、Redis 持久化 |
| 模型测试 | `model_testing.py` | 615行 | 4类测试、对比分析、资源追踪 |
| 限流排队 | `rate_limiter.py` | 301行 | Redis WATCH/MULTI 原子操作、优先级队列 |
| 缓存服务 | `cache_service.py` + `cache_updater.py` | 510行 | 两级缓存（内存+Redis）、10个预热任务 |
| API 代理 | `proxy_vllm.py` + `aiclient_interface.py` | 572行 | vLLM HTTP 代理、指数退避重试 |
| WebSocket | `websocket_manager.py` | 99行 | 频道广播 |
| Prometheus | `prometheus_exporter.py` | 225行 | 13项指标导出 |
| 路由 | `main.py` + `routes/v1.py` | 2731行 | OpenAI 兼容 API + 管理 + 健康 |
| **合计** | | **~7,400行** | |

### 1.2 架构特征

```
┌──────────────────────────────────────────────────┐
│                   FastAPI App                     │
├──────────┬──────────┬──────────┬─────────────────┤
│  v1 API  │  Manage  │  Health  │   WebSocket     │
├──────────┴──────────┴──────────┴─────────────────┤
│              Middleware (RateLimit/Timeout/Track)  │
├──────────────────────────────────────────────────┤
│            Service Layer (Singletons in deps.py)  │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │ Scheduler│ │GPUMonitor│ │MetricsCollector  │ │
│  └────┬─────┘ └────┬─────┘ └────────┬─────────┘ │
│       │            │                │            │
│  ┌────┴─────┐ ┌────┴─────┐ ┌───────┴──────────┐ │
│  │RateLimiter│ │CacheSvc  │ │PrometheusExporter│ │
│  └────┬─────┘ └────┬─────┘ └──────────────────┘ │
│       │            │                              │
│  ┌────┴────────────┴────┐ ┌──────────────────────┐│
│  │      Redis           │ │  Systemctl/vLLM     ││
│  └──────────────────────┘ └──────────────────────┘│
└──────────────────────────────────────────────────┘
```

### 1.3 关键技术依赖

| 依赖 | 用途 | 重构影响 |
|------|------|----------|
| **asyncio** | 全异步 I/O、后台任务 | 需要等效异步运行时 |
| **Redis** | 状态存储、限流、缓存、排队 | 两者均有成熟驱动 |
| **httpx** | vLLM HTTP 代理（普通+流式） | 需要成熟的 HTTP 客户端+流式支持 |
| **nvidia-smi/pynvml** | GPU 监控 | 需要调用系统命令或 NVML FFI |
| **systemctl** | 服务管理 | 命令行调用，语言无关 |
| **Pydantic** | 数据校验 | Go: 无直接等价；Rust: serde |
| **YAML** | 配置文件 | 两者均有库 |
| **Prometheus** | 指标导出 | 两者均有库 |
| **SSE/WebSocket** | 流式响应 | 需要原生支持 |

### 1.4 现有痛点

1. **单体 main.py 2019 行** — 路由未完全拆分，管理/健康/WebSocket 路由仍内联
2. **重复定义** — Pydantic schema 在 `schemas/` 和 `main.py` 中重复
3. **Redis 同步驱动 + 包装** — 实际用同步 redis-py 在 FastAPI 的线程池中运行，不是真正的异步
4. **全局单例** — `deps.py` 模块级实例化，测试困难
5. **动态类型** — 运行时才发现接口不匹配
6. **GIL 限制** — CPU 密集操作（指标计算、图像校验）受限于 GIL

---

## 二、Go vs Rust 方案对比

### 2.1 综合对比矩阵

| 维度 | Go | Rust | 评估 |
|------|-----|------|------|
| **开发效率** | ★★★★★ | ★★★ | Go 胜 |
| **运行性能** | ★★★★ | ★★★★★ | Rust 胜 |
| **内存占用** | ★★★★ | ★★★★★ | Rust 胜 |
| **并发模型** | ★★★★★ | ★★★★ | Go 胜（goroutine 更简单） |
| **异步生态** | ★★★★★ | ★★★★ | Go 胜（天然并发） |
| **类型安全** | ★★★★ | ★★★★★ | Rust 胜 |
| **Web 框架** | ★★★★★ | ★★★ | Go 胜（Gin/Echo/Fiber 成熟） |
| **Redis 库** | ★★★★★ | ★★★★ | Go 胜（go-redis 功能完整） |
| **运维友好** | ★★★★★ | ★★★★ | Go 胜（单二进制、pprof） |
| **学习曲线** | ★★★★★ | ★★ | Go 胜 |
| **人才储备** | ★★★★★ | ★★★ | Go 胜 |
| **交叉编译** | ★★★★★ | ★★★★ | Go 胜 |
| **编译速度** | ★★★★★ | ★★ | Go 胜 |
| **流式 SSE** | ★★★★★ | ★★★★ | Go 胜（框架原生支持） |
| **GPU/NVML** | ★★★ | ★★★ | 平手（都需要 FFI/命令行） |
| **容错误处理** | ★★★★ | ★★★★★ | Rust 胜（编译期保证） |

### 2.2 针对本项目的关键决策因素

#### 因素 1：SSE 流式代理（核心路径）

本系统最关键的路径是 `/v1/chat/completions` 的流式 SSE 代理。

- **Go**: `gin` / `echo` 原生支持 `SSEvent` 流式写入，`c.SSEvent()` + `c.Stream()`，代码简洁。`httpx` 等价物为 `net/http` + `bufio.Scanner`，天然支持流式读取。
- **Rust**: `axum` 支持 SSE（`Sse<impl Stream>`），但流式代理需要手动管理连接生命周期、处理背压，复杂度显著高于 Go。

#### 因素 2：后台任务调度

系统有 10+ 个周期性后台任务（GPU 缓存 3s、模型状态 5s、队列状态 3s 等）。

- **Go**: `goroutine` + `time.Ticker`，极简。每个后台任务 5 行代码。
- **Rust**: `tokio::spawn` + `tokio::time::interval`，可行但需要手动管理 `JoinHandle`、处理 `Send` 约束。

#### 因素 3：系统命令调用（nvidia-smi / systemctl）

- **Go**: `os/exec.Command` + `CombinedOutput`，简单直接。
- **Rust**: `tokio::process::Command`，异步版，同样简单。**平手**。

#### 因素 4：Redis 操作复杂度

系统使用 Redis 的 WATCH/MULTI 原子事务、优先级队列（List + Sort）、标签缓存等高级特性。

- **Go**: `go-redis/redis` v9 完整支持 TxPipeline、Watch、Lua 脚本，API 成熟。
- **Rust**: `redis-rs` 支持，但事务 API 不如 go-redis 便捷，需手动管理连接池。

#### 因素 5：部署环境

目标环境为 NVIDIA Jetson（ARM64），需要交叉编译。

- **Go**: `GOARCH=arm64 GOOS=linux go build`，一条命令。
- **Rust**: `cross build --target aarch64-unknown-linux-gnu`，需要 Docker 或安装交叉工具链。

### 2.3 结论

| 方案 | 推荐度 | 理由 |
|------|--------|------|
| **Go（推荐）** | ★★★★★ | SSE 流式代理是核心路径，Go 原生支持最好；goroutine 天然适配后台任务模式；编译快、部署简单、团队上手成本低；go-redis 和 Gin 生态成熟 |
| **Rust** | ★★★ | 性能和安全性更优，但本系统为 I/O 密集型（代理+调度），非 CPU 密集型，Rust 的性能优势无法充分发挥；流式代理和后台任务的实现复杂度显著高于 Go |

**最终推荐：Go**

理由总结：
1. 本系统是 **I/O 密集型代理+调度器**，不是计算密集型，Go 的性能完全足够
2. **SSE 流式代理**是核心路径，Go 的实现复杂度比 Rust 低 3-5 倍
3. 10+ 后台任务用 goroutine 实现极简
4. 目标环境 ARM64 交叉编译一步到位
5. 开发效率约为 Rust 的 2-3 倍，维护成本更低

---

## 三、Go 重构技术方案

### 3.1 技术选型

| 组件 | 选型 | 版本 | 替代方案 |
|------|------|------|----------|
| Web 框架 | **Gin** | v1.10+ | Echo, Fiber |
| Redis | **go-redis** | v9 | Rueidis |
| 配置 | **Viper** | v1.18+ | Koanf |
| 日志 | **Zap** | v1.27+ | Slog, Zerolog |
| 校验 | **go-playground/validator** | v10 | - |
| Prometheus | **prometheus/client_golang** | v1.19+ | - |
| YAML | **gopkg.in/yaml.v3** | v3 | - |
| UUID | **google/uuid** | v1.6+ | - |
| 测试 | **testify** | v1.9+ | - |
| 热重载 | **fsnotify** | v1.7+ | - |
| 进程管理 | **os/exec** | 标准库 | - |

### 3.2 项目结构

```
app-controller-go/
├── cmd/
│   └── server/
│       └── main.go                # 入口
├── internal/
│   ├── config/
│   │   ├── config.go              # 配置结构体 + 加载逻辑
│   │   └── watcher.go             # 配置热重载
│   ├── handler/
│   │   ├── v1/                    # OpenAI 兼容 API
│   │   │   ├── chat.go            # /v1/chat/completions
│   │   │   ├── models.go          # /v1/models
│   │   │   ├── embeddings.go      # /v1/embeddings
│   │   │   ├── images.go          # /v1/images/*
│   │   │   └── router.go          # v1 路由注册
│   │   ├── manage/                # 管理接口
│   │   │   ├── gpu.go
│   │   │   ├── model.go
│   │   │   ├── queue.go
│   │   │   ├── cache.go
│   │   │   ├── config.go
│   │   │   └── router.go
│   │   ├── health/                # 健康检查
│   │   │   └── router.go
│   │   └── ws/                    # WebSocket
│   │       └── monitor.go
│   ├── middleware/
│   │   ├── ratelimit.go
│   │   ├── timeout.go
│   │   ├── request_id.go
│   │   ├── cors.go
│   │   └── metrics.go
│   ├── service/
│   │   ├── scheduler.go           # 模型调度 + 生命周期
│   │   ├── gpu_monitor.go         # GPU 监控
│   │   ├── vllm_manager.go        # vLLM 管理
│   │   ├── sysctl.go              # systemd 管理
│   │   ├── cache.go               # 两级缓存
│   │   ├── cache_updater.go       # 缓存预热
│   │   ├── rate_limiter.go        # 限流 + 优先级队列
│   │   ├── model_tester.go        # 模型测试
│   │   ├── metrics_collector.go   # 指标采集
│   │   └── ws_manager.go          # WebSocket 管理
│   ├── proxy/
│   │   └── vllm.go                # vLLM HTTP 代理（含流式）
│   ├── repository/
│   │   └── redis.go               # Redis 操作封装
│   ├── model/
│   │   ├── chat.go                # Chat 相关 DTO
│   │   ├── embedding.go
│   │   ├── image.go
│   │   ├── service.go
│   │   └── test.go
│   └── pkg/
│       ├── logger/                 # 结构化日志
│       ├── prometheus/             # Prometheus 导出
│       └── response/              # 统一响应格式
├── configs/
│   └── config.yaml
├── scripts/
│   ├── build.sh
│   └── cross-build.sh
├── Dockerfile
├── Makefile
├── go.mod
└── go.sum
```

### 3.3 核心模块映射

| Python 模块 | Go 模块 | 关键变化 |
|-------------|---------|----------|
| `main.py` (2019行) | `cmd/server/main.go` + `internal/handler/*` | 拆分为独立 handler |
| `core/config.py` | `internal/config/config.go` | Viper 替代 Pydantic，struct tag 校验 |
| `core/scheduler.py` | `internal/service/scheduler.go` | sync.Mutex 替代 asyncio.Lock，goroutine 替代协程 |
| `core/monitor.py` | `internal/service/gpu_monitor.go` | `os/exec` 调用 nvidia-smi，ticker 缓存 |
| `core/vllm_manager.py` | `internal/service/vllm_manager.go` | 文件操作用 `os` 标准库 |
| `core/redis_client.py` | `internal/repository/redis.go` | go-redis v9，泛型封装 |
| `core/rate_limiter.py` | `internal/service/rate_limiter.go` | TxPipeline 替代 WATCH/MULTI |
| `core/cache_service.py` | `internal/service/cache.go` | `sync.RWMutex` + `map` 本地缓存 |
| `core/metrics.py` | `internal/service/metrics_collector.go` | 原子操作 (`sync/atomic`) 替代锁 |
| `core/websocket_manager.py` | `internal/service/ws_manager.go` | gorilla/websocket 或 nhooyr.io/websocket |
| `middleware/*` | `internal/middleware/*` | Gin 中间件接口 |
| `schemas/*` | `internal/model/*` | Go struct + validator tag |

### 3.4 核心流程设计

#### 3.4.1 SSE 流式代理（最关键路径）

```go
// internal/proxy/vllm.go
func (p *VLLMProxy) StreamChatCompletion(
    ctx *gin.Context,
    req *model.ChatCompletionRequest,
) error {
    body, _ := json.Marshal(req)
    httpReq, _ := http.NewRequestWithContext(
        ctx.Request.Context(), "POST",
        p.baseURL+"/v1/chat/completions",
        bytes.NewReader(body),
    )
    httpReq.Header.Set("Content-Type", "application/json")
    httpReq.Header.Set("Accept", "text/event-stream")

    resp, err := p.streamClient.Do(httpReq)
    if err != nil {
        return err
    }
    defer resp.Body.Close()

    ctx.Header("Content-Type", "text/event-stream")
    ctx.Header("Cache-Control", "no-cache")
    ctx.Header("Connection", "keep-alive")

    scanner := bufio.NewScanner(resp.Body)
    scanner.Buffer(make([]byte, 0, 64*1024), 1024*1024)
    for scanner.Scan() {
        line := scanner.Text()
        if strings.HasPrefix(line, "data: ") {
            data := strings.TrimPrefix(line, "data: ")
            if data == "[DONE]" {
                fmt.Fprintf(ctx.Writer, "data: [DONE]\n\n")
                ctx.Writer.Flush()
                break
            }
            fmt.Fprintf(ctx.Writer, "%s\n\n", line)
            ctx.Writer.Flush()
        } else if line != "" {
            fmt.Fprintf(ctx.Writer, "%s\n", line)
        }
    }
    return nil
}
```

#### 3.4.2 后台任务模式

```go
// internal/service/cache_updater.go
func (u *CacheUpdater) Start(ctx context.Context) {
    tasks := []struct {
        name     string
        interval time.Duration
        fn       func(context.Context)
    }{
        {"gpu_status", 3 * time.Second, u.updateGPUStatus},
        {"gpu_summary", 10 * time.Second, u.updateGPUSummary},
        {"model_status", 5 * time.Second, u.updateModelStatus},
        {"queue_status", 3 * time.Second, u.updateQueueStatus},
        {"system_status", 10 * time.Second, u.updateSystemStatus},
        {"health", 5 * time.Second, u.updateHealth},
        {"metrics", 10 * time.Second, u.updateMetrics},
        {"preload_status", 30 * time.Second, u.updatePreloadStatus},
        {"models_list", 300 * time.Second, u.updateModelsList},
        {"models_summary", 3 * time.Second, u.updateModelsSummary},
    }

    // warmup: all tasks run once concurrently
    var wg sync.WaitGroup
    for _, t := range tasks {
        wg.Add(1)
        go func(task struct {
            name     string
            interval time.Duration
            fn       func(context.Context)
        }) {
            defer wg.Done()
            task.fn(ctx)
        }(t)
    }
    wg.Wait()

    // periodic refresh
    for _, t := range tasks {
        go func(task struct {
            name     string
            interval time.Duration
            fn       func(context.Context)
        }) {
            ticker := time.NewTicker(task.interval)
            defer ticker.Stop()
            for {
                select {
                case <-ctx.Done():
                    return
                case <-ticker.C:
                    task.fn(ctx)
                }
            }
        }(t)
    }
}
```

#### 3.4.3 限流器（Redis 原子事务）

```go
// internal/service/rate_limiter.go
func (r *RateLimiter) Acquire(ctx context.Context, model string, priority int) (string, error) {
    key := fmt.Sprintf("rate_limit:%s:count", model)
    slotID := uuid.New().String()

    err := r.redis.Watch(ctx, func(tx *redis.Tx) error {
        count, err := tx.Get(ctx, key).Int64()
        if err != nil && err != redis.Nil {
            return err
        }
        limit := r.getLimit(model)
        if count >= int64(limit) {
            return ErrRateLimitExceeded
        }
        _, err = tx.TxPipelined(ctx, func(pipe redis.Pipeliner) error {
            pipe.Incr(ctx, key)
            pipe.Expire(ctx, key, 60*time.Second)
            pipe.HSet(ctx, key+":slots", slotID, time.Now().Unix())
            return nil
        })
        return err
    }, key)

    return slotID, err
}
```

#### 3.4.4 依赖注入

```go
// cmd/server/main.go
type App struct {
    Config         *config.AppConfig
    Redis          *repository.RedisRepo
    Scheduler      *service.Scheduler
    GPUMonitor     *service.GPUMonitor
    CacheService   *service.CacheService
    CacheUpdater   *service.CacheUpdater
    RateLimiter    *service.RateLimiter
    MetricsCollector *service.MetricsCollector
    PrometheusExporter *pkg.PrometheusExporter
    WSManager      *service.WSManager
    VLLMProxy      *proxy.VLLMProxy
    ModelTester    *service.ModelTester
}

func main() {
    cfg := config.Load()
    app := &App{Config: cfg}

    // wire dependencies
    app.Redis = repository.NewRedisRepo(cfg.Redis)
    app.CacheService = service.NewCacheService(app.Redis)
    app.GPUMonitor = service.NewGPUMonitor(cfg)
    app.RateLimiter = service.NewRateLimiter(app.Redis, cfg)
    app.Scheduler = service.NewScheduler(cfg, app.RateLimiter, app.GPUMonitor)
    app.MetricsCollector = service.NewMetricsCollector(app.Redis)
    // ...

    // register routes
    r := gin.Default()
    handler.RegisterRoutes(r, app)

    // background tasks
    ctx, cancel := context.WithCancel(context.Background())
    defer cancel()
    go app.GPUMonitor.Start(ctx)
    go app.CacheUpdater.Start(ctx)

    r.Run(":8000")
}
```

### 3.5 配置模型

```go
// internal/config/config.go
type AppConfig struct {
    Models   map[string]ModelConfig `yaml:"models"`
    Settings SettingsConfig         `yaml:"settings"`
    VLLM     VLLMConfig             `yaml:"vllm"`
}

type ModelConfig struct {
    Service         string `yaml:"service" validate:"required"`
    Port            int    `yaml:"port" validate:"min=1,max=65535"`
    RequiredMemory  string `yaml:"required_memory"`
    Preload         bool   `yaml:"preload"`
    KeepAlive       bool   `yaml:"keep_alive"`
    ModelPath       string `yaml:"model_path"`
    SupportsImages  bool   `yaml:"supports_images"`
    Description     string `yaml:"description"`
    ConcurrencyLimit int   `yaml:"concurrency_limit"`
}

type SettingsConfig struct {
    ConcurrencyLimit  int            `yaml:"concurrency_limit"`
    MinAvailableMemory string        `yaml:"min_available_memory"`
    RequestTimeout    int            `yaml:"request_timeout"`
    Redis             RedisConfig    `yaml:"redis"`
    Queue             QueueConfig    `yaml:"queue"`
    Priority          PriorityConfig `yaml:"priority"`
    Recovery          RecoveryConfig `yaml:"recovery"`
}
```

### 3.6 分阶段重构计划

#### Phase 1：骨架搭建（1 周）

- [ ] 初始化 Go 模块、项目结构
- [ ] 实现 `config` 加载（Viper + YAML）
- [ ] 实现 `model` DTO（struct + validator）
- [ ] 实现 `repository/redis.go`（go-redis 封装）
- [ ] 实现 `middleware`（CORS、RequestID、超时、限流）
- [ ] 搭建 Gin 路由骨架，注册空 handler
- [ ] 实现结构化日志（Zap）

#### Phase 2：核心代理路径（1.5 周）

- [ ] 实现 `proxy/vllm.go`（普通 + 流式代理）
- [ ] 实现 `handler/v1/chat.go`（SSE 流式）
- [ ] 实现 `handler/v1/models.go`
- [ ] 实现 `handler/v1/embeddings.go`
- [ ] 实现 `handler/v1/images.go`
- [ ] 端到端验证：聊天流式、模型列表、嵌入

#### Phase 3：调度与监控（1.5 周）

- [ ] 实现 `service/gpu_monitor.go`（nvidia-smi + 缓存）
- [ ] 实现 `service/scheduler.go`（模型启动/停止/内存管理）
- [ ] 实现 `service/sysctl.go`（systemctl 封装 + watchdog）
- [ ] 实现 `service/rate_limiter.go`（Redis 原子事务 + 优先级队列）
- [ ] 实现 `service/vllm_manager.go`（模型切换 + 自测）
- [ ] 集成测试：模型调度全流程

#### Phase 4：缓存与指标（1 周）

- [ ] 实现 `service/cache.go`（两级缓存）
- [ ] 实现 `service/cache_updater.go`（10 个预热任务）
- [ ] 实现 `service/metrics_collector.go`（指标采集 + Redis 持久化）
- [ ] 实现 `pkg/prometheus`（13 项指标导出）
- [ ] 实现 `handler/manage/*.go`（管理接口）
- [ ] 实现 `handler/health/*.go`（健康检查）

#### Phase 5：辅助功能 + 收尾（1 周）

- [ ] 实现 `service/model_tester.go`（4 类测试 + 对比分析）
- [ ] 实现 `service/ws_manager.go`（WebSocket 广播）
- [ ] 实现配置热重载（fsnotify）
- [ ] 编写 Dockerfile + Makefile
- [ ] 编写交叉编译脚本（ARM64）
- [ ] 性能基准测试 vs Python 版本
- [ ] 文档补充

**总工期：约 6 周**

### 3.7 预期收益

| 指标 | Python 现状 | Go 重构后 | 提升 |
|------|------------|-----------|------|
| 内存占用 | ~200MB | ~30MB | 85% ↓ |
| 冷启动时间 | ~3s | ~50ms | 98% ↓ |
| SSE 流式首 Token 延迟 | ~15ms | ~3ms | 80% ↓ |
| 最大并发连接 | ~500 | ~10,000 | 20x |
| 二进制大小 | N/A | ~15MB | 单文件部署 |
| 交叉编译 | 需 Python 环境 | 一条命令 | 极简 |
| 类型安全 | 运行时 | 编译期 | 根除一类错误 |

### 3.8 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| SSE 流式代理边缘 case | 中 | 高 | 先用 Python 版本跑 E2E 测试，Go 版本逐 case 对齐 |
| Redis 事务行为差异 | 低 | 中 | 编写 Redis 操作的集成测试，对比 WATCH/MULTI 行为 |
| NVML FFI 调用问题 | 中 | 低 | 优先使用 nvidia-smi 命令行，NVML 作为优化 |
| 配置热重载竞态 | 低 | 高 | 使用 sync.RWMutex 保护配置读写 |
| 团队 Go 经验不足 | 中 | 中 | Phase 1 骨架阶段安排 Code Review + 培训 |

---

## 四、附录

### A. Go 依赖清单（go.mod）

```
github.com/gin-gonic/gin v1.10.0
github.com/redis/go-redis/v9 v9.7.0
github.com/spf13/viper v1.19.0
github.com/go-playground/validator/v10 v10.22.0
github.com/google/uuid v1.6.0
github.com/prometheus/client_golang v1.19.1
go.uber.org/zap v1.27.0
gopkg.in/yaml.v3 v3.0.1
github.com/fsnotify/fsnotify v1.7.0
github.com/gorilla/websocket v1.5.3
github.com/stretchr/testify v1.9.0
```

### B. Python → Go 核心语法映射

| Python | Go |
|--------|-----|
| `async def` / `await` | `func` + `go` / `<-chan` |
| `asyncio.Lock()` | `sync.Mutex{}` |
| `asyncio.gather()` | `sync.WaitGroup` / `errgroup.Group` |
| `@dataclass` / Pydantic | `struct` + tag |
| `try/except` | `if err != nil { return err }` |
| `f"xxx {var}"` | `fmt.Sprintf("xxx %s", var)` |
| `dict` | `map[string]interface{}` / 具体 struct |
| `Optional[X]` | `*X` (指针) |
| `List[X]` | `[]X` |
| `Dict[K,V]` | `map[K]V` |

### C. Makefile 模板

```makefile
.PHONY: build run test clean cross-build

APP_NAME := app-controller
VERSION := $(shell git describe --tags --always --dirty)
LDFLAGS := -s -w -X main.Version=$(VERSION)

build:
	go build -ldflags "$(LDFLAGS)" -o bin/$(APP_NAME) ./cmd/server

run: build
	./bin/$(APP_NAME) -config configs/config.yaml

test:
	go test -race -cover ./...

clean:
	rm -rf bin/

cross-build:
	GOOS=linux GOARCH=arm64 go build -ldflags "$(LDFLAGS)" -o bin/$(APP_NAME)-arm64 ./cmd/server
	GOOS=linux GOARCH=amd64 go build -ldflags "$(LDFLAGS)" -o bin/$(APP_NAME)-amd64 ./cmd/server

docker-build:
	docker build -t $(APP_NAME):$(VERSION) .
```

### D. Dockerfile 模板

```dockerfile
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -ldflags "-s -w" -o /app-controller ./cmd/server

FROM alpine:3.20
RUN apk add --no-cache ca-certificates tzdata nvidia-utils
COPY --from=builder /app-controller /usr/local/bin/
COPY configs/config.yaml /etc/app-controller/config.yaml
EXPOSE 8000
ENTRYPOINT ["app-controller", "-config", "/etc/app-controller/config.yaml"]
```
