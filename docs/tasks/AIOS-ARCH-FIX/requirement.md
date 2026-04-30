# AIOS-ARCH-FIX 需求文档

> 基于系统架构修正所有模块缺口 | 开发者: heyongxian | 2026-04-30

---

## 背景

系统架构文档已修正为双路径分层模型:
- **C端推理**: aiclient2api(Node) → provider → go-vllm-api → 推理引擎
- **B端管控**: Frontend/插件 → Python B端 → 引擎启停/模型管理

深度代码审查发现多个模块存在配置漂移、Docker 网络错误、端口不对齐、无鉴权等严重问题。

---

## P0 缺口 (必须修复)

### P0-1: 三方配置漂移
**根config.yaml / app-controller/config.yaml / go-vllm-api/configs/config.yaml** 模型定义、元数据、Redis DB 完全不一致:
- Gemma-4 supports_images: root=true, python=false, go=true
- Qwen3-235B required_memory: root=120GB, python=48GB
- GGUF 模型在 Python 中 service=vllm-aiclient(应为 llama_cpp)
- Redis DB: python=5, root/go=0
- go-vllm-api 缺 model_groups/vllm_params/engines/feature_flags

**AC-01/02**: 统一为一份 root config.yaml, 包含所有字段, Python/Go 各自配置为 root config 的 subset 或直接使用 root config

### P0-2: Frontend Docker 端口 Bug
Dockerfile EXPOSE 80, docker-compose 映射 30000:30000, 容器内 nginx 监 80 → 服务不可达

**AC-03**: 修复为 30000:80 或容器内 nginx 监 30000

### P0-3: Docker nginx.conf localhost upstreams
frontend/nginx.conf (Docker版) 用 localhost:3000/35000/35001 → 容器内无法访问其他服务

**AC-04**: 改为 Docker 服务名 (aiclient/ai-controller/go-vllm-api)

### P0-4: admin_whitelist.go 未提交
git status 显示 `?? go-vllm-api/internal/middleware/admin_whitelist.go`, 但 main.go 已引用 → Go 服务编译依赖此文件

**AC-05**: git add + commit 该文件

### P0-5: B端无鉴权
所有 /manage/* POST/PUT/DELETE 裸暴露, 架构文档标注为安全风险

**AC-06**: 至少实现 IP 白名单 + admin whitelist(Go 侧已有), Python 侧需加鉴权中间件

---

## P1 缺口 (应修复)

| ID | 问题 | AC | 涉及文件 |
|----|------|----|----|
| P1-1 | 4处硬编码 192.168.7.103 IP | AC-07 | main.go, backend-client.js, nginx_30000.conf |
| P1-2 | Vite dev proxy 默认端口错 | AC-08 | vite.config.ts, .env.development |
| P1-3 | GGUF model service 类型错 | AC-09 | app-controller/config.yaml |
| P1-4 | docker-compose 缺环境变量 | AC-10 | docker-compose.yml |
| P1-5 | Docker nginx 缺 /ws/ 路由 | AC-11 | frontend/nginx.conf |
| P1-6 | Redis DB 不一致 | AC-12 | config.yaml, docker-compose.yml |

---

## P2 缺口 (可延后)

- Go internal 包 0% 测试覆盖
- aiclient2api 插件无测试
- Python model_engine_scheduler/model_hub 无测试
- 旧 gpu-monitor-switch.disabled 残留
- Stream max duration 不可配置

---

## 验收标准

1. root config.yaml 包含 Python+Go 所需所有字段
2. app-controller/go-vllm-api config 与 root 对齐
3. Frontend Docker 端口映射正确
4. Docker nginx.conf 使用 Docker 服务名
5. admin_whitelist.go 已提交
6. B端 /manage/* 写操作有鉴权保护
7. 所有硬编码 IP 替换为环境变量/Docker 服务名
8. Vite dev proxy 默认端口对齐(35000/35001)
9. GGUF 模型 service=llama_cpp
10. docker-compose 设置必要环境变量
11. Docker nginx.conf 含 /ws/ WebSocket 路由
12. Redis DB 号全局统一(db0)
