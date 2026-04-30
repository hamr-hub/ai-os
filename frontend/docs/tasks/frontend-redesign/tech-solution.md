# 技术方案: ai-os前端测试计划与测试用例全覆盖

## 1. 背景 & 目标

ai-os Vue3前端管控面板已全部实现（21个composable、6个store、14个页面、完整API client），但缺少系统性测试覆盖。当前仅有7个composable测试和3个store测试，大量新模块无测试保障。

**目标**: 为所有前端模块提供≥80%测试覆盖率，≥100个测试用例，vitest全PASS。

## 2. 范围 & 不做

**包含**: composable单元测试(14个新增)、store单元测试(3个新增)、页面组件渲染测试(8个关键页面)、测试计划文档

**不包含**: Go/Python后端测试、E2E测试(后续独立任务)、性能压测

## 3. 核心设计思路

### 3.1 测试分层策略

```
┌─────────────────────────────┐
│  Unit Tests (composable)    │  80+ 用例
│  vi.mock('@/api/client')    │
├─────────────────────────────┤
│  Unit Tests (store)         │  20+ 用例
│  createPinia + setActive    │
├─────────────────────────────┤
│  Component Tests (页面)     │  20+ 用例
│  @vue/test-utils mount      │
└─────────────────────────────┤
```

### 3.2 Mock策略

所有测试统一mock `@/api/client`，遵循现有模式：

```typescript
vi.mock('@/api/client', () => ({
  getGPUSummary: vi.fn().mockResolvedValue(mockData),
  // ... 每个测试只mock需要的函数
}))
```

### 3.3 WS测试策略

涉及WebSocket的composable（useModelSwitch、useModelDownload）使用MockWebSocket：

```typescript
class MockWebSocket {
  send = vi.fn()
  close = vi.fn()
  addEventListener = vi.fn()
  removeEventListener = vi.fn()
}
vi.stubGlobal('WebSocket', MockWebSocket)
```

## 4. 测试矩阵

### 4.1 Composable测试 (14个新增)

| Composable | 关键测试点 | 预估用例 |
|------------|-----------|---------|
| useAuth | login/logout/token/user/isAuthenticated | 5 |
| useConfigManagement | fetchAll/updateEngine/updateSystem/setDefault | 6 |
| useEngineManagement | fetchStatus/doSwitchEngine/doUpdateConfig | 5 |
| useHealthOps | fetchAlert/fetchDetail/fetchHistory/runCheck | 5 |
| useRateLimit | fetchQueue/fetchConfig/fetchStats/doUpdateConfig | 5 |
| useModelDownload | start/cancel/list/WS连接/降级轮询 | 8 |
| useModelPool | list/detail/load/remove | 5 |
| useModelSearch | search/recommend/checkMemory | 5 |
| useModelSwitch | triggerSwitch/cancel/WS/computed/终态 | 10 |
| usePolling | fetch/refresh/start/stop/AbortController | 7 |
| useLLMService | getStatus/getLogs/start/stop/loadFromPool | 5 |
| useGPUMemory | getGPU/recommend/checkMemory/doSwitchEngine | 6 |
| useGPUMemoryCheck | fetchMemoryInfo/getRecommendation/checkModel | 4 |

### 4.2 Store测试 (3个新增)

| Store | 关键测试点 | 预估用例 |
|-------|-----------|---------|
| auth | setToken/clearToken/isAuthenticated | 4 |
| modelPool | fetchPool/search/startDownload/cancel/load/delete/WS | 8 |
| gpu | fetchGPUData/startPolling/stopPolling/引用计数 | 6 |

### 4.3 页面组件渲染测试 (8个关键页面)

| 页面 | 测试点 | 预估用例 |
|------|--------|---------|
| Dashboard | 渲染GPU/模型/系统卡片 | 3 |
| ModelManagement | 渲染模型列表/切换按钮 | 2 |
| ModelHubPage | 渲染搜索/下载 | 2 |
| ModelPoolPage | 渲染池列表/加载按钮 | 2 |
| EngineManagementPage | 渲染引擎状态 | 2 |
| RateLimitPage | 渲染限流配置 | 2 |
| ConfigManagementPage | 渲染配置面板 | 2 |
| AuthPage | 渲染登录表单 | 2 |

## 5. 风险与验证策略

| 风险 | 级别 | 缓解措施 |
|------|------|---------|
| WS测试mock复杂 | P1 | MockWebSocket类统一封装 |
| usePolling生命周期mock | P1 | mock vue onMounted/onUnmounted |
| Chart.js依赖 | P2 | mock chart.js |

## 6. 待确认项

无

## 7. AC → 文件映射

| AC | 描述 | ac_type | 文件路径 | 实现方式 |
|----|------|---------|---------|---------|
| AC-01 | composable测试通过 | code | composables/__tests__/*.test.ts | 新增14个测试文件 |
| AC-02 | store测试通过 | code | stores/__tests__/*.test.ts | 新增3个测试文件 |
| AC-03 | API client测试通过 | code | composables/__tests__/*.test.ts | 随composable覆盖 |
| AC-04 | 页面渲染测试通过 | code | views/__tests__/*.test.ts | 新增8个测试文件 |
| AC-05 | E2E测试通过 | qa | Playwright | QA验收(不在本次) |
| AC-06 | 测试计划文档 | docs | docs/tasks/frontend-redesign/ | 新增YAML+MD |
