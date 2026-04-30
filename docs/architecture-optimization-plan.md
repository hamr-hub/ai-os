# AI-OS 系统架构优化方案

> ⚠️ **本文档已被新架构取代**。当前架构采用双路径分层设计：
> - **C端推理**: aiclient2api(Node后端) → provider → go-vllm-api → 推理引擎
> - **B端管控**: Frontend/插件 → Python → 引擎启停/模型管理
> 
> 详见 [docs/agent/architecture.md](../agent/architecture.md) 的最新架构设计。
> 
> 以下内容为历史方案参考，不再作为当前实施计划。

---

> 当前问题：服务过重、资源冗余、架构复杂

---

## 📊 当前架构问题分析

### 1. 服务冗余严重

**现状：**
```
前端 (30000) 
  ↓
aiclient2api 网关 (3000)  ← 冗余！前端已有nginx代理
  ↓
app-controller (35000) + go-vllm-api (35001)  ← 功能重叠
  ↓
vLLM (8000)
```

**问题：**
- 5个独立服务（Redis、app-controller、go-vllm-api、aiclient2api、frontend）
- 请求链路：前端 → nginx → aiclient2api → go-vllm-api → vLLM（5层）
- app-controller 和 go-vllm-api 都提供 `/manage/*` 和 `/v1/*` 接口
- aiclient2api 网关功能与前端 nginx 代理重叠

### 2. 资源浪费

**GPU 资源：**
- `ai-controller` 和 `go-vllm-api` 都配置 `count: all`（请求所有GPU）
- 当前 GPU 使用率：0%（空闲）
- 两个容器争夺同一GPU资源

**内存使用：**
```
CONTAINER        MEM USAGE
ai-os-frontend   91.41 MiB
aiclient         52.52 MiB
```
- 总内存60GB，当前仅使用10GB
- 服务容器数过多，每个都有独立开销

### 3. 架构复杂度高

**维护成本：**
- 5个服务需要独立部署、监控、日志管理
- Docker Compose 配置复杂
- 服务间依赖关系复杂（Redis → Controller → Go-vllm → Aiclient → Frontend）

**性能瓶颈：**
- 多层代理增加请求延迟
- 每层都有独立的连接池、超时配置
- 健康检查频繁（30s间隔）

---

## 🎯 优化方案

### 方案一：服务合并（⭐ 推荐）

**核心思路：** 合并功能重叠的后端服务，移除冗余网关

#### 架构设计

```
┌─────────────────────────────────────────────┐
│              前端层 (Vue 3)                  │
│         Nginx (30000) + Vite Dev (30001)     │
│         ├─ /api/* → 后端管理接口              │
│         └─ /v1/*  → 后端推理接口              │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│         统一后端服务 (Go/Python)              │
│              端口: 35000                      │
│         ├─ /api/manage/*  管理接口            │
│         ├─ /v1/*          OpenAI兼容接口       │
│         ├─ /health        健康检查            │
│         └─ 内置缓存替代Redis                  │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│              vLLM 推理引擎                    │
│              端口: 8000 (内部)                 │
└─────────────────────────────────────────────┘
```

#### 具体优化措施

**1. 合并后端服务**
- 将 `app-controller` (Python) 和 `go-vllm-api` (Go) 合并为单一服务
- **推荐保留 Go 版本**（性能更好、资源占用更低）
- 在 go-vllm-api 基础上增加管理接口功能

**优势：**
- 减少一个容器（节省 ~100MB 内存）
- 简化部署和维护
- 消除服务间通信开销

**2. 移除 aiclient2api 网关**
- 前端 nginx 已具备代理功能
- 直接在 nginx 中配置路由规则
- 如需鉴权/限流，使用 nginx 模块（lua/openresty）

**配置示例（nginx）：**
```nginx
# 管理接口代理
location /api/manage/ {
    proxy_pass http://backend:35000/manage/;
}

# 推理接口代理
location /v1/ {
    proxy_pass http://backend:35000/v1/;
    # 限流
    limit_req zone=api burst=20 nodelay;
    # 鉴权
    auth_request /auth;
}
```

**3. 优化资源分配**
```yaml
# docker-compose.yml
ai-backend:  # 统一后端
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1  # 明确指定1个GPU，而非all
            capabilities: [gpu]
  # 移除不必要的 volumes
  # 移除 docker.sock 挂载（除非必需）
```

**4. 内置缓存替代 Redis**
- 对于中小规模部署，使用进程内缓存（Go: sync.Map / Python: cachetools）
- 仅在需要分布式缓存时保留 Redis
- 减少一个服务容器

#### 优化效果预估

| 指标 | 优化前 | 优化后 | 改善 |
|------|--------|--------|------|
| 服务数量 | 5个 | 3个 | ↓40% |
| 内存占用 | ~150MB+ | ~100MB | ↓33% |
| 请求链路 | 5层 | 3层 | ↓40% |
| 部署复杂度 | 高 | 低 | 显著降低 |
| GPU冲突 | 是 | 否 | 完全解决 |

---

### 方案二：分层优化（保留现有架构）

