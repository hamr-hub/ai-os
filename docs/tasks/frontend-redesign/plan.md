# 任务清单 — Vue3 前端重新设计 + aiclient 插件功能升级

> taskId: frontend-redesign | source: docs/tasks/frontend-redesign/tech-solution.yaml

---

## 任务概览

| 优先级 | 类型 | 数量 | 说明 |
|--------|------|------|------|
| P0 | test | 3 | 核心composable单元测试 |
| P0 | code | 3 | 核心composable实现 |
| P1 | test | 2 | 搜索+引擎管理测试 |
| P1 | code | 8 | 页面UI+composable实现 |
| P2 | code | 2 | Agent图片上传+类型补充 |

---

## P0 任务 (必须完成)

### T0-1: useModelSwitch Phase2.5显存校验单元测试
- 文件: `frontend/src/composables/__tests__/useModelSwitch.test.ts`
- 验证: phase2.5状态映射/显存不足rollback/进度百分比

### P0-1: useModelSwitch Phase2.5实现
- 文件: `frontend/src/composables/useModelSwitch.ts`, `frontend/src/types/index.ts`
- 依赖: T0-1
- 完成: SwitchPhaseDetail含phase2.5 + WS解析 + build通过

### T0-2: useModelDownload WS下载进度+降级轮询测试
- 文件: `frontend/src/composables/__tests__/useModelDownload.test.ts`
- 验证: WS进度解析/断开降级3s轮询/状态映射

### P0-2: useModelDownload WS进度实现
- 文件: `frontend/src/composables/useModelDownload.ts`
- 依赖: T0-2
- 完成: WS实时进度 + 降级轮询 + 前往模型池按钮

### T0-3: useModelPool一键加载流程测试
- 文件: `frontend/src/composables/__tests__/useModelPool.test.ts`
- 验证: 显存校验→引擎启动→验证顺序/显存不足拒绝

### P0-3: useModelPool一键加载实现
- 文件: `frontend/src/composables/useModelPool.ts`
- 依赖: T0-3
- 完成: 一键加载含校验 + 显存不足告警

---

## P1 任务 (重要)

### T0-4: useModelSearch高级过滤器测试 → P1-1: 搜索过滤器实现
### T0-5: useEngineManagement引擎配置测试 → P1-2: 引擎管理实现
### P1-3: Dashboard GPU告警增强
### P1-4: ModelManagement引擎面板+Phase2.5+配置编辑 (依赖P0-1,P1-2)
### P1-5: ModelHubPage搜索徽章+过滤器+下载进度 (依赖P0-2,P1-1)
### P1-6: ModelPoolPage统计概览+一键加载 (依赖P0-3)
### P1-7: EngineManagementPage引擎配置UI (依赖P1-2)
### P1-8: GPUManage SGLang/llama.cpp指标

---

## P2 任务 (后续)

### P2-1: AgentChatWindow图片上传
### P2-2: api/client + types补充

---

## 验证命令

```bash
cd frontend && pnpm test
cd frontend && pnpm build
```
