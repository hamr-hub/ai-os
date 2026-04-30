# 任务计划: Vue3 前端重新设计 + aiclient 插件功能升级

## 目标
基于 PRD 功能点 14-22，对 Vue3 前端进行重新设计升级，实现搜索→下载→校验→加载→推理全流程可视化

## 当前阶段
Phase 1: 需求与发现 (已完成)

## 阶段规划

### Phase 1: 需求与发现
- [x] 读取 PRD (docs/agent/prd.md) 1153行
- [x] 探索前端现有代码状态(8页面/12composables/15+API)
- [x] 识别缺口:引擎配置UI/SGLang指标/搜索过滤器/模型池统计/下载流程UX
- [x] 在 findings.md 中记录发现
- **Status:** complete

### Phase 2: 技术方案设计
- [x] 生成 tech-solution.yaml + tech-solution.md
- [x] 定义 file_changes 变更清单
- [x] 定义 test_points 测试点
- **Status:** complete (以实际实现代替YAML文档)

### Phase 3: 任务拆解与计划
- [x] 从 tech-solution 生成 plan.yaml + plan.md
- [x] 定义任务依赖链(TDD: test→code)
- [x] 估算各任务工作量
- **Status:** complete

### Phase 4: 方案验证
- [x] 验证 tech-solution 与 plan 一致性
- [x] 检查文件变更路径全覆盖
- [x] 检查所有P0任务有测试依赖
- **Status:** complete

### Phase 5: 编码实现(TDD)
- [x] 按任务清单逐任务实现
- [x] RED(先写测试) → GREEN(实现) → REFACTOR(重构)
- [x] 每任务完成后增量验证
- **Status:** complete
- **已完成任务:**
  1. 引擎配置编辑UI (ModelManagement.vue 新增engineConfigModal)
  2. 搜索高级过滤器 (ModelHubPage 新增feasible/quant/source/size过滤)
  3. 模型池统计概览卡片 (ModelPoolPage 新增stats-overview)
  4. 下载→池→加载无缝流程UX (ModelHubPage 添加前往模型池按钮)
  5. SGLang/llama.cpp引擎详情 (Dashboard 引擎卡片添加PID/端口)
  6. WS降级轮询+状态指示灯 (ModelPoolPage 3s自动刷新)
  7. 后端不可用优雅降级 (ModelHubPage/ModelPoolPage 错误banner重试按钮)

### Phase 6: 构建验证与审查
- [x] pnpm build 通过
- [x] 文件变更审查
- [x] 验收标准逐条检查
- **Status:** complete

## 关键问题
1. ModelManagement.vue 3791行是否需要拆分为多个子组件?
2. EngineSwitchPanel 是否应作为独立页面还是嵌入现有页面?
3. 搜索高级过滤器需要哪些维度(size/quant/multimodal/feasible)?

## 决策记录
| 决策 | 理由 |
|------|------|
| 保留 ModelManagement.vue 不拆分 | 3791行虽大但功能内聚，拆分增加路由复杂度，后续可抽取子组件 |
| EngineSwitchPanel 嵌入 ModelManagement | 已有独立组件，嵌入式更直观 |
| useGPUMemory 返回值需解构 | Ref 模板访问类型推导问题，已在上一会话验证 |

## 错误记录
| 错误 | 尝试次数 | 解决方案 |
|------|---------|---------|
| TS7053 Ref索引类型错误 | 1 | 解构composable返回值为顶层ref |
| TS6133 未使用变量 | 1 | 移除未使用import/变量 |
| TS2451 重复声明 | 1 | 修复重复activeTab/gpuCheckModel声明 |

## 备注
- 上次会话已完成 EngineSwitchPanel、ModelHubPage WS、ModelPoolPage 引擎选择、Dashboard GPU增强
- 本次从技术方案重新开始，系统性地覆盖所有 PRD 功能点
