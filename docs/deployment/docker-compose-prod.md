# 生产环境部署

## 架构说明

生产环境使用根目录 `docker-compose.yml` 一键部署全部 4 个服务。

```
用户 → Nginx (8080→80) → aiclient2api (3000) → app-controller (5000) → Redis (6379)
                            ↓
                         vLLM (8000, 容器内)
```

## 服务清单

| 服务 | 容器名 | 端口映射 | 基础镜像 |
|------|--------|---------|---------|
| redis | ai-os-redis | 6379:6379 | redis:7.2-alpine |
| ai-controller | ai-os-controller | 5000:5000 | nvidia/cuda:12.1.1 (自建) |
| aiclient | ai-os-aiclient | 3000:3000 | justlikemaki/aiclient-2-api:latest |
| frontend | ai-os-frontend | 8080:80 | nginx:alpine (自建) |

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
# ai-os-redis       running   0.0.0.0:6379->6379/tcp
# ai-os-controller  running   0.0.0.0:5000->5000/tcp
# ai-os-aiclient    running   0.0.0.0:3000->3000/tcp
# ai-os-frontend    running   0.0.0.0:8080->80/tcp
```

### 3. 验证

```bash
# 检查各服务健康状态
curl http://localhost:5000/health
curl http://localhost:3000/health
curl http://localhost:8080

# Redis 连接
docker exec ai-os-redis redis-cli ping
# 预期输出：PONG
```

## 端口说明

### 对外暴露端口

| 端口 | 服务 | 用途 |
|------|------|------|
| 8080 | frontend | 用户访问入口 |
| 5000 | ai-controller | API 服务（可设为内部） |
| 3000 | aiclient | API 网关（可设为内部） |
| 6379 | Redis | 缓存服务（建议仅内网） |

### 安全建议

- 仅对外暴露 8080（前端 Nginx）
- Redis (6379) 绑定内网，禁止公网访问
- 后端和网关通过 Docker 内部网络通信

```yaml
# 如需限制端口暴露，修改 docker-compose.yml：
redis:
  ports:
    - "127.0.0.1:6379:6379"  # 仅本机访问

ai-controller:
  ports:
    - "127.0.0.1:5000:5000"  # 仅本机访问

aiclient:
  ports:
    - "127.0.0.1:3000:3000"  # 仅本机访问
```

## Nginx 配置

前端容器使用 `frontend/nginx.conf`，关键配置：

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    # SPA 路由支持
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API 代理（容器内）
    location /api/ {
        proxy_pass http://localhost:5000/;
    }

    # 静态资源缓存
    location /static/ {
        expires 30d;
    }
}
```

> **注意**：Docker 容器内 Nginx 代理到 `localhost:5000`，即同容器内的后端。如果前后端是独立容器，应改为 Docker 服务名 `http://ai-controller:5000`。

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
