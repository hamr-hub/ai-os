# 技术方案 - T20260422-001

> **版本**: 1.0 | **创建时间**: 2026-04-22

---

## 📦 文件变更清单

### 后端变更

| 文件 | 变更类型 | 说明 | AC |
|------|---------|------|-----|
| `core/config.py` | 修改 | 添加 Redis 配置支持 | AC-001~003 |
| `core/redis_client.py` | 修改 | 使用配置的 Redis 地址 | AC-001~003 |
| `config.yaml` | 修改 | 添加 redis 字段 | AC-002 |
| `core/logger.py` | 修改 | 美化日志输出 | AC-007 |

### 前端变更

| 文件 | 变更类型 | 说明 | AC |
|------|---------|------|-----|
| `style.css` | 修改 | 增强全局样式动画 | AC-005 |
| `views/Dashboard.vue` | 修改 | 优化视觉效果 | AC-005 |
| `components/Sidebar.vue` | 修改 | 优化交互体验 | AC-005 |
| `components/GPUMonitor.vue` | 修改 | 优化 GPU 监控样式 | AC-005 |
| `components/ModelManager.vue` | 修改 | 优化模型管理样式 | AC-005 |

---

## 🔧 实现要点

### Redis 配置优先级

```
环境变量 REDIS_HOST/REDIS_PORT
    ↓ (优先级最高)
config.yaml redis.host/redis.port
    ↓ (次优先级)
默认值 localhost:6379
```

### 日志格式优化

```
[2026-04-22 10:30:45] [INFO] [module] message
         ↑ 时间戳        ↑ 级别  ↑ 模块
```

### 前端样式增强

- 渐变色卡片背景
- 悬停时缩放动画 (scale 1.02)
- 平滑过渡 (transition 0.3s)
- 脉冲发光效果

---

## ⚠️ 风险评估

- **等级**: LOW
- **原因**:
  - 配置变更有默认值兜底
  - 样式美化不影响功能
  - Mock 服务已验证可用

---

## 🔄 回滚方案

1. 保留 `config.yaml.bak`
2. Git 回滚到当前版本
3. 前端样式可独立回滚
