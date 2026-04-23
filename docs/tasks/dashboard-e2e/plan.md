# 任务清单 - Dashboard功能完善 + 端到端测试

## Phase 1: 类型定义和API函数
- **T1** [P0] 添加SystemStatus/QueueStatus/HealthAlert类型定义 → `types/index.ts`
- **T2** [P0] 添加getSystemStatus/getQueueStatus/getHealthAlert API函数 → `api/client.ts`
- **T3** [P0] 创建useSystemData composable → `composables/useSystemData.ts`

## Phase 3: Go后端完善
- **T4** [P1] Go后端SystemStatus返回实际数据 → `service/system.go`, `manage.go`

## Phase 2: Dashboard功能完善
- **T5** [P1] Dashboard使用useTokenStats composable
- **T6** [P0] Dashboard新增系统状态卡片
- **T7** [P0] Dashboard新增队列状态卡片
- **T8** [P1] Dashboard新增健康告警卡片
- **T9** [P0] Dashboard添加loading骨架屏和错误处理
- **T10** [P1] Dashboard响应式布局优化

## Phase 4: Playwright E2E测试
- **T11** [P0] 搭建Playwright E2E测试框架
- **T12** [P0] 编写Dashboard E2E测试

## Phase 5: Vitest单元测试
- **T13** [P1] 搭建Vitest单元测试框架
- **T14** [P1] 编写composables和store单元测试
