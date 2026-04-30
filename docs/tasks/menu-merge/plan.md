# 前端菜单合并优化 — 任务清单

## 总览

| 优先级 | 数量 | 说明 |
|--------|------|------|
| P0 | 6 + 2测试 | 核心合并功能 |
| P1 | 1 | 构建验证 |

## 任务列表

### T0-1: 路由redirect和Tab容器测试 (P0, test)
- 验证旧路由redirect到新路由(带正确tab参数)
- 验证Tab容器渲染和切换逻辑

### T0-2: Sidebar菜单缩减测试 (P0, test)
- 验证菜单从13项缩减到6项
- 验证移除login菜单项
- 验证新菜单路由名称

### P0-1: 创建ModelCenter.vue (P0, code) ← 依赖T0-1
- 4 Tab容器: 调度/搜索/池/评测
- v-show切换，query param同步

### P0-2: 创建GPUMonitor.vue (P0, code) ← 依赖T0-1
- 2 Tab容器: 实时性能/GPU管理
- v-show切换，query param同步

### P0-3: 创建SystemOps.vue (P0, code) ← 依赖T0-1
- 4 Tab容器: 引擎/限流/配置/健康
- v-show切换，query param同步

### P0-4: 更新路由配置 (P0, code) ← 依赖T0-1/P0-1/P0-2/P0-3
- 新增3个合并路由
- 10个旧路由redirect

### P0-5: 更新Sidebar菜单 (P0, code) ← 依赖T0-2/P0-4
- 3组6项菜单结构

### P0-6: 改造Dashboard (P0, code) ← 依赖P0-4/P0-5
- 去掉启停操作，添加引导链接

### P1-1: 构建验证 (P1, code) ← 依赖P0-6
- pnpm build + TypeScript检查
