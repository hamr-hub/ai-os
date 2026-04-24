# FRONTEND-FIX-001: 前端界面修复

## 业务目标

修复 ai-os 前端界面的4个关键bug，确保页面正常显示和导航功能正常。

## 问题清单

### 1. 缺失的 benchmarks 路由（P0）
- **问题**：Sidebar 有"模型评测"导航项，但路由中缺少 `/benchmarks` 定义
- **影响**：点击"模型评测"无法到达 ModelBenchmarks.vue 页面，被 catch-all 跳转到 Dashboard
- **修复**：在 router/index.ts 中添加 `/benchmarks` 路由

### 2. Sidebar/Main 宽度不匹配（P0）
- **问题**：App.vue 使用硬编码 `220px/64px` 作为 marginLeft，但 sidebar 实际宽度为 `240px/68px`
- **影响**：展开时 main 内容区与 sidebar 重叠 20px，折叠时重叠 4px
- **修复**：改用 CSS 变量 `var(--sidebar-width)` / `var(--sidebar-collapsed-width)` 

### 3. TypeScript 类型错误（P1）
- **问题1**：SystemStatus 类型缺少 `queue` 字段，导致 `systemStatus.value?.queue` 类型错误
- **问题2**：useSystemData/useTokenHistory 的 `initialCount` 参数不支持 `ComputedRef<number>`
- **问题3**：Dashboard 中 `queueStatus` 的 `unknown` 类型错误
- **问题4**：测试文件引用了不存在的 `fetch` 方法
- **修复**：补充类型定义、参数改用 MaybeRefOrGetter、类型断言、修正测试

### 4. CSS 重复定义（P2）
- **问题**：`--shadow-glow` 在 style.css 中定义两次
- **修复**：删除重复定义

## 验收标准

| AC | Given | When | Then |
|----|-------|------|------|
| AC-1 | 侧边栏点击模型评测 | 路由跳转到 /benchmarks | ModelBenchmarks.vue 正确渲染 |
| AC-2 | 页面加载且sidebar展开 | sidebar宽度240px | main marginLeft=240px 无重叠 |
| AC-3 | 页面加载且sidebar折叠 | sidebar宽度68px | main marginLeft=68px 无重叠 |
| AC-4 | 执行 pnpm build | TypeScript检查+构建 | 0个类型错误，构建通过 |

## 影响范围

- `src/router/index.ts` - 新增路由
- `src/App.vue` - 修改 marginLeft 计算
- `src/style.css` - 删除重复变量
- `src/types/index.ts` - 添加 queue 字段
- `src/composables/useSystemData.ts` - 参数类型调整
- `src/composables/useTokenHistory.ts` - 参数类型调整
- `src/views/Dashboard.vue` - 类型断言修复
- `src/composables/__tests__/useSystemData.test.ts` - 修正测试引用
