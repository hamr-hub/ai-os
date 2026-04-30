# AIOS-ARCH-FIX 技术方案

> 基于 system architecture 双路径模型修正所有模块缺口

---

## 核心策略

**配置统一**: 以 root `config.yaml` 为唯一权威配置源, Python/Go 各自 mount 或引用
**Docker 修复**: 所有容器间通信使用 Docker 服务名, 端口映射对齐
**鉴权对齐**: Python 侧实现与 Go admin_whitelist 等价的 IP 白名单中间件

---

## 变更清单 (17 文件)

### P0 (5 文件)

| 文件 | 变更类型 | 描述 |
|------|---------|------|
| `config.yaml` | rewrite | 合3份为1份: Python(model_groups/vllm_params/feature_flags) + Go(discovery/llama_cpp) + 全模型 |
| `frontend/nginx.conf` | modify | upstreams→Docker服务名 + /ws/ WebSocket + /v1/test/ →Python + listen 80 |
| `go-vllm-api/internal/middleware/admin_whitelist.go` | git-add | 提交untracked文件 |
| `app-controller/middleware/admin_whitelist.py` | create | Python IP白名单中间件(与Go策略对齐) |
| `app-controller/main.py` | modify | 添加AdminWhitelistMiddleware到中间件栈 |

### P1 (8 文件)

| 文件 | 变更类型 | 描述 |
|------|---------|------|
| `docker-compose.yml` | modify | go-vllm-api volume→root config; aiclient加环境变量; frontend 30000:80; go加PYTHON_BACKEND_URL |
| `frontend/vite.config.ts` | modify | VITE_BACKEND默认→35000; VITE_GATEWAY默认→35001; health路由到Python |
| `frontend/.env.development` | modify | 加VITE_BACKEND/VITE_GATEWAY环境变量 |
| `go-vllm-api/cmd/server/main.go` | modify | PYTHON_BACKEND_URL默认→localhost:35000 |
| `aiclient2api/plugins/ai-os-manager/backend-client.js` | modify | 默认URL→localhost |
| `frontend/nginx_30000.conf` | modify | upstreams改localhost或环境变量 |
| `app-controller/config.yaml` | delete | 冗余副本→引用root |
| `go-vllm-api/configs/config.yaml` | delete | 冗余副本→引用root |

### 配置加载适配 (4 文件)

| 文件 | 变更类型 | 描述 |
|------|---------|------|
| `app-controller/core/config.py` | modify | 从root config加载所有字段 |
| `go-vllm-api/internal/config/config.go` | modify | 从root config加载所有字段 |
| `frontend/Dockerfile` | no-change | 保持EXPOSE 80 |
| `frontend/nginx.conf` | modify | listen 80(Docker内) |

---

## 统一配置方案

root `config.yaml` 合并策略:
- 模型列表: 以 root 为基准, 补充 Python 侧 `vllm_params` 和 `feature_flags`
- GGUF模型: service 统一为 `llama_cpp` (来自 root), port 为 8001/8002
- Gemma-4 supports_images/tool_calling: 统一为 true (root/Go 一致)
- Qwen3-235B required_memory: 统一为 120GB (root/Go 一致)
- Redis db: 统一为 0
- 新增 Python 独有字段: model_groups, vllm_params(per model), feature_flags, engines.hub/sglang
- 新增 Go 独有字段: discovery, llama_cpp

---

## 鉴权方案

Python AdminWhitelistMiddleware:
- 默认放行内网 CIDR: 127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16
- GET/HEAD 只读放行(任何IP)
- POST/PUT/DELETE/PATCH 仅内网IP可操作
- 与 Go admin_whitelist.go 策略完全对齐

---

## Docker 网络修复

| 服务 | 修复项 |
|------|--------|
| frontend | 端口 30000:80, nginx upstreams 用 Docker 服务名 |
| go-vllm-api | PYTHON_BACKEND_URL=http://ai-controller:35000, config mount ./config.yaml |
| aiclient | GO_BACKEND_URL=http://go-vllm-api:35001, PYTHON_BACKEND_URL=http://ai-controller:35000 |
| ai-controller | REDIS_DB=0(已正确) |

---

## 测试计划

| 测试 | 类型 | 描述 |
|------|------|------|
| test_config_loading.py | unit | Python从root config加载所有字段 |
| main_test.go | unit | Go从root config加载所有字段 |
| test_admin_whitelist.py | unit | IP白名单中间件验证 |
| test_docker_config.py | integration | docker-compose端口/环境变量验证 |
