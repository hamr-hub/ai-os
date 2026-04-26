# AI OS 代码架构文档

> **生成日期**: 2026-04-26  
> **文档目的**: 详细说明每个模块、每个文件、每段代码的作用，帮助开发者快速理解项目

---

## 整体架构概览

```
┌────────────────────────────────────────────────────────────────────┐
│                         用户浏览器                                 │
└──────────────┬─────────────────────────────────────────────────────┘
               │ HTTP/WebSocket
               ▼
┌───────────────────────────────────────┐
│  frontend/ (Vue 3 + Pinia + Router)   │  端口 30001 (开发) / 30000 (生产)
│  - 前端 UI 界面                        │  - 总览面板、模型调度、实时监控
│  - 状态管理 (Pinia)                    │  - 模型评测、AI Agent、系统文档
│  - 路由管理 (Vue Router)               │  - 服务连接管理、主题切换
│  - WebSocket 实时通信                  │  - GPU 状态仪表盘
└──────────────┬────────────────────────┘
               │ HTTP / WebSocket
               ▼
┌───────────────────────────────────────────────────────────────────┐
│                     aiclient2api/ (API 网关)                       │  端口 3000
│  - API 路由转发：将 OpenAI 协议请求转发到后端服务                   │
│  - 用户鉴权：验证用户身份和权限                                    │
│  - 负载均衡：在多个后端服务间分配请求                              │
│  - Token 管理：追踪和统计 Token 使用量                             │
│  - 插件系统：支持功能扩展                                          │
└──────────────┬────────────────────────────────────────────────────┘
               │
       ┌───────┴───────┐
       ▼               ▼
┌──────────────┐  ┌──────────────────┐
│ app-         │  │ go-vllm-api/     │  端口 35001
│ controller/  │  │ (Go + Gin)       │
│ (Python)     │  │ - vLLM 模型代理   │
│ 端口 35000   │  │ - 模型调度        │
│              │  │ - 性能优化        │
│ - 模型管理   │  │ - 并发处理        │
│ - 服务调度   │  │ - 流式响应        │
│ - GPU 监控   │  │                  │
│ - 系统控制   │  │                  │
│ - WebSocket  │  │                  │
│ - 配置管理   │  │                  │
│ - 缓存系统   │  │                  │
│ - 指标收集   │  │                  │
└──────────────┘  └──────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│         底层基础设施                │
│  - vLLM / llama.cpp 模型服务        │
│  - Redis 缓存                       │
│  - Prometheus 监控                  │
│  - GPU (NVIDIA NVML)                │
└─────────────────────────────────────┘
```

---

## 模块一：frontend/ - Vue 3 前端应用

**技术栈**: Vue 3 + TypeScript + Pinia + Vue Router + TailwindCSS  
**端口**: 开发 30001 / 生产 30000  
**作用**: 提供 AI 模型管理系统的 Web 用户界面

### 目录结构

```
frontend/src/
├── main.ts                    # 应用入口
├── App.vue                    # 根组件
├── router/
│   └── index.ts              # 路由配置
├── stores/
│   ├── app.ts                # 应用级状态（主题、Toast、侧边栏）
│   └── server.ts             # 服务器连接状态管理
├── components/
│   ├── TopBar.vue            # 顶部导航栏
│   ├── Sidebar.vue           # 左侧边栏
│   └── ToastContainer.vue    # Toast 消息提示容器
├── views/
│   ├── Dashboard.vue         # 总览面板
│   ├── MonitorView.vue       # 实时监控
│   ├── ModelManagement.vue   # 模型调度管理
│   ├── ModelBenchmarks.vue   # 模型评测
│   ├── AgentView.vue         # AI Agent 界面
│   └── DocsView.vue          # 系统文档
├── composables/
│   └── useGPU.ts             # GPU 状态获取 Composable
├── utils/
│   ├── connection.ts         # 连接工具函数
│   └── format.ts             # 数据格式化工具
└── style.css                 # 全局样式变量
```

### 核心文件详解

#### 1. `main.ts` - 应用入口

```
作用:
├── 创建 Vue 3 应用实例
├── 创建 Pinia 状态管理实例
├── 注册全局错误处理器（捕获组件运行时错误）
├── 注册全局警告处理器（捕获 Vue 警告）
├── 注册未捕获 Promise rejection 监听器
└── 挂载应用到 DOM #app 元素

执行流程:
1. import 模块 → 2. createApp → 3. createPinia → 4. 配置错误处理 → 5. use 插件 → 6. mount
```

**代码作用说明**:
- `createApp(App)`: 创建 Vue 应用实例，App 是根组件
- `createPinia()`: 创建状态管理实例，用于全局状态共享
- `app.config.errorHandler`: 全局错误拦截，防止组件崩溃影响整个应用
- `app.config.warnHandler`: 开发时警告信息输出
- `unhandledrejection`: 监听未处理的 Promise 拒绝，防止静默失败

#### 2. `App.vue` - 根组件

```
作用:
├── 定义应用整体布局结构
│   ├── TopBar (顶栏): 服务器状态、连接管理
│   ├── Sidebar (侧边栏): 导航菜单、GPU 状态、主题切换
│   └── RouterView (主内容区): 根据路由动态渲染页面
├── 组件挂载时初始化
│   ├── 初始化主题（从 localStorage 读取或设置默认值）
│   ├── 恢复服务器连接配置
│   └── 检查后端服务连接状态
└── 提供页面切换过渡动画（淡入淡出 + 滑动效果）

布局示意图:
┌────────────────────────────────────┐
│           TopBar (顶栏)             │
├──────────┬─────────────────────────┤
│          │                         │
│ Sidebar  │     RouterView          │
│ (侧边栏) │   (动态页面内容)          │
│          │                         │
└──────────┴─────────────────────────┘
```

