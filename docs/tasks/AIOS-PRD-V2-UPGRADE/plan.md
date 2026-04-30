# 任务清单: PRD 全功能升级迭代

> 任务 ID: AIOS-PRD-V2-UPGRADE | 7 个开发任务 | 优先级排序: P0→P1

---

## 任务总览

| ID | 标题 | 优先级 | 功能点 | 文件数 | 测试 |
|----|------|--------|--------|--------|------|
| T1 | OpenXLab 搜索/下载 | P1 | F15/F16 | 2 | pytest |
| T2 | 下载实时进度 | P1 | F15 | 2 | pytest |
| T3 | MS resume + 搜索排序 | P1 | F15/F16 | 2 | pytest |
| T4 | Token限流 + 前置拦截 | P0 | F3 | 3 | go test |
| T5 | 熔断阈值 + queue_size | P1 | F8 | 2 | go test |
| T6 | 配置version + 乐观锁 | P1 | F12 | 3 | pytest |
| T7 | 分级并发 + 超时 + 清理 | P1 | F4 | 2 | go test |

**执行顺序**: T4(P0) → T5 → T6 → T7 → T1 → T2 → T3

---

## T1: OpenXLab 搜索/下载源实现

- 新增 `model_hub.py._search_oxl()` 调用 openxlab API
- 新增 `model_hub.py._download_oxl()` 调用 openxlab download
- `search_models(source='all')` 聚合 3 平台去重
- 路由: `/manage/models/search?source=oxl`

## T2: 下载进度实时百分比推送

- `download_manager.py`: HF snapshot_download 用 tqdm callback 追踪进度
- `task.progress_pct` 中间更新 (0→10→20→...→100)
- WS/SSE 推送 `_fire_progress()` 在每个 progress_pct 变化时触发

## T3: ModelScope resume + 搜索排序

- `model_hub.py._download_ms()`: 添加 `resume_download=True`
- `search_models(sort='size'|'quant'|'required_gb'|'feasible')` 排序参数
- 路由: `/manage/models/search?sort=feasible`

## T4: Token维度限流 + max_model_len前置拦截 (P0)

- `rate_limiter.go`: 新增 TokenLimiter (Redis sliding window 60s)
- `chat.go`: 前置 `estimateTokens()` vs `max_model_len` → 400
- `ratelimit.go`: GPU>90%降额 + Remaining头精确

## T5: 熔断阈值调整 + max_queue_size

- `vllm.go`: NewCircuitBreaker(10, 5s)
- `scheduler.go`: maxQueueSize 限制 → 429

## T6: 配置version + 乐观锁 + Go校验

- `config.yaml`: version 字段
- `config_watcher.py`: version自动递增 + 操作日志
- `manage.py`: PUT version 409 + Go校验调用

## T7: 分级并发 + 30min超时 + 僵尸清理

- `config.yaml`: max_stream_concurrent
- `scheduler.go`: streamSlots + 30min timeout + zombie stream cleanup + goroutine count
