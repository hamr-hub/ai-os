# ai-os 全流程测试计划与测试用例

> 基于项目实际架构：Go C端网关(35001) + Python B端管理(35000) + vLLM/SGLang推理引擎 + Vue3前端(30000/30001)

---

## 一、测试环境准备

### 1.1 环境依赖
- Go网关服务 `go-vllm-api` 运行于 `localhost:35001`
- Python B端 `app-controller` 运行于 `localhost:35000`
- Redis 服务运行于 `localhost:6379`
- vLLM推理引擎运行于 `localhost:8000`
- 前端开发服务器运行于 `localhost:30001`
- 至少1个GPU可用（测试模型相关功能）
- 测试用小尺寸模型（如Qwen2-7B-Instruct）已就绪

### 1.2 测试工具
- `pytest` + `requests` (Python接口测试)
- `Go testing` (Go单元测试)
- `k6` 或 `wrk` (性能压测)
- `Postman/curl` (手工验证)
- `Vitest + Playwright` (前端测试)

### 1.3 配置文件
- `go-vllm-api/configs/config.yaml` - Go网关配置
- `app-controller/config.yaml` - Python B端配置

---

## 二、7维度全链路测试用例

### 2.1 流量网关层（Go 35001）

#### TC-GW-001: SSE流式长连接并发控制
| 字段 | 内容 |
|------|------|
| **优先级** | P0 |
| **前置条件** | Go网关启动，配置 `concurrency_limit=3`，模型已加载 |
| **测试步骤** | 1. 使用OpenAI SDK同时发起4个stream=true请求<br>2. 观察第4个请求的响应<br>3. 等待前3个请求完成后，再次发起请求 |
| **预期结果** | 前3个请求正常流式返回；第4个返回429 Too Many Requests；完成后新请求正常 |
| **测试脚本** | `tests/test_gateway/test_concurrency.py::test_stream_concurrent_limit` |

#### TC-GW-002: 长连接goroutine泄漏检测
| 字段 | 内容 |
|------|------|
| **优先级** | P0 |
| **前置条件** | Go网关启动 |
| **测试步骤** | 1. 记录初始goroutine数量（通过/manage/metrics）<br>2. 发起100个流式请求，每个中途断开连接<br>3. 等待30秒后，检查goroutine数量 |
| **预期结果** | goroutine数量回落到初始值附近（±5），无持续增长 |
| **测试脚本** | `tests/test_gateway/test_concurrency.py::test_goroutine_leak` |

#### TC-GW-003: 单IP QPS限流
| 字段 | 内容 |
|------|------|
| **优先级** | P0 |
| **前置条件** | 配置rate limit: max_requests=2, window_seconds=1 |
| **测试步骤** | 1. 从非白名单IP每秒发送3次 `/v1/chat/completions` 请求<br>2. 检查超限请求的响应码和Retry-After头 |
| **预期结果** | 超限请求返回429，响应含 `error: rate limit exceeded` |
| **测试脚本** | `tests/test_gateway/test_rate_limit.py::test_ip_rate_limit` |

#### TC-GW-004: 白名单IP免限流
| 字段 | 内容 |
|------|------|
| **优先级** | P1 |
| **前置条件** | 白名单包含 127.0.0.1 |
| **测试步骤** | 1. 从127.0.0.1每秒发送10次请求，持续10秒 |
| **预期结果** | 所有请求正常放行，无429 |
| **测试脚本** | `tests/test_gateway/test_rate_limit.py::test_whitelist_exempt` |

#### TC-GW-005: IP伪造拦截
| 字段 | 内容 |
|------|------|
| **优先级** | P1 |
| **前置条件** | Go网关使用 `c.ClientIP()` 获取真实IP |
| **测试步骤** | 1. 伪造 `X-Forwarded-For: 127.0.0.1` 从外部IP发送请求<br>2. 检查限流是否生效 |
| **预期结果** | Gin的ClientIP()取TCP连接真实IP，伪造无效，限流正常生效 |
| **测试脚本** | `tests/test_gateway/test_rate_limit.py::test_ip_forgery_blocked` |

#### TC-GW-006: 上游引擎故障熔断
| 字段 | 内容 |
|------|------|
| **优先级** | P0 |
| **前置条件** | vLLM引擎正常运行 |
| **测试步骤** | 1. kill掉vLLM进程<br>2. 连续发送10次请求<br>3. 重启vLLM，观察恢复 |
| **预期结果** | 引擎离线后请求返回503 Service Unavailable；watchdog自动重启引擎；恢复后请求正常 |
| **测试脚本** | `tests/test_gateway/test_fault.py::test_engine_down_recovery` |

