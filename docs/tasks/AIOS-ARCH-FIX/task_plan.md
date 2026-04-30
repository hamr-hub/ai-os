# 任务计划: AIOS-ARCH-FIX 系统架构完善

## 目标
基于架构文档修正所有模块缺口: 配置统一、Docker修复、端口对齐、鉴权

## 当前阶段
Phase 1

## 阶段规划

### Phase 1: 需求与发现
- [x] 深度代码审查, 识别4模块缺口
- [x] 生成 requirement.yaml + requirement.md
- [x] 复杂度评分 83/100 → 触发持久化规划
- **Status:** complete

### Phase 2: 技术方案
- [ ] 调用 tech-solution skill 生成 tech-solution.yaml
- [ ] 设计配置统一策略
- [ ] 设计 Docker 网络修复策略
- [ ] 设计鉴权方案
- **Status:** pending

### Phase 3: 任务拆解与验证
- [ ] 调用 plan-from-tech-solution 生成 plan.yaml + plan.md
- [ ] 调用 verify-from-tech-solution 校验一致性
- **Status:** pending

### Phase 4: P0 实现
- [ ] T1: 统一配置文件(root config.yaml 包含所有字段)
- [ ] T2: Frontend Docker 端口修复
- [ ] T3: Docker nginx.conf upstreams 改服务名
- [ ] T4: admin_whitelist.go 提交
- [ ] T5: Python B端鉴权中间件
- **Status:** pending

### Phase 5: P1 实现
- [ ] T6: 硬编码IP → 环境变量/Docker服务名
- [ ] T7: Vite dev proxy 端口对齐
- [ ] T8: GGUF service 类型修正
- [ ] T9: docker-compose 环境变量补全
- [ ] T10: Docker nginx /ws/ 路由
- [ ] T11: Redis DB 统一为 db0
- **Status:** pending

### Phase 6: 文件变更审查
- [ ] 调用 Stage 7.6 审查所有变更
- **Status:** pending

## 关键问题
1. root config.yaml 是否应作为唯一配置源? → Yes, Python/Go 各自 mount 或 copy
2. 鉴权方案: JWT vs IP白名单? → 先实现 IP白名单(与Go admin_whitelist对齐), JWT 后续
3. Docker 端口: 30000:80 vs 容器内监30000? → 30000:80 更简单

## 决策记录
| 决策 | 理由 |
|------|------|
| 配置统一为 root config.yaml | 减少三方漂移, Docker mount 同一文件 |
| IP白名单先于JWT | 与Go侧admin_whitelist策略对齐, 快速实现 |
| Docker端口 30000:80 | 容器内nginx监80是标准, 外部映射30000 |

## 错误记录
| 错误 | 尝试次数 | 解决方案 |
|------|---------|---------|
|      |         |         |
