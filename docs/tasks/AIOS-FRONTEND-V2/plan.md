# ai-os 前端迭代 — 任务清单

## 任务总览

| 任务 | 优先级 | 文件 | 依赖 |
|------|--------|------|------|
| T1: 修复类型定义 | P1 | types/index.ts | 无 |
| T2: 后端 token-stats 路由 | P1 | routes/manage.py | 无 |
| T3: API Client 对齐 | P1 | api/client.ts | T1 |
| T4: Dashboard GPU图+Token统计 | P1 | Dashboard.vue | T3 |
| T5: 模型管理类型修复+历史完善 | P2 | ModelManagement.vue | T1 |
| T6: ChatWindow tool_calls展示 | P2 | ChatWindow.vue | T1 |

## 执行顺序

```
T1 ──┬── T3 ── T4
     ├── T5
     └── T6
T2 ────────── (独立，可与T1并行)
```

T1和T2可并行执行，T3-T6依赖T1完成后按顺序执行。