**代码作用说明**:
- `store.initTheme()`: 初始化主题，支持 light/dark/system 三种模式
- `serverStore.initFromStorage()`: 从 localStorage 恢复上次连接的服务器配置
- `serverStore.checkConnection()`: 检查后端服务是否可用（ping 管理接口和推理接口）
- `mainMargin` computed: 根据侧边栏折叠状态计算主内容区左边距
- `<transition name="page">`: 页面切换时的淡入淡出 + 滑动动画

#### 3. `router/index.ts` - 路由配置

```
作用: 定义所有前端页面路由及其懒加载

路由列表:
├── / (dashboard)          → 总览面板（系统概览、模型状态、资源使用）
├── /monitor               → 实时监控（GPU/CPU/内存/磁盘指标图表）
├── /models                → 模型调度（模型启动/停止/切换、预加载管理）
├── /agent                 → AI Agent（智能代理交互界面）
├── /benchmarks            → 模型评测（模型性能对比测试）
├── /docs                  → 系统文档
├── /docs/:slug            → 动态文档页面
└── /* (not-found)         → 404 重定向到总览面板

特性:
├── 使用 createWebHistory() 启用 HTML5 History 模式
├── 所有组件都使用动态 import () 实现路由级代码分割
└── 通配符路由 /* 捕获所有未匹配路径
```

#### 4. `stores/app.ts` - 应用级状态管理

```
作用: 管理全局应用状态

管理状态:
├── toasts: ToastMessage[]        → 消息提示队列
├── sidebarCollapsed: boolean     → 侧边栏是否折叠
├── theme: 'light' | 'dark' | 'system' → 主题设置
├── actualTheme: 'light' | 'dark'     → 实际渲染主题（处理 system 模式）

提供方法:
├── setTheme()          → 设置主题并保存到 localStorage
├── initTheme()         → 初始化主题（从 localStorage 读取）
├── addToast()          → 添加消息提示
├── removeToast()       → 移除指定消息
├── toggleSidebar()     → 切换侧边栏折叠状态
├── success()           → 显示成功消息
├── error()             → 显示错误消息
├── warning()           → 显示警告消息
└── info()              → 显示信息消息

主题切换逻辑:
├── theme = 'system'  → actualTheme = 跟随系统深色/浅色模式
├── theme = 'dark'    → actualTheme = 'dark'
├── theme = 'light'   → actualTheme = 'light'
└── 监听系统模式变化，自动更新 actualTheme
```

**关键代码段说明**:
- `updateActualTheme()`: 根据当前主题设置计算实际渲染主题。当主题为 system 时，通过 `window.matchMedia('(prefers-color-scheme: dark)')` 判断系统模式
- `watch(theme, updateActualTheme)`: 监听主题变化，自动触发更新
- `addToast()`: 添加消息到队列，设置自动消失定时器
- `removeToast()`: 从队列中移除指定消息

#### 5. `stores/server.ts` - 服务器连接状态管理

```
作用: 管理后端服务连接，支持多服务器切换和健康检查

管理状态:
├── activeUrl: string              → 当前连接的服务器 URL
├── backendType: 'go' | 'python' | 'auto' → 后端类型
├── connectionStatus: 'online' | 'offline' | 'checking' | 'degraded'
├── lastCheckedAt: number          → 上次检查时间
├── lastErrorMessage: string       → 最后错误信息
├── history: ServerHistoryEntry[]  → 连接历史（最多 10 条）
└── connectionDetails              → 连接详细信息（管理接口/推理接口状态）

计算属性:
├── manageBase                     → 管理 API 基础路径 (/manage)
├── v1Base                         → v1 API 基础路径 (/v1)
├── healthUrl                      → 健康检查 URL
├── manageHealthUrl                → 管理接口健康检查 URL
├── inferenceHealthUrl             → 推理接口健康检查 URL
└── currentLabel                   → 当前服务器显示名称

核心方法:
├── probeEndpoint()        → 探测单个端点是否可用（带超时控制）
├── checkConnection()      → 检查连接状态（管理接口 + 推理接口并行检查）
├── switchServer()         → 切换服务器（保存配置 + 同步历史）
├── removeHistory()        → 移除历史记录
└── initFromStorage()      → 从 localStorage 恢复配置

连接状态定义:
├── online     → 管理接口和推理接口都正常
├── degraded   → 只有一个接口正常，另一个异常
├── checking   → 正在检查中
└── offline    → 两个接口都不可用
```

**关键代码段说明**:
- `probeEndpoint()`: 使用 `fetch` 加 `AbortController` 实现带超时的 HTTP 请求检测
- `checkConnection()`: 并行检查管理接口和推理接口，支持重试（最多 2 次），指数退避延迟
- `syncHistory()`: 维护连接历史，新连接添加到头部，按最后使用时间排序，保留最多 10 条
- `saveConfig()` / `saveHistory()`: 持久化到 localStorage

#### 6. `components/TopBar.vue` - 顶部导航栏

