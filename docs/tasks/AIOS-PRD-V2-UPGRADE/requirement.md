# 需求文档: PRD 全功能升级迭代

> 任务 ID: AIOS-PRD-V2-UPGRADE | 优先级: High | 版本: v2

---

## 需求概述

基于 PRD v1.3 文档，对 ai-os 平台现有实现进行全量功能升级迭代。经深入代码审计，大部分 PRD 功能已实现，聚焦于 6 个真实缺口。

**已完整实现 (无需升级)**:
- F1-F7: Go C端全量功能 ✅
- F9-F11: 原子切换/GPU监控/WebSocket ✅
- F13: Agent 系统完整闭环 ✅ (Go agentCompletion+agentStream 含 tool_calls_start/executing/result/end)
- F14: 多引擎路由 ✅ (engines/config/status/switch 路由已在 manage.py)
- F17-F18: GPU显存优选/模型池 ✅
- F19-F21: 前端3页面 ✅
- F22: Agent 对话页 ✅ (AgentChatWindow含 ToolInvocation可视化)

---

## 需升级迭代功能清单 (6 项)

### 1. F15-UPGRADE: 多源模型下载完善 (P1)

**缺口**: OpenXLab 搜索/下载源缺失、下载进度不实时(0→100)、MS 缺 resume_download

**验收标准**:
1. OpenXLab 搜索: keyword 搜索返回模型列表
2. OpenXLab 下载: openxlab model download
3. 下载进度实时百分比 (HF 用 snapshot_download 回调追踪)
4. MS 下载支持 resume_download=True

---

### 2. F16-UPGRADE: 跨平台搜索完善 (P1)

**缺口**: OpenXLab 搜索源缺失、搜索结果无排序

**验收标准**:
1. OpenXLab 搜索: keyword 搜索返回模型列表
2. source=all 聚合 3 平台去重
3. 搜索结果按 size/quant/required_gb/feasible 排序

---

### 3. F3-UPGRADE: 限流增强 (P0)

**缺口**: 仅 IP QPS，缺 token 维度限流、缺 max_model_len 前置拦截

**验收标准**:
1. IP QPS + 每分钟总输入 token 数双维度限流
2. GPU 显存>90% 自动降额
3. 输入 token 超 max_model_len 返回 400
4. X-RateLimit-Remaining 精确反映窗口剩余额度

---

### 4. F8-UPGRADE: 熔断阈值与队列限制 (P1)

**缺口**: CircuitBreaker threshold=5→应10、reset=30s→应5s、缺 max_queue_size

**验收标准**:
1. 连续10次失败触发熔断，5s快速拒绝
2. max_queue_size 超额请求立即429
3. 熔断状态可查询

---

### 5. F12-UPGRADE: 配置管理增强 (P1)

**缺口**: 无 version/乐观锁、无操作日志、无 Go/Python 双向校验

**验收标准**:
1. config.yaml 增加 version 字段
2. PUT 校验 version (HTTP 409)
3. Python 修改后调 Go 校验一致性
4. 操作日志记录

---

### 6. F4-UPGRADE: 并发控制增强 (P1)

**缺口**: 普通/流式共用并发槽、流式无30min超时、僵尸流式连接无特殊处理

**验收标准**:
1. config 增加 max_stream_concurrent
2. 流式请求最大30min超时
3. 僵尸流式连接巡检(>5min清理)
4. goroutine 数量监控告警

---

## AC → 文件映射确认

| AC 编号 | AC 描述 | ac_type | 对应文件路径 | 实现方式 |
|--------|---------|---------|------------|----------|
| F15-ac1 | OpenXLab搜索 | code | app-controller/core/model_hub.py | 新增 _search_oxl 方法 |
| F15-ac2 | OpenXLab下载 | code | app-controller/core/model_hub.py | 新增 _download_oxl 方法 |
| F15-ac3 | 下载进度实时% | code | app-controller/core/download_manager.py | 新增 progress callback |
| F15-ac4 | MS resume_download | code | app-controller/core/model_hub.py | 修改 _download_ms |
| F16-ac1 | OXL搜索 | code | app-controller/core/model_hub.py | 同 F15-ac1 |
| F16-ac2 | 3平台聚合去重 | code | app-controller/core/model_hub.py | 修改 search_models |
| F16-ac3 | 搜索排序 | code | app-controller/core/model_hub.py + routes/model_hub.py | 新增 sort 参数 |
| F3-ac1 | token维度限流 | code | go-vllm-api/internal/service/rate_limiter.go + middleware/ratelimit.go | 新增 token counter |
| F3-ac2 | 显存自适应限流 | code | go-vllm-api/internal/middleware/ratelimit.go | 扩展 GPU degradation |
| F3-ac3 | max_model_len拦截 | code | go-vllm-api/internal/handler/v1/chat.go | 新增前置校验 |
| F3-ac4 | Remaining头精确 | code | go-vllm-api/internal/middleware/ratelimit.go | 修改 header 计算 |
| F8-ac1 | 熔断阈值10/5s | config | go-vllm-api/internal/proxy/vllm.go | 修改 NewCircuitBreaker 参数 |
| F8-ac2 | max_queue_size | code | go-vllm-api/internal/service/scheduler.go | 新增队列容量限制 |
| F8-ac3 | 熔断状态可查询 | code | go-vllm-api/internal/handler/health/health.go | 已有 CircuitBreakerStats |
| F12-ac1 | version字段 | code | app-controller/core/config.py + core/config_watcher.py | 新增 version 字段 |
| F12-ac2 | 乐观锁409 | code | app-controller/routes/manage.py | 修改 PUT /manage/config |
| F12-ac3 | Go校验一致性 | code | app-controller/routes/manage.py | 新增校验调用 |
| F12-ac4 | 操作日志 | code | app-controller/core/config_watcher.py | 新增操作日志 |
| F4-ac1 | max_stream_concurrent | config | go-vllm-api + config.yaml | 新增配置字段 |
| F4-ac2 | 30min超时 | code | go-vllm-api/internal/service/scheduler.go | 新增 stream max duration |
| F4-ac3 | 僵尸流式清理 | code | go-vllm-api/internal/service/scheduler.go | 扩展 zombie checker |
| F4-ac4 | goroutine监控 | code | go-vllm-api/internal/service/scheduler.go | 新增 goroutine count |

**门禁结论**: PASS — 所有 code 类 AC 已映射到具体文件
