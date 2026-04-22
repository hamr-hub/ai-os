# 研发资产报告

> ai-os 项目资产盘点

**生成时间**: 2026-04-22  
**项目类型**: 多模块项目  
**平台**: codeflicker

---

## 项目概览

### 模块结构
- **frontend**: Vue 3 + Vite + TypeScript 前端
- **app-controller**: Python FastAPI 后端
- **aiclient2api**: API 网关

### 技术栈

**前端**
- Vue 3.5 + Composition API
- Vite 6 构建工具
- TypeScript 5.8
- Tailwind CSS 4
- Pinia 3 状态管理
- Vue Router 5
- Axios HTTP 客户端
- Lucide Vue Next 图标库

**后端**
- Python 3.11+
- FastAPI
- Pydantic 数据验证
- YAML 配置管理

---

## 核心资产

### 前端组件
| 组件 | 路径 | 功能 |
|------|------|------|
| ChatWindow | frontend/src/components/ChatWindow.vue | 聊天窗口 |
| ModelManager | frontend/src/components/ModelManager.vue | 模型管理 |
| GPUMonitor | frontend/src/components/GPUMonitor.vue | GPU 监控 |
| Sidebar | frontend/src/components/Sidebar.vue | 侧边栏导航 |
| ToastContainer | frontend/src/components/ToastContainer.vue | 消息通知 |

### 页面视图
| 视图 | 路径 | 功能 |
|------|------|------|
| Dashboard | frontend/src/views/Dashboard.vue | 仪表盘首页 |
| ChatView | frontend/src/views/ChatView.vue | 对话页面 |
| ModelsView | frontend/src/views/ModelsView.vue | 模型管理页 |
| GPUView | frontend/src/views/GPUView.vue | GPU 状态页 |

### Composables
| Hook | 路径 | 功能 |
|------|------|------|
| useGlobalState | frontend/src/composables/useGlobalState.ts | 全局状态管理 |
| useModels | frontend/src/composables/useModels.ts | 模型列表管理 |
| useGPU | frontend/src/composables/useGPU.ts | GPU 状态监控 |

### Pinia Stores
| Store | 路径 | 功能 |
|-------|------|------|
| app | frontend/src/stores/app.ts | 应用状态（主题/Toast） |
| chat | frontend/src/stores/chat.ts | 对话状态管理 |

### API 模块
| 模块 | 路径 | 功能 |
|------|------|------|
| client | frontend/src/api/client.ts | API 客户端封装 |

---

## 后端资产

### 核心模块
| 模块 | 路径 | 功能 |
|------|------|------|
| config | app-controller/core/config.py | 配置管理 |
| logger | app-controller/core/logger.py | 日志系统 |
| metrics | app-controller/core/metrics.py | 性能指标 |
| monitor | app-controller/core/monitor.py | 系统监控 |
| vllm_manager | app-controller/core/vllm_manager.py | vLLM 模型管理 |
| websocket_manager | app-controller/core/websocket_manager.py | WebSocket 连接管理 |

### 配置模型
- ModelConfig: 模型配置验证
- QueueConfig: 队列配置
- SettingsConfig: 系统设置
- AppConfig: 应用配置根

---

## Snippets 资产

已提取代码片段存放在 `.codeflicker/snippets/`：

### 使用建议
1. **Vue 组件**: 参考 ChatWindow、ModelManager 的组件结构
2. **Composables**: 参考 useGlobalState 的状态管理模式
3. **Pinia Store**: 参考 app store 的 Toast/主题实现
4. **API Client**: 参考 client.ts 的 axios 封装
5. **Python Config**: 参考 config.py 的 Pydantic 验证

---

## 编码规范

### Vue 3
- 使用 `<script setup lang="ts">` 语法
- Props 使用 `defineProps<T>()` 类型推断
- 样式使用 Tailwind CSS utility-first

### Python
- 使用 type hints
- Pydantic 数据验证
- Google Style 文档字符串

### Git
- Commit: `<type>(scope): <subject>`
- Type: feat/fix/refactor/docs/test/chore

---

## 后续建议

### P0 必要
- [ ] 补充测试框架（Vitest）
- [ ] 添加 E2E 测试（Playwright）

### P1 推荐
- [ ] 补充组件文档（Storybook）
- [ ] 添加 API 文档生成

### P2 可选
- [ ] 添加性能监控（埋点）
- [ ] 补充错误上报

---

> 自动生成于 2026-04-22 | AI Flow v0.4.16