```
作用: 显示当前服务器连接状态，提供连接管理功能

功能模块:
├── 左侧: 服务器状态显示
│   ├── 连接状态徽章 (online/checking/degraded/offline)
│   ├── 服务器 URL 显示
│   └── 后端类型标签 (GO/PY/AUTO)
├── 右侧: 连接管理
│   ├── 刷新连接状态按钮
│   └── 切换服务按钮（展开下拉面板）
└── 下拉面板:
    ├── 当前连接状态卡片
    ├── 手动连接表单（URL 输入 + 后端类型选择）
    ├── 本地代理快捷按钮
    └── 连接历史列表（点击切换、删除）

状态徽章颜色:
├── online  → 绿色 (#22c55e)
├── checking → 琥珀色 (#f59e0b)
├── degraded → 橙色 (#f97316)
└── offline → 红色 (#ef4444)

后端类型颜色:
├── go     → 青色 (#06b6d4)
├── python → 琥珀色 (#f59e0b)
└── auto   → 紫色 (#8b5cf6)
```

**关键代码段说明**:
- `statusConfig` computed: 根据连接状态返回对应的样式配置（颜色、图标、边框等）
- `backendConfig` computed: 根据后端类型返回对应的样式配置
- `applyServer()`: 应用手动输入的服务器配置，切换后自动检查连接
- `useHistory()`: 使用历史记录中的服务器配置
- `useLocalProxy()`: 切换到本地代理模式（清空 URL）
- `handleClickOutside()`: 点击面板外部时自动关闭下拉面板

#### 7. `components/Sidebar.vue` - 左侧边栏

```
作用: 应用导航菜单和系统状态展示

功能区域:
├── Logo 区域: 应用标识 + 版本号（点击跳转到总览面板）
├── 导航菜单:
│   ├── 核心控制
│   │   ├── 总览面板 (Dashboard)
│   │   ├── 模型调度 (ModelManagement)
│   │   ├── 模型评测 (ModelBenchmarks)
│   │   └── AI Agent
│   └── 数据监控
│       ├── 实时性能 (Monitor)
│       └── 系统文档 (Docs)
├── GPU 状态组件: 显示 GPU 利用率和显存使用（折叠时隐藏）
└── 操作按钮:
    ├── 主题切换 (light/dark/system)
    ├── 侧边栏折叠/展开
    └── 系统安全

侧边栏状态:
├── 展开: 宽度 var(--sidebar-width)，显示完整导航项文字
└── 折叠: 宽度 var(--sidebar-collapsed-width)，仅显示图标

动画效果:
├── 导航项激活状态: 左侧发光条动画
├── 侧边栏折叠/展开: 平滑宽度过渡
└── 文字显示/隐藏: fade 淡入淡出
```

**关键代码段说明**:
- `groups` 数组: 定义导航菜单的分组和项，包含名称、标签、图标
- `isActive()`: 判断当前路由是否匹配导航项
- `cycleTheme()`: 循环切换主题 (light → dark → system → light)
- `gpuInfo` computed: 从 useGPU composable 获取 GPU 状态摘要
- 导航项样式: 激活状态有渐变背景 + 边框 + 发光条效果

---

## 模块二：app-controller/ - Python FastAPI 后端

**技术栈**: FastAPI + Python + uvicorn + httpx + pydantic  
**端口**: 35000  
**作用**: AI 模型管理的核心控制器，负责模型调度、服务管理、监控等

### 目录结构

```
app-controller/
├── main.py                    # 应用入口，FastAPI 初始化
├── config.yaml                # 模型配置文件
├── core/                      # 核心业务逻辑
│   ├── config.py             # 配置解析与验证
│   ├── config_watcher.py     # 配置文件监听与热重载
│   ├── scheduler.py          # 模型调度器
│   ├── vllm_manager.py       # vLLM 模型管理器
│   ├── llama_cpp_manager.py  # llama.cpp 模型管理器
│   ├── gpu_monitor.py        # GPU 状态监控
│   ├── monitor.py            # 系统监控（CPU/内存/磁盘）
│   ├── cache_service.py      # 缓存服务（内存 + Redis）
│   ├── cache_updater.py      # 缓存更新服务
│   ├── redis_client.py       # Redis 客户端封装
│   ├── websocket_manager.py  # WebSocket 连接管理
│   ├── sys_ctl.py            # 系统服务控制（systemd）
│   ├── metrics.py            # 指标收集与统计
│   ├── prometheus_exporter.py# Prometheus 指标导出
│   ├── structured_logger.py  # 结构化日志
│   ├── logger.py             # 基础日志
│   ├── rate_limiter.py       # 请求限流
│   ├── model_testing.py      # 模型测试框架
│   └── deps.py               # 依赖注入（全局实例管理）
├── routes/                    # API 路由
│   ├── v1.py                 # OpenAI 兼容 API (v1/chat/completions 等)
│   ├── manage.py             # 管理 API (/manage/*)
│   ├── health.py             # 健康检查 API (/health)
│   ├── websocket.py          # WebSocket API (/ws)
│   └── agent.py              # Agent API (/agent/*)
├── api/                       # 外部接口集成
│   ├── aiclient_interface.py # aiclient2api 集成
│   └── proxy_vllm.py         # vLLM 代理
├── middleware/                # HTTP 中间件
│   ├── error_handler.py      # 错误处理中间件
│   ├── rate_limit.py         # 限流中间件
│   └── timeout_handler.py    # 超时处理中间件
├── schemas/                   # 数据模型定义
│   ├── chat.py               # 聊天请求/响应模型
│   ├── image.py              # 图像模型
│   ├── embedding.py          # Embedding 模型
│   ├── service.py            # 服务控制模型
│   └── test.py               # 测试模型
├── tools/                     # 工具定义
│   ├── definitions.py        # 工具定义
│   └── executor.py           # 工具执行器
└── scripts/                   # 运维脚本
    └── switch_vllm_model_aiclient.py # 模型切换脚本
```