#### TC-GW-007: SSE流式转发完整性
| 字段 | 内容 |
|------|------|
| **优先级** | P0 |
| **前置条件** | 模型已加载，引擎正常 |
| **测试步骤** | 1. 发送stream=true请求<br>2. 收集所有SSE chunk<br>3. 验证最后一个chunk是否包含 `[DONE]` |
| **预期结果** | 流式逐字返回，无截断；SSE格式正确；结束标识 `data: [DONE]` |
| **测试脚本** | `tests/test_gateway/test_sse.py::test_stream_integrity` |

#### TC-GW-008: 非流式对话转发
| 字段 | 内容 |
|------|------|
| **优先级** | P0 |
| **测试步骤** | 1. 发送 stream=false 请求<br>2. 验证响应格式 |
| **预期结果** | 响符合OpenAI ChatCompletion格式，含choices/usage字段 |
| **测试脚本** | `tests/test_gateway/test_sse.py::test_non_stream_completion` |

#### TC-GW-009: 模型列表接口
| 字段 | 内容 |
|------|------|
| **优先级** | P1 |
| **测试步骤** | 1. GET `/v1/models`<br>2. 验证返回格式 |
| **预期结果** | 返回 `{object: "list", data: [...]}`，每个模型含 id/object/running/port 等字段 |
| **测试脚本** | `tests/test_gateway/test_v1_api.py::test_list_models` |

#### TC-GW-010: 客户端断开时上下文取消
| 字段 | 内容 |
|------|------|
| **优先级** | P0 |
| **测试步骤** | 1. 发起流式请求<br>2. 2秒后中断连接<br>3. 检查引擎侧请求是否终止 |
| **预期结果** | goroutine退出，并发槽位释放，无资源泄漏 |
| **测试脚本** | `tests/test_gateway/test_sse.py::test_client_disconnect_cleanup` |

#### TC-GW-011: 请求超时兜底
| 字段 | 内容 |
|------|------|
| **优先级** | P1 |
| **测试步骤** | 1. 配置request_timeout=30<br>2. 发送长时间推理请求<br>3. 观察超时行为 |
| **预期结果** | 超时后返回504 Gateway Timeout |
| **测试脚本** | `tests/test_gateway/test_fault.py::test_request_timeout` |

---

### 2.2 B端管理与配置同步层（Python 35000 + Go 35001）

#### TC-CFG-001: 配置修改与自动同步到Go网关
| 字段 | 内容 |
|------|------|
| **优先级** | P0 |
| **前置条件** | Python B端和Go网关均正常运行 |
| **测试步骤** | 1. PUT `/manage/config` 修改settings.concurrency_limit<br>2. GET Go网关 `/manage/config-sync` 查看运行时配置<br>3. 发送请求验证新并发限制生效 |
| **预期结果** | Python端config.yaml更新；Go网关配置同步；新并发限制立即生效 |
| **测试脚本** | `tests/test_config/test_config_sync.py::test_config_modify_sync` |

#### TC-CFG-002: 配置热重载（文件监听）
| 字段 | 内容 |
|------|------|
| **优先级** | P0 |
| **测试步骤** | 1. 手动修改 `go-vllm-api/configs/config.yaml`<br>2. 等待5秒<br>3. 检查Go网关运行时配置是否更新 |
| **预期结果** | fsnotify监听触发，配置自动热重载，无需重启 |
| **测试脚本** | `tests/test_config/test_config_sync.py::test_hot_reload_yaml` |

#### TC-CFG-003: 配置同步失败兜底（Go网关离线）
| 字段 | 内容 |
|------|------|
| **优先级** | P1 |
| **测试步骤** | 1. 关闭Go网关<br>2. 通过Python修改配置<br>3. 重启Go网关<br>4. 检查配置同步 |
| **预期结果** | Python本地配置保存成功；Go重启后通过心跳自动补同步 |
| **测试脚本** | `tests/test_config/test_config_sync.py::test_sync_failure_fallback` |

