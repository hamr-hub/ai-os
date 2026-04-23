# 生产环境部署

## 架构说明

生产环境使用根目录 `docker-compose.yml` 一键部署全部 5 个服务。

```
用户 → Nginx (30000→80) → aiclient2api (3000) → app-controller (35000) / go-vllm-api (35001) → Redis (6379)
                            ↓
                         vLLM (8000, 容器内)
```

## 服务清单

| 服务 | 容器名 | 端口映射 | 基础镜像 |
|------|--------|---------|---------|
| redis | ai-os-redis | 6379:6379 | redis:7.2-alpine |
| ai-controller | ai-os-controller | 35000:35000 | nvidia/cuda:12.1.1 (自建) |
| go-vllm-api | ai-os-go-vllm-api | 35001:35001 | go-vllm-api (自建) |
| aiclient | ai-os-aiclient | 3000:3000 | justlikemaki/aiclient-2-api:latest |
| frontend | ai-os-frontend | 30000:80 | nginx:alpine (自建) |

## 启动步骤

### 1. 准备配置

```bash
# 环境变量
cp .env.example .env
# 编辑 .env，至少修改：
# - SECRET_KEY=<随机密钥>
# - REDIS_URL=redis://redis:6379  (Docker 内部网络)
# - ALLOWED_ORIGINS=<你的域名>

# 后端配置（如需自定义模型）
cp app-controller/config.yaml config.yaml
```

### 2. 构建与启动

```bash
# 构建所有镜像
docker compose build

# 后台启动
docker compose up -d

# 查看状态
docker compose ps

# 预期输出：
# ai-os-redis          running   0.0.0.0:6379->6379/tcp
# ai-os-controller     running   0.0.0.0:35000->35000/tcp
# ai-os-go-vllm-api    running   0.0.0.0:35001->35001/tcp
# ai-os-aiclient       running   0.0.0.0:3000->3000/tcp
# ai-os-frontend       running   0.0.0.0:30000->80/tcp
```

### 3. 验证

```bash
# 检查各服务健康状态
curl http://localhost:35000/health
curl http://localhost:35001/health
curl http://localhost:3000/health
curl http://localhost:30000

# Redis 连接
docker exec ai-os-redis redis-cli ping
# 预期输出：PONG
```

## 端口说明

### 对外暴露端口

| 端口 | 服务 | 用途 |
|------|------|------|
| 30000 | frontend | 用户访问入口 |
| 35000 | ai-controller | Python API 管理接口（可设为内部） |
| 35001 | go-vllm-api | Go API 推理接口（可设为内部） |
| 3000 | aiclient | API 网关（可设为内部） |
| 6379 | Redis | 缓存服务（建议仅内网） |

### 安全建议

- 仅对外暴露 30000（前端 Nginx）
- Redis (6379) 绑定内网，禁止公网访问
- 后端和网关通过 Docker 内部网络通信

```yaml
# 如需限制端口暴露，修改 docker-compose.yml：
redis:
  ports:
    - "127.0.0.1:6379:6379"  # 仅本机访问

ai-controller:
  ports:
    - "127.0.0.1:35000:35000"  # 仅本机访问

go-vllm-api:
  ports:
    - "127.0.0.1:35001:35001"  # 仅本机访问

aiclient:
  ports:
    - "127.0.0.1:3000:3000"  # 仅本机访问
```

## Nginx 配置

前端容器使用 `frontend/nginx.conf`，关键配置：

```nginx
upstream python_backend {
    server ai-controller:35000;
}

upstream go_backend {
    server go-vllm-api:35001;
}

server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    # SPA 路由支持
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API 代理（容器间使用 Docker 服务名）
    location /api/manage/ {
        proxy_pass http://python_backend/manage/;
    }

    location /v1/ {
        proxy_pass http://go_backend/v1/;
    }

    # 静态资源缓存
    location /static/ {
        expires 30d;
    }
}
```

> **注意**：Docker 容器内 Nginx 使用 Docker 服务名（`ai-controller:35000`、`go-vllm-api:35001`）进行代理，而不是 localhost。

## 数据持久化

Docker Compose 定义了 `redis_data` 卷用于 Redis 数据持久化。其他数据通过挂载卷实现：

| 挂载路径 | 说明 |
|---------|------|
| `./config.yaml:/app/config.yaml` | 后端配置文件 |
| `./app-controller/logs:/app/logs` | 日志目录 |
| `./aiclient2api/data:/app/data` | aiclient2api 数据 |
| `./aiclient2api/configs:/configs` | aiclient2api 配置 |

## 日志管理

各服务配置了日志轮转：

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "50m"   # 单文件最大 50MB
    max-file: "5"     # 最多保留 5 个文件
```

查看日志：

```bash
# 全部日志
docker compose logs -f

# 单服务日志
docker compose logs -f ai-controller
docker compose logs -f frontend

# 最近 100 行
docker compose logs --tail 100 ai-controller
```

## 更新部署

```bash
# 拉取最新代码
git pull

# 重新构建并启动
docker compose up -d --build

# 仅更新前端
docker compose up -d --build frontend

# 仅更新后端
docker compose up -d --build ai-controller
```

## 回滚

```bash
# 查看镜像历史
docker images | grep ai-os

# 回退到指定版本
docker compose down
# 修改镜像 tag 或 checkout 对应 commit
docker compose up -d
```