### 核心文件详解

#### 1. `main.py` - 应用入口

```
作用: FastAPI 应用初始化和生命周期管理

加载顺序:
1. 导入核心依赖（scheduler, gpu_monitor 等）
2. 注册配置变更回调
3. 定义中间件
4. 注册路由
5. 注册异常处理器
6. 启动服务

生命周期:
├── startup_event()
│   ├── 创建 HTTP 客户端（普通请求 + 流式请求）
│   ├── 连接 Redis（成功后启动缓存更新器）
│   ├── 安装信号处理器（SIGHUP 热重载配置）
│   ├── 启动配置监听
│   ├── 预加载配置的模型
│   └── 启动后台任务循环
│       ├── GPU 缓存更新循环
│       ├── 状态广播循环（WebSocket）
│       ├── 历史记录保存循环
│       └── 健康状态监听循环
└── shutdown_event()
    ├── 停止配置监听
    ├── 停止缓存更新器
    ├── 取消所有后台任务
    ├── 关闭 HTTP 客户端
    ├── 清理 llama.cpp 进程
    └── 清理系统管理进程

中间件链（按执行顺序）:
├── CORSMiddleware      → 跨域资源共享（允许所有来源）
├── RateLimitMiddleware → 请求限流（100 请求/60 秒）
├── TimeoutHandlerMiddleware → 超时处理（60 秒超时）
└── request_tracking_middleware → 请求追踪（生成 request_id，记录日志和指标）

路由注册:
├── v1_router           → /v1/* (OpenAI 兼容 API)
├── manage_router       → /manage/* (管理 API)
├── integration_router  → /api/v1/* (集成 API)
├── health_router       → /health (健康检查)
├── websocket_router    → /ws (WebSocket)
└── agent_router        → /agent/* (Agent 功能)
```

**中间件代码详解**:

```python
async def request_tracking_middleware(request: Request, call_next):
    """
    请求追踪中间件：
    1. 为每个请求生成唯一 UUID (request_id)
    2. 将 request_id 附加到请求对象和响应头
    3. 记录请求开始时间
    4. 处理请求后计算耗时
    5. 同时写入三种记录：
       - structured_logger: 结构化日志（JSON 格式）
       - prometheus: Prometheus 指标（用于监控系统）
       - metrics: 内部指标收集（用于前端展示）
    """
```

**后台任务循环详解**:

```python
async def broadcast_status_loop():
    """
    状态广播循环（每 2 秒执行一次）：
    1. 获取 GPU 状态摘要
    2. 获取所有可用模型
    3. 构建每个模型的状态信息：
       - running: 是否运行中
       - port: 服务端口
       - service: 服务类型 (vllm/llama_cpp)
       - active_requests: 当前活跃请求数
       - preloaded: 是否预加载
       - last_used: 上次使用时间
    4. 通过 WebSocket 广播给所有连接的前端
    """

async def save_history_loop():
    """
    历史记录保存循环（每 5 秒执行一次）：
    1. 保存 GPU 历史数据（用于趋势图）
    2. 保存系统监控历史（CPU/内存/磁盘）
    3. 保存 Token 使用历史（用于统计）
    """
```

#### 2. `core/config.py` - 配置解析与验证

```
作用: 定义配置数据结构，解析 YAML 配置文件

数据模型（Pydantic）:
├── RedisConfig         → Redis 连接配置（host, port, db）
├── ModelConfig         → 单个模型配置
│   ├── service: 服务类型 (vllm/llama_cpp)
│   ├── port: 服务端口
│   ├── required_memory: 所需内存（如 "8GB"）
│   ├── preload: 是否预加载
│   ├── keep_alive: 是否保持活跃
│   ├── model_path: 模型文件路径
│   ├── supports_images: 是否支持图像输入
│   ├── supports_tool_calling: 是否支持工具调用
│   ├── supports_image_generation: 是否支持图像生成
│   └── llama.cpp 专用参数（n_gpu_layers, ctx_size, n_threads）
├── QueueConfig         → 请求队列配置
├── PriorityConfig      → 优先级配置
├── RecoveryConfig      → 服务恢复配置
├── SettingsConfig      → 全局设置
│   ├── concurrency_limit: 并发限制
│   ├── min_available_memory: 最小可用内存
│   ├── request_timeout: 请求超时
│   ├── model_start_timeout: 模型启动超时
│   ├── idle_timeout: 空闲超时
│   ├── gpu_memory_utilization: GPU 内存利用率
│   └── queue/priority/recovery/redis 子配置
├── LlamaCppConfig      → llama.cpp 全局配置
└── AppConfig           → 根配置（models + settings + vllm + llama_cpp）

工具函数:
├── parse_memory_size() → 解析内存大小字符串（如 "8GB" → 8589934592 字节）
├── load_config()       → 从 YAML 文件加载配置，支持环境变量覆盖
└── validate_config()   → 验证配置合法性，返回错误列表
```

**配置加载流程**:
1. 读取 YAML 文件
2. 解析为字典
3. 检查 settings.redis，如果不存在则从环境变量读取
4. 环境变量覆盖（REDIS_HOST, REDIS_PORT, REDIS_DB）
5. 使用 Pydantic 验证并转换为 AppConfig 对象

