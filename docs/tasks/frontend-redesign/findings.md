# 研究发现

## 背景
Vue3 前端重新设计 + aiclient 插件功能升级，基于 PRD 功能点 14-22

## 关键发现

### 发现 1: 前端功能已大部分存在
- **来源**: Explore agent 前端代码扫描
- **内容**: 8个页面(3791+872+794+869+762+503+696+304行),12个composables,15+API方法,路由和导航完整
- **影响**: 本次升级以"完善+重设计"为主，而非全新开发
- **日期**: 2026-04-30

### 发现 2: 关键缺口清单
- **来源**: PRD vs 现有代码对比
- **内容**: 
  1. 引擎配置编辑UI (API存在但无UI)
  2. SGLang/llama.cpp专项指标不在Dashboard展示
  3. 搜索结果只有基础排序(缺高级过滤器)
  4. 模型池无统计概览卡片
  5. 下载→池→加载流程衔接不够顺畅
  6. Agent不支持图片上传
- **影响**: 需要新增组件/修改现有页面
- **日期**: 2026-04-30

### 发现 3: ModelManagement.vue 过大
- **来源**: wc -l 统计
- **内容**: 3791行，含模型调度+引擎切换+搜索+下载+推荐+配置编辑
- **影响**: 虽大但功能内聚，暂不拆分，后续可抽取子组件
- **日期**: 2026-04-30

### 发现 4: useGPUMemory Ref 模板类型问题已解决
- **来源**: 上一会话的TS错误修复
- **内容**: composable返回的Ref在模板中不自动解包，需解构为顶层ref才能正确TS推导
- **影响**: 所有使用useGPUMemory/useGPUMemoryCheck的页面需类似处理
- **日期**: 2026-04-30

### 发现 5: pnpm build 已通过
- **来源**: 上一会话最后验证
- **内容**: 修复所有TS错误后 build 通过，输出 20+ 个 chunk
- **影响**: 可作为新变更的基线
- **日期**: 2026-04-30

## 研究问题
1. ModelManagement.vue 是否需要拆分? → 暂不拆分，功能内聚
2. EngineSwitchPanel 是否应独立页面? → 保持嵌入模式
3. 搜索过滤器需要哪些维度? → size/quant/multimodal/feasible/source

## 技术笔记
- Vue 3.3+ 模板中 ref 自动解包仅限顶层，嵌套 Ref 需解构
- Tailwind CSS v4 via @tailwindcss/vite (不使用 PostCSS)
- chart.js + vue-chartjs 用于 GPU/系统监控图表
- Lucide icons 组件化使用方式
- WS 连接模式: connectDownloadWS() + disconnectWS() + wsConnected ref
- 现有 CSS 变量体系: --bg-primary/--bg-card/--border-primary/--text-primary 等

## 参考资料
- docs/agent/prd.md — PRD 文档
- docs/agent/architecture.md — 架构设计
- frontend/src/views/*.vue — 所有页面
- frontend/src/composables/*.ts — 所有composables
- frontend/src/api/client.ts — API客户端
- frontend/src/types/index.ts — 类型定义
