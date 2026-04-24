# app-controller → go-vllm-api 重构计划

## 任务清单

| ID | 任务 | 状态 | 依赖 |
|----|------|------|------|
| T1 | 修复编译错误 (logger/prometheus/redis/cors/watcher/ws_manager/cache_updater/gpu_monitor/manage_handler) | ✅ 完成 | - |
| T2 | ChatMessage 支持 multimodal content part + tools/logprobs/response_format | ✅ 完成 | T1 |
| T3 | 限流中间件接入 Redis + 超时中间件 | ✅ 完成 | T1 |
| T4 | 创建部署配置文件 (config.yaml/Dockerfile/docker-compose.yml) | ✅ 完成 | - |
| T5 | 编译验证 + go vet | ✅ 完成 | T1-T4 |
| T6 | 实现图像验证与上传接口 (ValidateImage/UploadImage) | ⏳ 进行中 | T1 |
| T7 | 实现模型测试框架接口 (test_model/comparative_analysis) | 📅 待办 | T1 |
| T8 | 完善结构化日志与 RequestContext | 📅 待办 | T1 |
| T9 | 编写核心逻辑的单元测试 | 📅 待办 | T5 |

## 已完成的变更

### 编译错误修复
- `internal/pkg/logger/logger.go`: `zapcore.Open` → `os.OpenFile`
- `internal/pkg/prometheus/prometheus.go`: 修复 `promhttp.Handler` 类型、移除 `.Desc().Name()` 调用
- `internal/repository/redis.go`: 修复 `Watch` 签名 (需要回调函数)，修复 `Info` 返回类型
- `internal/middleware/cors.go`: 移除未使用 `time` import
- `internal/config/watcher.go`: 移除未使用 `os` import
- `internal/service/ws_manager.go`: 修复 `for range` 索引→值
- `internal/service/cache_updater.go`: 修复 unused `gpuStatus` 变量
- `internal/service/gpu_monitor.go`: 移除 unused `bufio`/`json` import
- `internal/handler/manage/manage.go`: 修复 `GetConfig` 重复定义、移除未使用 `model` import

### P0 功能补齐
- `internal/model/chat.go`: 新增 `ContentVal`(支持 string/[]ContentPart)、`ContentPart`(text/image_url)、`ToolDefinition`/`ToolCall`/`ResponseFormat`/`LogprobsResult`
- `internal/middleware/ratelimit.go`: 接入 `service.RateLimiter` (Redis)，新增 `Timeout` 中间件
- `internal/service/rate_limiter.go`: 新增 `CanAcceptClientRequest` 方法 (基于 IP 的 Redis 限流)
- `internal/service/scheduler.go`: 新增 `GetRateLimiter` getter

### P1 部署配置
- `configs/config.yaml`: Go 版完整配置文件
- `Dockerfile`: Go 多阶段构建 (< 50MB)
- `docker-compose.yml`: go-vllm-api + redis