#### TC-CFG-004: 非法配置拦截
| 字段 | 内容 |
|------|------|
| **优先级** | P0 |
| **测试步骤** | 1. PUT `/manage/config` 提交 `settings.concurrency_limit=-1`<br>2. 检查响应和当前配置 |
| **预期结果** | 返回400错误，原有配置不被修改 |
| **测试脚本** | `tests/test_config/test_config_sync.py::test_invalid_config_rejected` |

#### TC-CFG-005: 配置版本一致性校验
| 字段 | 内容 |
|------|------|
| **优先级** | P1 |
| **测试步骤** | 1. 分别读取Python和Go网关配置<br>2. 对比关键配置项<br>3. 触发多次修改后再次对比 |
| **预期结果** | 双端关键配置项始终一致 |
| **测试脚本** | `tests/test_config/test_config_sync.py::test_config_version_consistency` |

#### TC-CFG-006: 竞态配置修改
| 字段 | 内容 |
|------|------|
| **优先级** | P2 |
| **测试步骤** | 1. 同时从2个会话修改不同配置项<br>2. 检查最终配置 |
| **预期结果** | 配置项粒度更新，互不覆盖（Python端使用dict.update而非全量覆盖） |
| **测试脚本** | `tests/test_config/test_config_sync.py::test_concurrent_config_update` |

---

### 2.3 推理引擎层

#### TC-ENG-001: 引擎热切换（vLLM→SGLang）
| 字段 | 内容 |
|------|------|
| **优先级** | P0 |
| **前置条件** | vLLM(8000)和SGLang(8001)同时启动 |
| **测试步骤** | 1. POST `/manage/switch/atomic` action=switch<br>2. 切换过程中持续发送请求<br>3. 查看Go网关上游地址 |
| **预期结果** | 切换无报错；网关上游地址更新；切换中请求不丢失；新请求转发到新引擎 |
| **测试脚本** | `tests/test_engine/test_engine_switch.py::test_engine_hot_switch` |

#### TC-ENG-002: 模型热切换
| 字段 | 内容 |
|------|------|
| **优先级** | P0 |
| **前置条件** | 模型A已加载运行 |
| **测试步骤** | 1. POST `/manage/switch/atomic` 切换到模型B<br>2. 监控GPU显存释放和加载<br>3. 切换完成后发送请求 |
| **预期结果** | 模型A卸载，显存释放；模型B加载成功；新请求使用模型B推理 |
| **测试脚本** | `tests/test_engine/test_model_switch.py::test_model_hot_switch` |

#### TC-ENG-003: 模型切换进度追踪
| 字段 | 内容 |
|------|------|
| **优先级** | P1 |
| **测试步骤** | 1. 发起模型切换<br>2. 循环GET `/manage/switch/status`<br>3. 观察phase变化 |
| **预期结果** | 状态从switching→completed，session_id和target_model正确 |
| **测试脚本** | `tests/test_engine/test_model_switch.py::test_switch_status_tracking` |

#### TC-ENG-004: 模型切换冲突拒绝
| 字段 | 内容 |
|------|------|
| **优先级** | P1 |
| **前置条件** | 正在进行模型切换 |
| **测试步骤** | 1. 切换进行中再次发起切换请求 |
| **预期结果** | 返回409 Conflict，提示"模型切换正在进行中" |
| **测试脚本** | `tests/test_engine/test_model_switch.py::test_switch_conflict_rejected` |

#### TC-ENG-005: 引擎进程崩溃自动恢复
| 字段 | 内容 |
|------|------|
| **优先级** | P0 |
| **测试步骤** | 1. kill掉vLLM进程<br>2. 观察systemd/supervisor是否自动重启<br>3. 检查Go网关health状态 |
| **预期结果** | 进程自动重启；health检查恢复healthy；恢复时间<30s |
| **测试脚本** | `tests/test_engine/test_fault_recovery.py::test_engine_crash_recovery` |

#### TC-ENG-006: 显存泄漏检测
| 字段 | 内容 |
|------|------|
| **优先级** | P1 |
| **测试步骤** | 1. 连续5次模型热切换<br>2. 每次切换前记录GPU显存占用<br>3. 最终对比显存 |
| **预期结果** | 显存占用无持续增长；每次卸载后显存基本恢复到初始水平 |
| **测试脚本** | `tests/test_engine/test_model_switch.py::test_memory_leak_after_switch` |

---

### 2.4 模型管理与文件系统层

