# 需求文档: ai-os Vue3前端 + aiclient2api插件 测试计划与测试用例全覆盖

## 1. 业务目标

**目标用户**: 管理员/运维人员(B端)、C端开发者(推理API)

**解决的问题**: 前端Vue3管控面板和aiclient2api插件缺少系统性测试覆盖，当前仅有7个composable测试和3个store测试，大量新模块无测试保障

**成功指标**:
- 测试覆盖率 ≥80% (composable/store)
- 测试用例数 ≥100个
- vitest run 全PASS

## 2. 范围

**包含**:
- 21个前端composable单元测试
- 6个前端store单元测试
- API client关键函数测试
- 14个页面组件基础渲染测试
- 4条E2E关键路径测试
- aiclient2api插件核心功能测试

**不包含**:
- Go/Python后端测试
- 性能压测
- Docker部署测试

## 3. 关键交互路径

1. **查看GPU状态**: Dashboard → GPU概览 → vLLM指标
2. **切换模型**: ModelManagement → 选择模型 → 切换 → 查看进度
3. **搜索下载模型**: ModelHub → 搜索 → 下载 → 加载到池
4. **管理模型池**: ModelPool → 列表 → 加载/删除
5. **配置限流**: RateLimit → 修改配置 → 保存

## 4. 验收标准

| ID | Given | When | Then |
|----|-------|------|------|
| AC-01 | vitest已配置 | vitest run | 所有composable测试通过，覆盖率≥80% |
| AC-02 | vitest已配置 | vitest run | 所有store测试通过，覆盖率≥80% |
| AC-03 | vitest已配置 | vitest run | API client关键函数测试通过 |
| AC-04 | vitest已配置 | vitest run | 14个页面组件渲染测试通过 |
| AC-05 | Playwright已配置 | playwright test | 4条E2E关键路径通过 |
| AC-06 | 测试计划已生成 | 检查docs目录 | test-plan.yaml + test-plan.md存在 |

## 5. 隐含需求

| ID | 场景 | 说明 | 严重性 |
|----|------|------|--------|
| IR-01 | 网络异常/后端离线 | composable/store必须处理API错误场景 | P0 |
| IR-02 | WS断连降级 | usePolling/useGPU/useModelPool需测试降级逻辑 | P0 |
| IR-03 | 边界数据 | 数据/null/超大数据的渲染和计算 | P1 |

## 6. 代码现状

- 前端代码已全部实现(21个composable, 6个store, 14个页面)
- 已有7个composable测试: useGPU, useModels, useMarkdown, useSystemData, useTokenStats, useGPUChartDatasets(useGPUHistory同文件), connectionUtils, formatUtils
- 已有3个store测试: app, server, agentChat
- 需补充: 14个composable测试 + 3个store测试 + API client测试 + 页面渲染测试 + E2E测试

## 7. 门禁判定

**Verdict: PASS**
- 模糊度评分: 90/100
- P0缺口: 无
- P1缺口: 无(隐含需求已识别)
