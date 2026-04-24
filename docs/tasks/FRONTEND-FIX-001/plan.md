# FRONTEND-FIX-001 开发任务清单

## 任务概览

| ID | 类型 | 优先级 | 标题 | 依赖 |
|----|------|--------|------|------|
| T0-1 | test | P0 | 验证 benchmarks 路由导航正确性 | 无 |
| P0-1 | code | P0 | 修复缺失的 benchmarks 路由 | T0-1 |
| T0-2 | test | P0 | 验证 App.vue mainMargin 使用 CSS 变量 | 无 |
| P0-2 | code | P0 | 修复 sidebar/main 宽度不匹配 | T0-2 |
| T0-3 | test | P0 | 验证 TS 类型修复 - SystemStatus queue 字段 | 无 |
| P0-3 | code | P0 | 修复 TS 类型错误（多文件） | T0-3 |
| P1-1 | code | P1 | 修复 CSS 重复 --shadow-glow 定义 | 无 |

## 任务详情

### T0-1: 验证 benchmarks 路由导航正确性
- **Given**: 路由配置中包含 /benchmarks 路径
- **When**: router.resolve({ name: 'benchmarks' })
- **Then**: 路径为 /benchmarks，组件为 ModelBenchmarks.vue

### P0-1: 修复缺失的 benchmarks 路由
- **文件**: src/router/index.ts
- **实现**: 在 agent 路由后添加 `/benchmarks` 路由指向 ModelBenchmarks.vue

### T0-2: 验证 App.vue mainMargin 使用 CSS 变量
- **Given**: sidebarCollapsed 为 false
- **When**: 计算 mainMargin
- **Then**: 使用 var(--sidebar-width) 而非硬编码 220px

### P0-2: 修复 sidebar/main 宽度不匹配
- **文件**: src/App.vue
- **实现**: mainMargin 改用 CSS 变量 var(--sidebar-width)/var(--sidebar-collapsed-width)

### T0-3: 验证 TS 类型修复
- **Given**: SystemStatus 类型定义包含可选 queue 字段
- **When**: TypeScript 编译检查
- **Then**: 无类型错误

### P0-3: 修复 TS 类型错误（多文件）
- **文件**: types/index.ts, useSystemData.ts, useTokenHistory.ts, Dashboard.vue, useSystemData.test.ts
- **实现**: 补充 queue 字段、参数改为 MaybeRefOrGetter、类型断言、修正测试

### P1-1: 修复 CSS 重复定义
- **文件**: src/style.css
- **实现**: 删除第二处 --shadow-glow 定义

## 测试命令
- `cd frontend && pnpm test`
- `cd frontend && npx vue-tsc --noEmit`
- `cd frontend && pnpm build`