#### TC-MDL-001: 正在使用的模型删除拦截
| 字段 | 内容 |
|------|------|
| **优先级** | P0 |
| **前置条件** | 模型A正在被引擎加载使用 |
| **测试步骤** | 1. POST `/manage/delete` 删除模型A |
| **预期结果** | 操作被拦截，返回错误提示；模型文件未被删除 |
| **测试脚本** | `tests/test_model/test_model_delete.py::test_delete_active_model_blocked` |

#### TC-MDL-002: 本地模型扫描
| 字段 | 内容 |
|------|------|
| **优先级** | P1 |
| **测试步骤** | 1. 在模型目录放入合法模型文件（含config.json+safetensors）<br>2. GET `/manage/scan`<br>3. 检查模型列表 |
| **预期结果** | 合法模型入库；非模型目录被忽略 |
| **测试脚本** | `tests/test_model/test_model_scan.py::test_local_model_scan` |

#### TC-MDL-003: 模型下载与进度追踪
| 字段 | 内容 |
|------|------|
| **优先级** | P1 |
| **测试步骤** | 1. POST `/manage/download` 提交下载任务<br>2. 循环查询下载进度 |
| **预期结果** | 下载后台执行；进度可追踪；完成后状态变ready |
| **测试脚本** | `tests/test_model/test_model_download.py::test_model_download_progress` |

#### TC-MDL-004: 磁盘空间不足拦截
| 字段 | 内容 |
|------|------|
| **优先级** | P1 |
| **测试步骤** | 1. 配置模型目录磁盘空间不足<br>2. 提交大模型下载任务 |
| **预期结果** | 下载被拦截，返回磁盘空间不足提示 |
| **测试脚本** | `tests/test_model/test_model_download.py::test_disk_full_download_blocked` |

#### TC-MDL-005: 模型删除（非活动模型）
| 字段 | 内容 |
|------|------|
| **优先级** | P1 |
| **前置条件** | 模型未被使用 |
| **测试步骤** | 1. 删除非活动模型<br>2. 检查本地目录和数据库 |
| **预期结果** | 文件被删除；数据库记录清除；列表无该模型 |
| **测试脚本** | `tests/test_model/test_model_delete.py::test_delete_inactive_model` |

#### TC-MDL-006: 模型路径不存在拒绝加载
| 字段 | 内容 |
|------|------|
| **优先级** | P0 |
| **测试步骤** | 1. 切换到路径不存在的模型 |
| **预期结果** | 返回404 "模型路径不存在" |
| **测试脚本** | `tests/test_model/test_model_switch.py::test_switch_nonexistent_path` |

---

### 2.5 全链路高可用

#### TC-HA-001: 全链路请求追踪（Request-ID）
| 字段 | 内容 |
|------|------|
| **优先级** | P1 |
| **测试步骤** | 1. 发送请求，检查响应头是否含Request-ID<br>2. 查看Go网关日志是否携带该ID |
| **预期结果** | 每个请求有唯一Request-ID；日志携带该ID可追溯 |
| **测试脚本** | `tests/test_ha/test_tracing.py::test_request_id_propagation` |

#### TC-HA-002: Redis缓存故障降级
| 字段 | 内容 |
|------|------|
| **优先级** | P1 |
| **前置条件** | Redis正常运行 |
| **测试步骤** | 1. 关闭Redis<br>2. 发送请求<br>3. 检查RateLimiter和CacheService行为 |
| **预期结果** | RateLimiter.redis==nil时直接放行；CacheService降级到内存缓存；服务不中断 |
| **测试脚本** | `tests/test_ha/test_redis_failure.py::test_redis_down_degradation` |

#### TC-HA-003: 网关进程崩溃恢复
| 字段 | 内容 |
|------|------|
| **优先级** | P0 |
| **测试步骤** | 1. kill掉Go网关进程<br>2. 重启后检查配置和模型状态 |
| **预期结果** | 配置从本地config.yaml恢复；模型状态通过心跳补同步；服务恢复 |
| **测试脚本** | `tests/test_ha/test_fault_recovery.py::test_gateway_crash_recovery` |

#### TC-HA-004: 并发槽位泄漏检测（Redis模式）
| 字段 | 内容 |
|------|------|
| **优先级** | P1 |
| **测试步骤** | 1. 发起100个并发请求后立即断开<br>2. 检查Redis中active_requests计数器 |
| **预期结果** | AcquireRequest/ReleaseRequest对称；计数器回落到0 |
| **测试脚本** | `tests/test_ha/test_slot_leak.py::test_concurrent_slot_leak_redis` |

