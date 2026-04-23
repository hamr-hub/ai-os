# Dashboard功能完善 + 端到端测试

## 需求概述

完善Dashboard页面功能，增加系统状态、队列、健康告警等数据卡片；优化加载状态、错误处理和响应式布局；搭建Playwright E2E测试和Vitest单元测试框架。

## 需求清单

### R1: 系统状态卡片 (P0)
- Dashboard新增CPU/内存/磁盘使用率卡片
- 数据源: `/manage/system/status`
- 进度条 + 阈值颜色

### R2: 队列状态卡片 (P0)
- Dashboard新增请求队列卡片
- 数据源: `/manage/queue`
- 显示各模型队列请求数

### R3: 健康告警卡片 (P1)
- Dashboard新增健康告警卡片
- 数据源: `/manage/health/alert`
- 状态颜色标记 + 告警列表

### R4: 使用useTokenStats composable (P1)
- 替换Dashboard中重复的token数据获取逻辑

### R5: 加载状态和错误处理 (P0)
- 首次加载骨架屏
- API失败可重试提示
- 操作失败Toast通知

### R6: 响应式布局 (P1)
- 3列(>1200px) / 2列(768-1200px) / 1列(<768px)

### R7: Playwright E2E测试 (P0)
- 搭建Playwright + 编写Dashboard E2E测试

### R8: Vitest单元测试 (P1)
- 搭建Vitest + composables/stores测试
