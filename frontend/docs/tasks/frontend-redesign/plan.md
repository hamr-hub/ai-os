# 任务清单: ai-os前端测试计划与测试用例全覆盖

## 概览

- **技术方案来源**: tech-solution.yaml
- **测试覆盖率目标**: ≥80%
- **每功能最少测试数**: 3
- **总任务数**: 18个test任务 + 8个code任务 = 26个任务

---

## P0 任务 (必须完成)

### Test任务

| ID | 标题 | 文件 | 预估用例数 |
|----|------|------|-----------|
| T0-1 | useAuth测试 | composables/__tests__/useAuth.test.ts | 5 |
| T0-2 | useConfigManagement测试 | composables/__tests__/useConfigManagement.test.ts | 6 |
| T0-3 | useEngineManagement测试 | composables/__tests__/useEngineManagement.test.ts | 5 |
| T0-4 | useHealthOps测试 | composables/__tests__/useHealthOps.test.ts | 5 |
| T0-5 | useRateLimit测试 | composables/__tests__/useRateLimit.test.ts | 5 |
| T0-6 | useModelDownload测试 | composables/__tests__/useModelDownload.test.ts | 8 |
| T0-7 | useModelPool测试 | composables/__tests__/useModelPool.test.ts | 5 |
| T0-8 | useModelSearch测试 | composables/__tests__/useModelSearch.test.ts | 5 |
| T0-9 | useModelSwitch测试 | composables/__tests__/useModelSwitch.test.ts | 10 |
| T0-10 | usePolling测试 | composables/__tests__/usePolling.test.ts | 7 |
| T0-11 | useLLMService测试 | composables/__tests__/useLLMService.test.ts | 5 |
| T0-12 | useGPUMemory测试 | composables/__tests__/useGPUMemory.test.ts | 6 |
| T0-13 | useGPUMemoryCheck测试 | composables/__tests__/useGPUMemoryCheck.test.ts | 4 |
| T0-14 | auth store测试 | stores/__tests__/auth.test.ts | 4 |
| T0-15 | modelPool store测试 | stores/__tests__/modelPool.test.ts | 8 |
| T0-16 | gpu store测试 | stores/__tests__/gpu.test.ts | 6 |

### Code任务 (按test依赖执行)

| ID | 标题 | 依赖 | 文件数 |
|----|------|------|--------|
| P0-1 | useAuth/useConfig/useEngine测试代码 | T0-1,T0-2,T0-3 | 3 |
| P0-2 | useHealthOps/useRateLimit测试代码 | T0-4,T0-5 | 2 |
| P0-3 | useModelDownload/Pool/Search测试代码 | T0-6,T0-7,T0-8 | 3 |
| P0-4 | useModelSwitch/usePolling测试代码 | T0-9,T0-10 | 2 |
| P0-5 | useLLMService/useGPUMemory/useGPUMemoryCheck测试代码 | T0-11,T0-12,T0-13 | 3 |
| P0-6 | auth/modelPool/gpu store测试代码 | T0-14,T0-15,T0-16 | 3 |

---

## P1 任务 (建议完成)

| ID | 标题 | 依赖 | 文件数 |
|----|------|------|--------|
| T0-17 | 页面组件渲染测试 | 无 | 8个页面 |
| P1-1 | 编写页面渲染测试代码 | T0-17 | 8 |
| P1-2 | 生成测试计划文档 | T0-18 | 2 |

---

## 执行命令

- **测试**: `cd frontend && npx vitest run`
- **Lint**: `git diff --name-only HEAD | grep '.test.ts$' | xargs eslint`
- **类型检查**: `cd frontend && npx vue-tsc --noEmit`

---

## 预估测试用例总数: ~104个
