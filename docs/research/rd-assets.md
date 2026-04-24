# 研发资产报告

> ai-os 项目资产盘点

**更新时间**: 2026-04-24

---

## 项目概览

4 个核心模块：frontend (Vue 3)、app-controller (FastAPI)、go-vllm-api (Go Gin)、aiclient2api (网关)

---

## 前端资产

### 组件
| 组件 | 路径 | 功能 |
|------|------|------|
| AgentChatWindow | src/components/AgentChatWindow.vue | Agent 聊天窗口 |
| GpuMetricsCard | src/components/cards/GpuMetricsCard.vue | GPU 指标卡片 |
| LineChart | src/components/LineChart.vue | 折线图 |
| Sidebar | src/components/Sidebar.vue | 侧边栏导航 |
| TopBar | src/components/TopBar.vue | 顶部栏 |
| ToastContainer | src/components/ToastContainer.vue | 消息通知 |

### 页面视图
| 视图 | 路径 | 功能 |
|------|------|------|
| Dashboard | src/views/Dashboard.vue | 仪表盘首页 |
| AgentView | src/views/AgentView.vue | Agent 对话页 |
| DocsView | src/views/DocsView.vue | 项目文档页 |
| ModelManagement | src/views/ModelManagement.vue | 模型管理页 |
| MonitorView | src/views/MonitorView.vue | GPU 监控页 |
| ModelBenchmarks | src/views/ModelBenchmarks.vue | 模型基准测试 |

### Composables
| Hook | 路径 | 功能 |
|------|------|------|
| useGPU | src/composables/useGPU.ts | GPU 状态监控 |
| useGPUHistory | src/composables/useGPUHistory.ts | GPU 历史数据 |
| useMarkdown | src/composables/useMarkdown.ts | Markdown 渲染 |
| useModels | src/composables/useModels.ts | 模型列表管理 |
| useSystemData | src/composables/useSystemData.ts | 系统数据 |
| useTokenHistory | src/composables/useTokenHistory.ts | Token 使用历史 |
| useTokenStats | src/composables/useTokenStats.ts | Token 统计 |

### Pinia Stores
| Store | 路径 | 功能 |
|-------|------|------|
| app | src/stores/app.ts | 应用状态（主题/Toast） |
| agentChat | src/stores/agentChat.ts | Agent 对话状态 |
| server | src/stores/server.ts | 服务器连接状态 |

### API
| 模块 | 路径 | 功能 |
|------|------|------|
| client | src/api/client.ts | Axios API 客户端封装 |

---

## Python 后端资产

### 核心模块
| 模块 | 路径 | 功能 |
|------|------|------|
| config | core/config.py | 配置管理 (Pydantic 验证) |
| logger | core/logger.py | 日志系统 |
| structured_logger | core/structured_logger.py | 结构化日志 |
| metrics | core/metrics.py | 性能指标 |
| monitor | core/monitor.py | 系统监控 |
| vllm_manager | core/vllm_manager.py | vLLM 模型管理 |
| vllm_metrics | core/vllm_metrics.py | vLLM 指标采集 |
| redis_client | core/redis_client.py | Redis 客户端 |
| scheduler | core/scheduler.py | 任务调度 |
| rate_limiter | core/rate_limiter.py | 限流器 |
| cache_service | core/cache_service.py | 缓存服务 |
| cache_updater | core/cache_updater.py | 缓存更新器 |
| config_watcher | core/config_watcher.py | 配置热更新 |
| websocket_manager | core/websocket_manager.py | WebSocket |
| prometheus_exporter | core/prometheus_exporter.py | Prometheus 导出 |
| sys_ctl | core/sys_ctl.py | 系统控制 |
| model_testing | core/model_testing.py | 模型测试 |
| llama_cpp_manager | core/llama_cpp_manager.py | llama.cpp 管理 |
| deps | core/deps.py | 依赖注入 |

---

## Go 后端资产

go-vllm-api: Gin 框架，vLLM 代理 + OpenAI 兼容接口 + WebSocket

```
internal/
├── config/      # 配置
├── handler/     # 请求处理 (manage/, v1/)
├── proxy/       # vLLM 代理
├── service/     # 业务逻辑
└── middleware/   # 中间件
```

---

> 更新于 2026-04-24