#### 3. `routes/v1.py` - OpenAI 兼容 API

```
作用: 提供与 OpenAI API 兼容的接口，使现有 OpenAI 客户端可直接使用

API 端点:
├── GET  /v1/models                    → 列出所有可用模型
├── GET  /v1/models/{model_name}       → 获取单个模型详情
├── POST /v1/chat/completions          → 聊天补全（核心推理接口）
├── POST /v1/images/generations        → 图像生成
├── POST /v1/embeddings                → Embedding 向量生成
├── POST /v1/images/validate           → 图像验证
├── POST /v1/images/upload             → 图像上传
├── GET  /v1/images/info               → 图像服务信息
├── GET  /v1/status                    → API 状态
├── POST /v1/test/model/{name}         → 测试单个模型
├── GET  /v1/test/report/{name}        → 获取模型测试报告
├── GET  /v1/test/reports              → 获取所有测试报告
├── POST /v1/test/comparative          → 对比分析多个模型
├── POST /v1/test/model/{name}/switch-and-test → 切换并测试模型
└── DELETE /v1/test/reports            → 清空测试报告

聊天补全请求处理流程:
1. 接收 ChatCompletionRequest 请求体
2. 如果未指定模型，使用默认模型
3. 检查模型可用性
4. 如果是多模态请求，验证模型是否支持图像
5. 获取并发槽位（或排队等待）
6. 检查 GPU 内存是否充足
7. 确保模型已启动（必要时自动启动）
8. 构建后端 URL
9. 如果是流式请求 (stream=true):
   - 建立流式连接
   - 逐块转发 SSE 数据
   - 添加心跳检测
   - 处理 [DONE] 结束标志
   - 记录 token 使用量
10. 如果是非流式请求:
    - 发送请求到后端
    - 等待完整响应
    - 记录 token 使用量
11. 释放并发槽位
12. 记录请求指标
```

**流式响应处理详解**:

```python
async def generate():
    """
    流式响应生成器（SSE - Server-Sent Events）：
    1. 逐行读取后端 vLLM 的 SSE 响应
    2. 心跳机制：每 10 秒无活动时发送 ": heartbeat" 保持连接
    3. 处理 "data: " 前缀的行：
       - 解析 JSON 数据
       - 替换 id 为统一生成的 chatcmpl-xxx
       - 替换 model 为前端请求的模型名（而非后端内部名）
       - 如果遇到 "usage" 字段，记录 token 用量
       - 如果遇到 "[DONE]"，发送完成标志
    4. 异常处理：
       - 超时：发送超时错误消息
       - HTTP 错误：发送错误消息
       - 其他异常：发送内部错误消息
    5. finally 块：关闭后端响应连接
    """
```

#### 4. `routes/manage.py` - 管理 API

```
作用: 提供系统管理接口，用于模型管理、系统监控、配置管理等

API 端点分类:

GPU 管理:
├── GET  /manage/gpu                    → GPU 状态（详细）
├── GET  /manage/gpu/summary            → GPU 状态（摘要）
├── GET  /manage/gpu/history            → GPU 历史数据
├── GET  /manage/gpu/processes          → GPU 进程列表
├── GET  /manage/gpu/enhanced           → GPU 增强信息（NVML）
├── GET  /manage/vllm/metrics           → vLLM 指标
└── POST /manage/gpu/history/config     → 配置 GPU 历史

模型管理:
├── GET  /manage/models                 → 所有模型状态
├── GET  /manage/models/summary         → 模型摘要
├── POST /manage/models/{name}/start    → 启动模型
├── POST /manage/models/{name}/stop     → 停止模型
├── POST /manage/models/{name}/switch   → 切换模型（带自检）
├── GET  /manage/default-model          → 获取默认模型
├── POST /manage/default-model/{name}   → 设置默认模型
└── DELETE /manage/default-model        → 清除默认模型

预加载管理:
├── GET  /manage/preload                → 预加载状态
├── POST /manage/preload/{name}         → 预加载模型
├── POST /manage/preload/{name}/enable  → 启用预加载
├── POST /manage/preload/{name}/disable → 禁用预加载
├── GET  /manage/preload/all            → 预加载所有模型
└── GET  /manage/preload/status         → 详细预加载状态

队列与指标:
├── GET  /manage/queue                  → 队列状态
├── GET  /manage/token/stats            → Token 统计
├── GET  /manage/metrics                → 指标数据
├── POST /manage/metrics/reset          → 重置指标
└── GET  /manage/health/alert           → 健康告警状态

缓存管理:
├── GET  /manage/cache/status           → 缓存状态
├── POST /manage/cache/refresh          → 刷新缓存
└── GET  /manage/cache/stats            → 缓存统计

配置管理:
├── GET  /manage/config                 → 获取配置
├── PUT  /manage/config                 → 更新配置
├── POST /manage/config/reload          → 重载配置

服务控制:
├── GET  /manage/service/status         → 服务状态
├── POST /manage/service/start          → 启动服务
├── POST /manage/service/stop           → 停止服务
└── POST /manage/service/restart        → 重启服务

系统监控:
├── GET  /manage/system/status          → 系统状态（CPU/内存/磁盘）
├── GET  /manage/system/history         → 系统历史
├── GET  /manage/token/history          → Token 历史

Redis:
├── GET  /manage/redis/health           → Redis 健康检查
├── GET  /manage/redis/keys             → Redis 键查询
└── DELETE /manage/redis/flush          → 清空 Redis

综合:
├── GET  /manage/monitor/all            → 监控数据汇总
├── GET  /manage/llama_cpp/models       → llama.cpp 模型列表
├── GET  /manage/llama_cpp/status       → llama.cpp 状态

集成 API (/api/v1):
├── GET  /api/v1/status                 → 节点集成状态
└── GET  /api/v1/models/{name}/info     → 模型信息
```

