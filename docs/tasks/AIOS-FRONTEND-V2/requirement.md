# ai-os 前端三大模块迭代完善 - 需求分析报告

## 任务概述

基于当前 ai-os 项目（Vue 3 + FastAPI），完善三大核心模块：

1. **Dashboard 控制台** — GPU监控、模型列表、一键切换、Token用量
2. **模型管理** — 运行模型展示、4项能力检测（对话/多模态/工具调用/图片生成）、检测历史
3. **Agent 聊天界面** — 简单 agent 交互 UI，连接本地模型，预留 hermes agent 扩展

## 当前状态 vs 目标差距

### Module 1: Dashboard 控制台

| 功能 | 状态 | 差距 |
|------|------|------|
| GPU 监控卡片 | ✅ 已完成 | - |
| GPU 历史趋势图 | ❌ 缺失 | 后端 API 已有，前端未集成 |
| 运行中模型 | ✅ 已完成 | - |
| 模型列表+一键切换 | ✅ 已完成 | - |
| Token 用量统计 | ❌ 缺失 | 后端方法已有，缺路由+前端展示 |
| 请求统计 | ✅ 已完成 | - |

### Module 2: 模型管理

| 功能 | 状态 | 差距 |
|------|------|------|
| 运行中模型展示 | ✅ 已完成 | - |
| 已停止模型列表 | ✅ 已完成 | - |
| 4项能力检测 | ⚠️ UI有，类型不完整 | `feature_support` 缺 `multimodal`/`image_generation` 字段定义 |
| 性能指标 | ✅ 已完成 | - |
| 资源使用 | ⚠️ 部分完成 | 类型缺 `end_temperature`/`end_utilization` |
| 检测历史 | ⚠️ 列表有，详情不完整 | 展开缺少 multimodal/image_generation 展示 |
| 检测详情 | ✅ 已完成 | - |

### Module 3: Agent 聊天界面

| 功能 | 状态 | 差距 |
|------|------|------|
| 会话管理 | ✅ 已完成 | - |
| 模型选择 | ✅ 已完成 | - |
| 系统提示词 | ✅ 已完成 | - |
| 流式对话 | ✅ 已完成 | - |
| Tool Calls 展示 | ❌ 缺失 | Message 有 `toolCalls` 字段但 UI 未渲染 |
| Agent 风格布局 | ⚠️ 基本具备 | 顶部交互可优化 |

## 关键差距清单（7项）

| # | 优先级 | 模块 | 描述 | 修复方案 |
|---|--------|------|------|----------|
| G1 | P1 | Dashboard | GPU 历史趋势图缺失 | Dashboard.vue 添加 SVG 图表，调用 getGPUHistory() |
| G2 | P1 | Dashboard | Token 用量统计缺失 | 1) routes/manage.py 添加路由 2) Dashboard.vue 添加展示区 |
| G3 | P1 | 模型管理 | feature_support 类型不完整 | types/index.ts 添加 multimodal + image_generation |
| G4 | P2 | 模型管理 | GPU 资源类型缺字段 | types/index.ts 添加 end_temperature + end_utilization |
| G5 | P2 | 模型管理 | 检测历史详情不完整 | ModelManagement.vue 增加4项能力展示 |
| G6 | P2 | Agent聊天 | tool_calls 展示缺失 | ChatWindow.vue 添加渲染逻辑 |
| G7 | P2 | Agent聊天 | Agent 布局可优化 | 优化 ChatWindow 顶栏交互 |

## 判定：PASS

所有差距均为可修复的技术问题，无 P0 阻塞项，可继续进入技术方案设计。
