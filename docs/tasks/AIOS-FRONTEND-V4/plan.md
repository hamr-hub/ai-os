# AIOS-FRONTEND-V4 任务清单

## 任务总览

| ID | 优先级 | 类型 | 标题 | 依赖 |
|----|--------|------|------|------|
| T0-1 | P0 | test | 修复useSystemData单元测试mock | - |
| P0-1 | P0 | code | 修正useSystemData单元测试mock | T0-1 |
| T0-2 | P0 | test | E2E测试断言验证 | - |
| P0-2 | P0 | code | 修正E2E测试选择器和断言 | T0-2 |
| T0-3 | P1 | test | Benchmarks/Docs E2E测试编写 | - |
| P0-3 | P1 | code | 补充Benchmarks/Docs E2E测试 | T0-3 |
| P0-4 | P1 | code | Dashboard视觉一致性确认 | - |

## 执行顺序

1. **T0-1 + P0-1**: 修复单元测试（先写测试验证mock逻辑，再修正mock代码）
2. **T0-2 + P0-2**: 修正E2E测试断言（先验证断言失败原因，再修正）
3. **T0-3 + P0-3**: 补充Benchmarks/Docs E2E测试
4. **P0-4**: 确认Dashboard视觉一致性

## 验证命令

- **单元测试**: `cd frontend && npx vitest run`
- **E2E测试**: `cd frontend && npx playwright test`
- **类型检查**: `cd frontend && npx vue-tsc --noEmit`
