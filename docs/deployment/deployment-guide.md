# 部署指南总览

## 部署场景

| 场景 | 说明 | 文档 |
|------|------|------|
| 开发环境 | 前后端独立运行，热更新 | [开发环境部署](./docker-compose-dev.md) |
| 生产环境 | 全栈容器化部署 (5 服务) | [生产环境部署](./docker-compose-prod.md) |
| GPU 环境 | GPU 加速推理 + vLLM | [GPU 环境部署](./docker-compose-gpu.md) |

## 端口对照

详见 [端口参考手册](./port-reference.md)。

## 服务架构

```
用户 → 前端 (开发 30001 / 生产 30000)
         ↓
     aiclient2api (3000) — API 网关 / 鉴权
         ↓
     go-vllm-api (35001) — 推理接口 /v1
     app-controller (35000) — 管理接口 /manage
         ↓
     vLLM (8000) — 模型推理
     Redis (6379) — 缓存 / 队列
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PORT` | 35000 | Python 后端端口 |
| `GO_PORT` | 35001 | Go 后端端口 |
| `CLIENT_PORT` | 3000 | aiclient2api 端口 |
| `REDIS_URL` | redis://localhost:6379 | Redis 连接 |
| `SECRET_KEY` | — | 安全密钥 (必填) |
| `LOG_LEVEL` | INFO | 日志级别 |
| `MODEL_BASE_PATH` | /mnt/pve_models | 模型存储路径 |

---

> 更新于 2026-04-24
