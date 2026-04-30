# 前端菜单合并优化 — 技术方案

## 合并策略: Tab容器页面

核心思路：不改动原有子页面组件，创建轻量Tab容器页面，将子页面作为子组件嵌入。

```
┌─────────────────────────────────────────────┐
│ 模型中心                                     │
│ ┌──────┬──────┬──────┬──────┐              │
│ │ 调度 │ 搜索 │  池  │ 评测 │ ← Tab切换    │
│ └──────┴──────┴──────┴──────┘              │
│ ┌───────────────────────────────────────┐  │
│ │ ModelManagement.vue (原封不动)         │  │ ← v-show显示
│ │ ModelHubPage.vue                      │  │ ← v-show隐藏
│ │ ModelPoolPage.vue                     │  │ ← v-show隐藏
│ │ ModelBenchmarks.vue                   │  │ ← v-show隐藏
│ └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

## 新菜单结构 (3组6项)

| 组 | 菜单项 | 路由 | 说明 |
|---|--------|------|------|
| 核心控制 | 总览面板 | / | Dashboard(去掉启停操作) |
| 核心控制 | 模型中心 | /modelcenter | 4 Tab: 调度/搜索/池/评测 |
| 监控运维 | GPU监控 | /gpumonitor | 2 Tab: 实时性能/GPU管理 |
| 监控运维 | 系统运维 | /systemops | 4 Tab: 引擎/限流/配置/健康 |
| 工具 | AI Agent | /agent | 不变 |
| 工具 | 系统文档 | /docs | 不变 |

## 路由变更

### 新增路由
- `/modelcenter` — 模型中心 (query param: tab=schedule|search|pool|benchmark)
- `/gpumonitor` — GPU监控 (query param: tab=performance|manage)
- `/systemops` — 系统运维 (query param: tab=engine|ratelimit|config|health)

### 旧路由redirect
- `/models` → `/modelcenter?tab=schedule`
- `/modelhub` → `/modelcenter?tab=search`
- `/modelpool` → `/modelcenter?tab=pool`
- `/benchmarks` → `/modelcenter?tab=benchmark`
- `/monitor` → `/gpumonitor?tab=performance`
- `/gpumanage` → `/gpumonitor?tab=manage`
- `/engines` → `/systemops?tab=engine`
- `/ratelimit` → `/systemops?tab=ratelimit`
- `/config` → `/systemops?tab=config`
- `/health` → `/systemops?tab=health`

## Tab容器页面设计

### 关键实现: v-show而非v-if

使用 `v-show` 切换Tab内容，避免组件重复挂载/销毁，保持各页面状态不丢失。

```vue
<template>
  <div class="model-center">
    <div class="page-header">...</div>
    <div class="tab-controls">
      <button v-for="tab in tabs" @click="activeTab = tab.key"
        :class="{ active: activeTab === tab.key }">{{ tab.label }}</button>
    </div>
    <div class="tab-content">
      <ModelManagement v-show="activeTab === 'schedule'" />
      <ModelHubPage v-show="activeTab === 'search'" />
      <ModelPoolPage v-show="activeTab === 'pool'" />
      <ModelBenchmarks v-show="activeTab === 'benchmark'" />
    </div>
  </div>
</template>
```

### URL同步Tab状态

通过query param同步Tab状态，用户刷新页面后能回到当前Tab：

```ts
const route = useRoute()
const router = useRouter()
const activeTab = ref(route.query.tab || 'schedule')

watch(activeTab, (tab) => {
  router.replace({ query: { tab } })
})

watch(() => route.query.tab, (tab) => {
  if (tab) activeTab.value = tab as string
})
```

## Dashboard改造

- 去掉 `handleStartModel` / `handleStopModel` / `handleSwitchAndSetDefault` 相关操作按钮
- 保留模型状态展示卡片（只显示running/stopped状态）
- 添加"前往模型中心"引导按钮 `router.push('/modelcenter')`
- 保留GPU状态卡片和引擎状态卡片（无操作按钮）

## 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| Sidebar.vue | 修改 | groups从4组13项改为3组6项 |
| router/index.ts | 修改 | 新增3路由+10个redirect |
| ModelCenter.vue | 新建 | 模型中心Tab容器 |
| GPUMonitor.vue | 新建 | GPU监控Tab容器 |
| SystemOps.vue | 新建 | 系统运维Tab容器 |
| Dashboard.vue | 修改 | 去掉启停操作按钮，加引导链接 |

## 回滚方案

1. 旧路由保留redirect，不会404
2. 旧页面组件不删除
3. 恢复Sidebar.vue的groups数组+删除redirect即可回滚
4. Tab容器页面可随时移除
