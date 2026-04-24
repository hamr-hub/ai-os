# AIOS-FRONTEND-V4: 界面美化与端到端测试完善

## 业务目标

- **目标用户**: AI模型运维人员和开发者
- **核心问题**: Dashboard界面视觉体验不够精致，E2E测试覆盖率不足且部分测试与实际UI不匹配
- **成功指标**: E2E测试通过率100%、单元测试通过率100%、骨架屏加载体验正确

## 范围

### 做什么
1. Dashboard界面视觉优化：卡片间距、圆角、阴影、空状态样式统一
2. 修复失败的单元测试（useSystemData.test.ts - 3个失败）
3. 完善E2E测试：修正与实际UI不匹配的断言（选择器/类名/路径）
4. 补充缺失E2E测试场景（Benchmarks页面、Docs页面）
5. 响应式布局E2E测试修正（中屏阈值应为768px而非1000px）

### 不做什么
- 新增页面或功能
- 后端API修改
- 性能优化（非视觉相关）

## 关键交互

**Dashboard首页** → 用户打开Dashboard → 看到6张卡片（GPU/Token/系统/队列/健康/模型） → 各卡片展示数据或空状态

状态：加载中(骨架屏) → 数据已加载 → 数据不可用(空状态)

## 验收标准

| ID | Given | When | Then | 类型 |
|----|-------|------|------|------|
| AC-01 | Dashboard页面数据加载中 | 用户访问Dashboard | 显示6个骨架屏卡片占位，无空白闪烁 | 视觉 |
| AC-02 | Dashboard页面数据加载完成 | 6张数据卡片渲染完成 | 所有卡片圆角12px、间距16px、阴影shadow-sm、边框border-card统一 | 视觉 |
| AC-03 | 某项数据不可用 | 对应卡片显示空状态 | 空状态有图标+文字描述，样式统一（居中、灰色图标、14px文字） | 视觉 |
| AC-04 | 现有useSystemData单元测试 | 执行vitest run | 所有37个测试全部通过，0个失败 | 功能 |
| AC-05 | E2E测试配置 | 执行playwright test | 所有断言与实际UI匹配，无定位器错误 | 功能 |
| AC-06 | Benchmarks和Docs页面 | 执行E2E测试 | 有基础可见性测试覆盖 | 功能 |
| AC-07 | Dashboard不同屏幕宽度 | 切换宽度 | >=1400px 3列, >=768px 2列, <768px 1列 | 视觉 |

## 隐含需求

- 网络请求失败 → 显示空状态卡片 + 重试按钮
- 后端服务未启动 → 所有数据显示空状态 + TopBar offline状态

## 数据接口

现有API无需修改，依赖：
- `/api/system/status` → SystemStatus
- `/api/system/history` → SystemHistoryEntry[]
- `/api/health/alert` → HealthAlert
- `/api/gpu/summary` → GPUSummary
- `/api/token/stats` → TokenStats
- `/api/models` → ModelStatus