**缓存策略说明**:
- 所有 GET 接口都使用内存缓存（`cache_service`）
- 每个接口有独立的缓存 key（如 `api:manage:gpu:status`）
- 缓存 TTL 根据数据更新频率设置（3-60 秒不等）
- 模型状态变更后调用 `_clear_model_caches()` 清除相关缓存
- `refresh` 参数可强制刷新缓存

#### 5. `core/deps.py` - 依赖注入

```
作用: 创建和管理全局单例实例，供其他模块使用

创建的实例:
├── config_watcher        → 配置监听器
├── scheduler             → 模型调度器
├── gpu_monitor           → GPU 监控器
├── system_monitor        → 系统监控器
├── ws_manager            → WebSocket 管理器
├── metrics               → 指标收集器
├── prometheus            → Prometheus 导出器
├── cache_service         → 缓存服务
├── cache_updater         → 缓存更新器
├── redis_client          → Redis 客户端
├── structured_logger     → 结构化日志器
├── model_tester          → 模型测试框架
├── sys_controller        → 系统服务控制器
├── rate_limiter          → 限流器
└── 各种超时和限制常量

初始化顺序:
1. 加载配置 → 2. 创建 Redis 客户端 → 3. 创建缓存服务 → 4. 创建各组件
```

---

## 模块三：go-vllm-api/ - Go Gin 后端

**技术栈**: Go + Gin + zap 日志  
**端口**: 35001  
**作用**: 高性能的 vLLM 代理服务，处理并发请求和流式响应

### 目录结构

```
go-vllm-api/
├── cmd/server/
│   └── main.go                # Go 应用入口
├── internal/
│   ├── config/
│   │   ├── config.go          # 配置解析
│   │   └── watcher.go         # 配置监听
│   ├── proxy/
│   │   └── vllm.go            # vLLM 代理核心
│   ├── service/
│   │   ├── scheduler.go       # 模型调度
│   │   ├── vllm_manager.go    # vLLM 管理
│   │   ├── llama_cpp_manager.go # llama.cpp 管理
│   │   ├── gpu_monitor.go     # GPU 监控
│   │   ├── cache.go           # 缓存服务
│   │   ├── cache_updater.go   # 缓存更新
│   │   ├── ws_manager.go      # WebSocket 管理
│   │   ├── metrics_collector.go # 指标收集
│   │   ├── model_testing.go   # 模型测试
│   │   ├── sysctl.go          # 系统控制
│   │   ├── system.go          # 系统监控
│   │   └── rate_limiter.go    # 限流器
│   ├── handler/
│   │   ├── v1/chat.go         # v1 API 处理器
│   │   ├── manage/manage.go   # 管理 API 处理器
│   │   ├── health/health.go   # 健康检查处理器
│   │   └── ws/ws.go           # WebSocket 处理器
│   ├── middleware/
│   │   ├── cors.go            # CORS 中间件
│   │   ├── tracking.go        # 请求追踪
│   │   ├── ratelimit.go       # 限流中间件
│   │   └── error.go           # 错误处理
│   ├── model/                 # 数据模型
│   ├── repository/            # 数据访问层
│   │   └── redis.go           # Redis 操作
│   ├── pkg/                   # 公共包
│   │   ├── logger/logger.go   # 日志
│   │   ├── prometheus/        # Prometheus
│   │   ├── response/          # 响应封装
│   │   └── utils/             # 工具函数
│   └── tools/                 # Agent 工具
└── configs/
    └── config.yaml            # 配置文件
```

### 核心文件详解

#### 1. `cmd/server/main.go` - Go 应用入口

```
作用: Gin 应用初始化、服务启动和生命周期管理

启动流程:
1. 解析命令行参数（--port, --config, --log-dir）
2. 初始化 zap 日志
3. 加载 YAML 配置
4. 创建 Redis 连接
5. 初始化核心服务：
   ├── cacheService    → 缓存服务
   ├── gpuMonitor      → GPU 监控
   ├── sysCtl          → 系统控制
   ├── vllmManager     → vLLM 管理
   ├── llamaCppMgr     → llama.cpp 管理
   ├── scheduler       → 调度器
   ├── metricsCollector→ 指标收集
   ├── promExporter    → Prometheus 导出
   ├── vllmProxy       → vLLM 代理
   └── wsManager       → WebSocket 管理
6. 启动 GPU 监控
7. 启动缓存更新器（如果 Redis 可用）
8. 启动配置监听
9. 预加载模型
10. 启动状态广播循环
11. 配置 Gin 中间件
12. 注册路由
13. 启动 HTTP 服务
14. 等待信号（SIGINT, SIGTERM, SIGHUP）

中间件链（按执行顺序）:
├── gin.Recovery()              → Panic 恢复
├── middleware.CORS()           → 跨域处理
├── middleware.RequestID()      → 请求 ID 生成
├── middleware.RequestTracking()→ 请求追踪
├── middleware.ErrorHandler()   → 错误处理
└── middleware.RateLimit()      → 限流

信号处理:
├── SIGHUP   → 热重载配置
├── SIGINT   → 优雅关闭
└── SIGTERM  → 优雅关闭

关闭流程:
1. 停止配置监听
2. 停止缓存更新器
3. 停止 GPU 监控
4. 清理所有 llama.cpp 进程
5. 优雅关闭 HTTP 服务（10 秒超时）
```

