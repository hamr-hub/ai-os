# 需求文档 - T20260422-001

> **标题**: 可配置Redis服务地址与系统美化优化  
> **创建时间**: 2026-04-22  
> **开发者**: heyongxian

---

## 📋 功能需求

### F001: Redis服务地址可配置化

- 支持通过环境变量 `REDIS_HOST`/`REDIS_PORT` 配置
- 支持在 `config.yaml` 中配置 `redis` 字段
- 默认值保持 `localhost:6379`
- 优先级：环境变量 > 配置文件 > 默认值

### F002: 使用 Mock vLLM 服务

- Mock 服务已存在于 `app-controller/scripts/mock_vllm_server.py`
- 需验证前端与 Mock 服务的接口兼容性
- 主要接口：`/health`, `/v1/models`, `/v1/chat/completions`

### F003: 美化 Frontend 页面

- 优化 Dashboard 视觉效果（卡片动画、渐变色、阴影）
- 增强 Sidebar 交互体验（折叠动画、激活状态）
- 统一色彩体系和组件风格

### F004: 美化 Python 工程

- 增强日志输出格式（结构化日志、颜色标记）
- 优化错误处理和提示信息
- 代码注释规范化

### F005: 功能验证与接口联调

- 前端独立功能正常
- 后端独立功能正常
- 前后端接口联调正常

---

## ✅ 验收标准

| ID | Given | When | Then | 优先级 |
|----|-------|------|------|--------|
| AC-001 | 环境变量设置了 REDIS_HOST | 启动服务 | 使用配置的地址 | P0 |
| AC-002 | config.yaml 包含 redis 字段 | 启动服务 | 使用配置文件地址 | P0 |
| AC-003 | 未配置 Redis | 启动服务 | 使用默认 localhost:6379 | P0 |
| AC-004 | Mock 服务运行中 | 访问 /v1/models | 显示正确模型列表 | P0 |
| AC-005 | 服务运行中 | 访问 Dashboard | 显示优化的 UI | P1 |
| AC-006 | 前端独立运行 | 测试所有页面 | 无报错交互流畅 | P1 |
| AC-007 | 后端独立运行 | 测试所有 API | 返回正确数据 | P1 |
| AC-008 | 前后端联调 | 测试完整流程 | 接口通信正常 | P0 |

---

## 🔧 技术上下文

**前端**: Vue 3.5 + TypeScript + Tailwind CSS 4 + Pinia  
**后端**: FastAPI + Python 3.11+ + Pydantic + YAML 配置

---

## ⚠️ 风险评估

- **风险等级**: LOW
- **功能点数**: 5
- **涉及文件预估**: 12
- **业务流程数**: 3