**核心思路：** 保持服务拆分，但优化资源配置和依赖关系

#### 具体措施

**1. 明确服务职责边界**
```
app-controller (35000):  专职管理接口
  - 模型管理
  - GPU监控
  - 系统状态
  - 缓存管理

go-vllm-api (35001):     专职推理接口
  - OpenAI兼容API
  - vLLM代理
  - 请求路由
```

**2. 限制GPU资源**
```yaml
ai-controller:
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            device_ids: ['0']  # 仅使用GPU 0（管理用途）
            capabilities: [gpu]

go-vllm-api:
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            device_ids: ['0']  # 使用GPU 0（推理用途）
            capabilities: [gpu]
```

**3. 优化 aiclient2api**
- 评估是否真的需要独立网关
- 如果仅做简单转发，用 nginx 替代
- 如果需要高级功能（鉴权、限流、熔断），保留但优化配置

**4. 调整健康检查间隔**
```yaml
healthcheck:
  interval: 60s    # 从30s改为60s
  timeout: 5s      # 从10s改为5s
  retries: 2       # 从3次改为2次
  start_period: 30s # 从60s改为30s
```

---

### 方案三：轻量级架构（极简方案）

**核心思路：** 完全重构为单一后端，适合个人/小团队使用

#### 架构设计

```
┌─────────────────────────────────────────────┐
│         FastAPI/Go 单体应用                   │
│         端口: 35000                           │
│         ├─ 静态文件服务 (前端)                 │
│         ├─ REST API                          │
│         └─ WebSocket                         │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│              vLLM 推理引擎                    │
└─────────────────────────────────────────────┘
```

#### 特点
- 仅2个服务：应用 + vLLM
- 无需 Docker Compose，单容器部署
- 内置所有功能（缓存、监控、管理）
- 适合资源受限环境

---

## 📋 实施计划

### 阶段一：立即优化（1-2天）

- [ ] 移除 `aiclient2api` 网关，前端nginx直接代理
- [ ] 调整GPU资源分配（明确指定设备）
- [ ] 优化健康检查配置
- [ ] 清理不必要的volume挂载

### 阶段二：服务合并（1周）

- [ ] 评估 app-controller 和 go-vllm-api 功能重叠
- [ ] 设计统一后端API
- [ ] 迁移管理接口到 go-vllm-api（或反之）
- [ ] 测试验证
- [ ] 更新前端API路由

### 阶段三：架构重构（按需）

- [ ] 评估是否引入 Redis 的必要性
- [ ] 实现内置缓存
- [ ] 性能压测
- [ ] 文档更新

---

## 🎬 快速开始：方案一实施

### Step 1: 移除 aiclient2api

**修改 docker-compose.yml：**
```yaml
services:
  # 删除 aiclient 服务
  # 前端直接代理到后端
```

**修改前端 nginx 配置：**
```nginx
# frontend/nginx.conf
server {
    listen 30000;
    
    # 静态文件
    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }
    
    # API代理
    location /api/ {
        proxy_pass http://ai-controller:35000;
    }
    
    # v1代理
    location /v1/ {
        proxy_pass http://go-vllm-api:35001;
    }
}
```

### Step 2: 优化资源配置

**修改 docker-compose.yml：**
```yaml
ai-controller:
  # 移除 gpu 资源（如果仅做管理，不需要GPU）
  # 或限制为特定设备
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            device_ids: ['0']
            capabilities: [gpu]

go-vllm-api:
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            device_ids: ['0']
            capabilities: [gpu]
```

### Step 3: 验证部署

```bash
# 停止所有服务
docker compose down

# 重新构建并启动
docker compose up -d --build

# 检查服务状态
docker compose ps

# 查看资源使用
docker stats
```

---

## 📊 性能监控

### 关键指标

| 指标 | 目标值 | 监控方式 |
|------|--------|----------|
| CPU使用率 | < 50% | `docker stats` |
| 内存使用 | < 200MB | `docker stats` |
| GPU使用率 | 按需 | `nvidia-smi` |
| 请求延迟 | < 100ms | 应用日志 |
| 服务可用性 | > 99.9% | 健康检查 |

### 监控命令

```bash
# 实时资源监控
watch -n 5 'docker stats --no-stream && echo "---" && nvidia-smi'

# 服务健康检查
curl -s http://localhost:35000/health | jq
curl -s http://localhost:35001/health | jq

# 日志分析
docker compose logs -f --tail=100
```

---

## ⚠️ 注意事项

1. **向后兼容**：确保API路径不变，前端无需大改
2. **数据迁移**：如果有 Redis 数据，需要迁移方案
3. **灰度发布**：建议先在测试环境验证
4. **回滚计划**：保留旧配置，随时可回滚

---

## 📞 后续支持

- 更新部署文档：`docs/deployment/deployment-guide.md`
- 更新架构文档：`docs/agent/architecture.md`
- 更新端口参考：`docs/deployment/port-reference.md`

---

> 生成时间：2026-04-26
> 建议优先实施方案一，可在1-2天内完成初步优化
