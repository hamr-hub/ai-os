# ai-os 前端三大模块迭代 — 技术方案

## 方案概述

本次迭代完善3大模块的7个gap，涉及7个文件修改，均为低到中等风险变更。

## 变更清单

### T1: 修复类型定义 `frontend/src/types/index.ts`
- `TestReport.feature_support` 添加 `multimodal: boolean` 和 `image_generation: boolean`
- `resource_utilization.gpu` 添加 `end_temperature?: number` 和 `end_utilization?: number`

### T2: 后端添加 token-stats 路由 `app-controller/routes/manage.py`
- 新增 `GET /manage/token-stats` 端点
- 调用 `metrics.get_token_stats()`，10秒 Redis 缓存

### T3: API Client 对齐 `frontend/src/api/client.ts`
- 确保 `getTokenStats()` → `/manage/token-stats`
- 确保 `getGPUHistory()` → `/manage/gpu/history`
- 确保 `testModel()` → `/v1/test/model/{name}`

### T4: Dashboard 添加 GPU 历史图 + Token 统计 `frontend/src/views/Dashboard.vue`
- GPU 历史趋势图：3条SVG折线（温度绿/利用率蓝/显存紫）
- Token 用量统计：总 Token / Prompt Token / Completion Token
- 集成到自动刷新逻辑

### T5: 模型管理类型修复 + 检测历史完善 `frontend/src/views/ModelManagement.vue`
- 移除 `as any` 类型转换
- 检测历史展开详情添加4项能力展示

### T6: ChatWindow 添加 tool_calls 展示 `frontend/src/components/ChatWindow.vue`
- tool_calls 渲染为可折叠代码块
- 显示 function name + arguments (JSON)
- 紫色左边框与普通 assistant 消息区分

## 回滚方案

```bash
git checkout -- frontend/src/types/index.ts app-controller/routes/manage.py frontend/src/api/client.ts frontend/src/views/Dashboard.vue frontend/src/views/ModelManagement.vue frontend/src/components/ChatWindow.vue frontend/src/stores/chat.ts
```