---

### 2.6 安全与权限

#### TC-SEC-001: OpenAI接口无鉴权（当前状态验证）
| 字段 | 内容 |
|------|------|
| **优先级** | P0 |
| **测试步骤** | 1. 无API Key直接调用 `/v1/chat/completions`<br>2. 验证当前是否可访问 |
| **预期结果** | 当前无鉴权，记录为**安全风险**，需后续补充API Key校验 |
| **测试脚本** | `tests/test_security/test_auth.py::test_no_auth_current_state` |

#### TC-SEC-002: 网关管理接口IP白名单
| 字段 | 内容 |
|------|------|
| **优先级** | P1 |
| **测试步骤** | 1. 从非白名单IP调用 `/manage/*` 接口<br>2. 检查访问控制 |
| **预期结果** | 当前manage接口无IP白名单限制，记录为安全风险 |
| **测试脚本** | `tests/test_security/test_auth.py::test_manage_api_access` |

#### TC-SEC-003: 非法输入参数校验
| 字段 | 内容 |
|------|------|
| **优先级** | P0 |
| **测试步骤** | 1. 发送空model字段的请求<br>2. 发送超长context请求<br>3. 发送非JSON格式请求 |
| **预期结果** | 空model返回400；非JSON返回400；超长context被引擎拒绝 |
| **测试脚本** | `tests/test_security/test_input_validation.py::test_invalid_input_params` |

#### TC-SEC-004: 模型路径遍历防护
| 字段 | 内容 |
|------|------|
| **优先级** | P0 |
| **测试步骤** | 1. 提交包含 `../` 的模型路径<br>2. 提交包含 `/etc/passwd` 的路径 |
| **预期结果** | 路径遍历被拦截，返回400 |
| **测试脚本** | `tests/test_security/test_input_validation.py::test_path_traversal_blocked` |

#### TC-SEC-005: 模型下载源校验
| 字段 | 内容 |
|------|------|
| **优先级** | P2 |
| **测试步骤** | 1. 提交不可信源的下载地址<br>2. 检查是否被拦截 |
| **预期结果** | 仅允许huggingface/modelscope等可信源 |
| **测试脚本** | `tests/test_security/test_input_validation.py::test_untrusted_download_source` |

---

### 2.7 运维与可观测性

#### TC-OBS-001: GPU监控数据获取
| 字段 | 内容 |
|------|------|
| **优先级** | P1 |
| **测试步骤** | 1. GET `/manage/gpu`<br>2. GET `/manage/gpu/summary`<br>3. GET `/manage/gpu/enhanced` |
| **预期结果** | 返回GPU利用率、显存、温度等完整信息；enhanced含40+字段 |
| **测试脚本** | `tests/test_ops/test_monitoring.py::test_gpu_monitoring_data` |

#### TC-OBS-002: 健康检查接口
| 字段 | 内容 |
|------|------|
| **优先级** | P0 |
| **测试步骤** | 1. GET `/health` (Go网关)<br>2. GET `/health` (Python B端)<br>3. 对比返回数据 |
| **预期结果** | 两端均返回健康状态、GPU可用性、引擎连通性、健康评分 |
| **测试脚本** | `tests/test_ops/test_monitoring.py::test_health_check` |

#### TC-OBS-003: 健康评分告警
| 字段 | 内容 |
|------|------|
| **优先级** | P1 |
| **测试步骤** | 1. GET `/manage/health/alert`<br>2. 检查should_alert和alert_reasons |
| **预期结果** | health_score < 70时should_alert=true；alert_reasons列出具体原因 |
| **测试脚本** | `tests/test_ops/test_monitoring.py::test_health_alert` |

#### TC-OBS-004: WebSocket GPU推送
| 字段 | 内容 |
|------|------|
| **优先级** | P1 |
| **测试步骤** | 1. 连接WebSocket `/ws`<br>2. 接收10条消息<br>3. 验证数据格式 |
| **预期结果** | 每条消息包含GPU状态数据；推送间隔约3秒 |
| **测试脚本** | `tests/test_ops/test_websocket.py::test_ws_gpu_push` |