**与 Python 版本的差异**:
- Go 版本使用 Goroutine 处理并发，性能更高
- 使用 `http.Transport` 连接池管理，复用连接
- 流式响应使用 channel 传递事件，而非异步生成器
- 配置加载使用 `sync.RWMutex` 保护并发读写

#### 2. `proxy/vllm.go` - vLLM 代理核心

```
作用: 将请求转发到 vLLM 后端服务

HTTP 客户端配置:
├── requestClient（普通请求）
│   ├── Timeout: 60s
│   ├── MaxIdleConns: 200
│   ├── MaxIdleConnsPerHost: 50
│   └── IdleConnTimeout: 90s
└── streamClient（流式请求）
    ├── Timeout: 0（无超时，支持长连接）
    ├── MaxIdleConns: 200
    ├── MaxIdleConnsPerHost: 50
    ├── IdleConnTimeout: 90s
    └── ResponseHeaderTimeout: 120s

提供的方法:
├── ChatCompletion()         → 普通聊天补全请求
├── StreamChatCompletion()   → 流式聊天补全请求（返回 channel）
├── ListModels()             → 列出模型
├── Embeddings()             → Embedding 请求
├── PostEndpoint()           → 通用 POST 请求
└── WaitUntilReady()         → 等待服务就绪（轮询检查）

流式处理机制:
1. 发送请求到 vLLM
2. 创建 channel（缓冲区 256）
3. 启动 goroutine 读取 SSE 流
4. 心跳检测：每 10 秒无活动发送 ": heartbeat"
5. 解析 "data: " 前缀行
6. 遇到 "[DONE]" 时发送 Done 事件并返回
7. 异常时发送 Error 事件
```

**流式读取器详解**:

```go
func (p *VLLMProxy) streamReader(resp *http.Response, ch chan<- StreamEvent) {
    /**
     * 流式 SSE 读取器：
     * 1. 使用 bufio.Scanner 逐行读取响应体
     * 2. 设置缓冲区最大 1MB，防止大消息溢出
     * 3. 心跳机制：10 秒无活动发送一次心跳
     * 4. 解析 SSE 格式：
     *    - "data: " 开头的行是数据行
     *    - "data: [DONE]" 是结束标志
     * 5. 发送 StreamEvent 到 channel
     * 6. 异常时发送错误事件
     * 7. defer 确保 channel 和响应体被关闭
     */
}
```

#### 3. `config/config.go` - Go 配置解析

```
作用: YAML 配置解析，支持环境变量覆盖

与 Python 版本的对应关系:
├── AppConfig     → app_controller/core/config.py::AppConfig
├── ModelConfig   → app_controller/core/config.py::ModelConfig
├── SettingsConfig→ app_controller/core/config.py::SettingsConfig
├── VLLMConfig    → app_controller/core/config.py 中的 vLLM 配置
└── LlamaCppConfig→ app_controller/core/config.py::LlamaCppConfig

特殊处理:
├── Redis URL 解析（支持 redis://host:port/db 格式）
├── 环境变量覆盖（REDIS_URL, REDIS_HOST, REDIS_PORT, REDIS_DB）
├── llama.cpp 默认值设置
└── 内存大小解析（支持 B/KB/MB/GB/TB）

并发安全:
├── cfgOnce (sync.Once) → 确保首次加载只执行一次
└── cfgMu (sync.RWMutex) → 保护配置读写
```

---

## 模块四：aiclient2api/ - API 网关

**技术栈**: Node.js (Docker 部署)  
**端口**: 3000  
**作用**: API 网关，负责路由转发、用户鉴权、Token 管理

### 目录结构

```
aiclient2api/
├── configs/
│   ├── config.json           # 网关配置（模型提供商）
│   ├── provider_pools.json   # 提供商连接池配置
│   ├── plugins.json          # 插件配置
│   ├── token-store.json      # Token 存储
│   └── usage-cache.json      # 使用量缓存
└── docker-compose.yml        # Docker 部署配置
```

### 配置文件详解

#### `config.json`
```json
{
  "MODEL_PROVIDER": "openai-custom"  // 模型提供商类型
}
```
作用：定义 API 网关使用的模型提供商类型。`openai-custom` 表示使用兼容 OpenAI 协议的自定义后端。

#### `provider_pools.json`
```json
{
  "providers": [
    {
      "customName": "app-controller",    // 提供商名称
      "baseUrl": "http://ai-controller:35000/v1",  // 后端地址
      "apiKey": "",                      // API Key
      "enabled": true                    // 是否启用
    },
    {
      "customName": "go-vllm-api",       // 提供商名称
      "baseUrl": "http://go-vllm-api:35001/v1",    // 后端地址
      "apiKey": "",                      // API Key
      "enabled": false                   // 是否启用
    }
  ]
}
```
作用：定义多个后端服务的连接池。网关可以在多个后端之间切换或负载均衡。
- `app-controller` (Python): 默认启用，提供完整的管理功能
- `go-vllm-api` (Go): 可选，用于高性能场景

#### `plugins.json`
作用：定义网关插件系统配置。插件可以扩展网关功能，如：
- 请求/响应转换
- 速率限制
- 缓存
- 日志增强

#### `token-store.json`
作用：持久化 Token 使用量数据，用于计费和统计。