#### TC-OBS-005: Metrics采集与统计
| 字段 | 内容 |
|------|------|
| **优先级** | P1 |
| **测试步骤** | 1. 发送若干请求后GET `/manage/metrics`<br>2. 检查请求统计、token统计、延迟分布 |
| **预期结果** | metrics含请求总数/成功率/P99延迟/token用量等完整统计 |
| **测试脚本** | `tests/test_ops/test_monitoring.py::test_metrics_collection` |

#### TC-OBS-006: 结构化日志验证
| 字段 | 内容 |
|------|------|
| **优先级** | P2 |
| **测试步骤** | 1. GET `/manage/logs/test` (Python端)<br>2. 查看Go网关日志输出格式 |
| **预期结果** | Python端结构化日志含request_id/IP/耗时等字段；Go端Zap日志格式统一 |
| **测试脚本** | `tests/test_ops/test_monitoring.py::test_structured_logging` |

#### TC-OBS-007: 系统资源监控
| 字段 | 内容 |
|------|------|
| **优先级** | P1 |
| **测试步骤** | 1. GET `/manage/system/status` |
| **预期结果** | 返回CPU/内存/磁盘使用率、队列信息 |
| **测试脚本** | `tests/test_ops/test_monitoring.py::test_system_status` |

#### TC-OBS-008: 缓存状态与统计
| 字段 | 内容 |
|------|------|
| **优先级** | P2 |
| **测试步骤** | 1. GET `/manage/cache/status`<br>2. GET `/manage/cache/stats` |
| **预期结果** | 返回缓存命中率、更新器状态、各缓存键统计 |
| **测试脚本** | `tests/test_ops/test_monitoring.py::test_cache_status` |

---

## 三、性能测试用例

#### TC-PERF-001: 网关转发性能损耗
| 字段 | 内容 |
|------|------|
| **优先级** | P0 |
| **测试步骤** | 1. 直连vLLM引擎，记录QPS和延迟<br>2. 通过Go网关转发，记录QPS和延迟<br>3. 计算损耗比例 |
| **验收标准** | QPS差异≤5%；P99延迟增加≤10ms |
| **测试脚本** | `tests/test_perf/test_gateway_perf.py` |

#### TC-PERF-002: 高并发稳定性（30分钟）
| 字段 | 内容 |
|------|------|
| **优先级** | P0 |
| **测试步骤** | 100并发请求持续压测30分钟 |
| **验收标准** | 网关无崩溃/OOM/goroutine泄漏；内存波动≤20%；成功率100% |
| **测试脚本** | `tests/test_perf/test_stability.py` |

#### TC-PERF-003: 长连接稳定性（1小时）
| 字段 | 内容 |
|------|------|
| **优先级** | P1 |
| **测试步骤** | 100个并发流式长连接，每个1000 token |
| **验收标准** | 无断开/截断/卡顿；内存稳定无泄漏 |
| **测试脚本** | `tests/test_perf/test_long_connection.py` |

#### TC-PERF-004: 限流性能
| 字段 | 内容 |
|------|------|
| **优先级** | P1 |
| **测试步骤** | 1000 req/s持续压测 |
| **验收标准** | 限流准确；网关CPU≤2核；被限流请求快速响应 |
| **测试脚本** | `tests/test_perf/test_rate_limit_perf.py` |

---

## 四、稳定性与故障恢复测试

#### TC-STAB-001: 引擎崩溃自动恢复
| 字段 | 内容 |
|------|------|
| **优先级** | P0 |
| **测试步骤** | 1. kill vLLM进程<br>2. 观察watchdog自动重启<br>3. 检查恢复时间 |
| **验收标准** | 恢复时间≤30s；网关自动恢复转发 |
| **测试脚本** | `tests/test_stability/test_engine_recovery.py` |

#### TC-STAB-002: Redis故障降级
| 字段 | 内容 |
|------|------|
| **优先级** | P1 |
| **测试步骤** | 1. 关闭Redis<br>2. 发送请求<br>3. 检查降级行为 |
| **验收标准** | RateLimiter放行；Cache降级内存缓存；服务不中断 |
| **测试脚本** | `tests/test_stability/test_redis_degradation.py` |

#### TC-STAB-003: Python B端宕机Go网关独立运行
| 字段 | 内容 |
|------|------|
| **优先级** | P0 |
| **测试步骤** | 1. 关闭Python B端<br>2. Go网关独立转发请求<br>3. 重启Python B端后检查同步 |
| **验收标准** | Go网关独立可用；配置从本地加载；Python重启后自动补同步 |
| **测试脚本** | `tests/test_stability/test_python_down_go_alone.py` |

#### TC-STAB-004: 7x24小时长稳测试
| 字段 | 内容 |
|------|------|
| **优先级** | P2 |
| **验收标准** | 无崩溃/内存泄漏；成功率≥99.9%；无配置漂移 |

---

## 五、安全合规测试

#### TC-SEC-COMP-001: 权限最小化验证
- 所有高危操作需二次确认或鉴权
- 不同角色权限隔离
- 网关管理接口仅可信IP可访问（当前缺失，标记风险）

#### TC-SEC-COMP-002: 数据安全验证
- 配置文件/数据库文件权限检查
- 密码不明文存储
- 操作日志可追溯

#### TC-SEC-COMP-003: 输入安全验证
- 所有接口参数校验
- 无SQL注入/路径遍历漏洞
- 仅可信源下载模型

---

## 六、测试脚本目录结构

```
tests/
├── test_gateway/              # Go网关层测试
│   ├── test_sse.py            # SSE流式转发
│   ├── test_concurrency.py    # 并发控制
│   ├── test_rate_limit.py     # 限流
│   ├── test_fault.py          # 故障处理
│   └── test_v1_api.py         # OpenAI协议API
├── test_config/               # 配置同步测试
│   ├── test_config_sync.py    # 配置同步与热重载
├── test_engine/               # 引擎层测试
│   ├── test_engine_switch.py  # 引擎热切换
│   ├── test_model_switch.py   # 模型热切换
│   ├── test_fault_recovery.py # 故障恢复
├── test_model/                # 模型管理测试
│   ├── test_model_scan.py     # 模型扫描
│   ├── test_model_download.py # 模型下载
│   ├── test_model_delete.py   # 模型删除
├── test_ha/                   # 高可用测试
│   ├── test_tracing.py        # 链路追踪
│   ├── test_redis_failure.py  # Redis故障
│   ├── test_slot_leak.py      # 槽位泄漏
│   ├── test_fault_recovery.py # 故障恢复
├── test_security/             # 安全测试
│   ├── test_auth.py           # 鉴权
│   ├── test_input_validation.py # 输入校验
├── test_ops/                  # 运维可观测性测试
│   ├── test_monitoring.py     # 监控指标
│   ├── test_websocket.py      # WebSocket
├── test_perf/                 # 性能测试
│   ├── test_gateway_perf.py   # 网关性能
│   ├── test_stability.py      # 稳定性压测
│   ├── test_long_connection.py # 长连接
│   ├── test_rate_limit_perf.py # 限流性能
├── test_stability/            # 稳定性测试
│   ├── test_engine_recovery.py # 引擎恢复
│   ├── test_redis_degradation.py # Redis降级
│   ├── test_python_down_go_alone.py # B端宕机
└── conftest.py                # 测试配置与fixtures
```

---

## 七、上线前最终验收 Checklist

| # | 检查项 | 状态 |
|---|--------|------|
| 1 | 全链路功能验收全部通过，无P0阻塞性bug | ☐ |
| 2 | 性能压测达标，无性能瓶颈 | ☐ |
| 3 | 故障恢复演练全部通过，自愈能力符合预期 | ☐ |
| 4 | 监控告警体系搭建完成，核心指标都有监控和告警 | ☐ |
| 5 | 日志体系完善，可追溯性达标 | ☐ |
| 6 | 安全合规验收通过，无高危安全漏洞 | ☐ |
| 7 | 配置备份机制完善，可快速回滚 | ☐ |
| 8 | 生产环境资源充足，GPU/磁盘/带宽符合业务需求 | ☐ |
| 9 | 应急预案完善，运维人员熟悉故障处理流程 | ☐ |

---

## 八、当前已知安全风险（需后续修复）

| 风险ID | 描述 | 严重等级 | 建议修复时间 |
|--------|------|----------|------------|
| SEC-001 | OpenAI接口无鉴权，任意用户可调用 | 高 | 上线前必须修复 |
| SEC-002 | 网关管理接口无IP白名单+API Key双重鉴权 | 高 | 上线前必须修复 |
| SEC-003 | B端接口无登录鉴权 | 高 | 上线前必须修复 |
| SEC-004 | 模型下载无源校验 | 中 | 上线后1周内修复 |
| SEC-005 | 无操作审计日志持久化 | 中 | 上线后1周内修复 |