#### `usage-cache.json`
作用：缓存 Token 使用量，减少重复计算。

---

## 模块间通信关系

### 请求流向

```
1. 前端请求 (fetch) 
   → aiclient2api (端口 3000)
   → app-controller (端口 35000) 或 go-vllm-api (端口 35001)
   → vLLM/llama.cpp 模型服务

2. 前端 WebSocket 连接
   → app-controller (端口 35000)
   → 定时广播 GPU/模型状态
```

### 数据共享

| 数据类型 | 存储位置 | 消费方 |
|---------|---------|--------|
| GPU 状态 | Redis | app-controller, go-vllm-api, 前端 |
| 模型配置 | config.yaml | app-controller, go-vllm-api |
| 指标数据 | 内存 + Redis | app-controller, go-vllm-api |
| WebSocket 连接 | 应用内存 | app-controller → 前端 |
| Token 使用量 | Redis + 内存 | app-controller, aiclient2api |

---

## 关键技术概念

### 1. 模型调度 (Scheduler)

**作用**: 管理 AI 模型的启动、停止、切换和资源分配

**核心能力**:
- **并发控制**: 每个模型有最大并发请求数限制
- **队列管理**: 超过并发限制时请求进入队列等待
- **内存感知**: 根据 GPU 内存决定是否启动新模型
- **预加载**: 启动时自动加载配置的预加载模型
- **健康监控**: 定期检查模型服务健康状态
- **模型切换**: 安全地从一个模型切换到另一个

### 2. 缓存系统

**架构**:
```
┌─────────────────────────────────────┐
│           缓存服务层                 │
│  ┌─────────────┐  ┌──────────────┐  │
│  │ 内存缓存     │  │ Redis 缓存    │  │
│  │ (进程内)     │→ │ (进程外)      │  │
│  │ TTL: 3-60s  │  │ 持久化        │  │
│  └─────────────┘  └──────────────┘  │
└─────────────────────────────────────┘
         ▲                    ▲
    cache_updater        redis_client
   (定时更新缓存)        (连接管理)
```

**缓存策略**:
- 读多写少的数据使用缓存（如模型列表、GPU 状态）
- 模型状态变更后立即清除相关缓存
- 支持手动刷新单个端点或全部缓存

### 3. 健康检查

**检查目标**:
- 管理接口 (`/manage/models/summary`)
- 推理接口 (`/health`)
- Redis 连接 (`/manage/redis/health`)
- GPU 状态
- 模型服务可用性

**检查频率**:
- WebSocket 广播：每 2 秒
- 前端轮询：按需（页面可见时）
- 后台任务：每 5 秒保存历史

### 4. 流式响应 (SSE)

**Server-Sent Events 流程**:
```
客户端 ← Server ← vLLM/llama.cpp
         │
         ├── 逐行读取 SSE 数据
         ├── 解析 "data: " 行
         ├── 添加心跳 (每 10 秒)
         ├── 替换 id/model 字段
         ├── 记录 token 用量
         └── 转发到客户端
```

---

## 部署架构

### Docker Compose 服务拓扑

```
services:
├── frontend         → 端口 30001 (开发)
├── ai-controller    → 端口 35000 (Python)
├── go-vllm-api      → 端口 35001 (Go)
├── aiclient         → 端口 3000 (网关)
├── redis            → 端口 6379 (缓存)
├── nginx            → 端口 30000 (生产代理)
└── prometheus       → 端口 9090 (监控)

共享卷:
├── /mnt/pve_models  → 模型文件存储
├── ./data/redis     → Redis 持久化
└── ./logs           → 日志文件
```

### Nginx 30000 代理规则

```
生产环境访问路径:
├── http://host:30000/          → 前端 (build 后静态文件)
├── http://host:30000/api/*     → aiclient2api (网关)
├── http://host:30000/v1/*      → ai-controller / go-vllm-api
├── http://host:30000/manage/*  → ai-controller
├── http://host:30000/health    → ai-controller / go-vllm-api
└── http://host:30000/ws        → ai-controller (WebSocket)
```

---

## 开发调试指南

### 启动命令

```bash
# 前端开发服务器
cd frontend && pnpm dev                    # http://localhost:30001

# Python 后端
cd app-controller && python main.py        # http://localhost:35000

# Go 后端
cd go-vllm-api && go run cmd/server/main.go --port 35001  # http://localhost:35001

# API 网关 (Docker)
cd aiclient2api && docker compose up -d    # http://localhost:3000

# 全栈 Docker 部署
docker compose up -d
```

### 常用调试技巧

1. **查看实时日志**: `docker compose logs -f ai-controller`
2. **检查 Redis 缓存**: `redis-cli KEYS "api:*"`
3. **查看 GPU 状态**: `curl http://localhost:35000/manage/gpu/summary`
4. **测试聊天接口**: `curl -X POST http://localhost:35000/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"xxx","messages":[{"role":"user","content":"hi"}]}'`
5. **热重载配置**: `kill -SIGHUP <pid>`

---

## 总结

| 模块 | 语言/框架 | 端口 | 主要职责 |
|------|----------|------|---------|
| frontend | Vue 3 + TS | 30001 | Web UI、用户交互 |
| app-controller | Python + FastAPI | 35000 | 核心控制器、模型调度 |
| go-vllm-api | Go + Gin | 35001 | 高性能代理、并发处理 |
| aiclient2api | Node.js | 3000 | API 网关、路由转发 |
| Redis | Redis | 6379 | 缓存、持久化 |
