# 研究发现: AIOS-ARCH-FIX

## 背景
系统架构双路径分层: C端推理(aiclient→Go→vLLM) + B端管控(Frontend→Python→引擎管理)

## 关键发现

### 发现 1: 三方配置漂移 (P0)
- **来源**: 深度代码审查 — 3份 config.yaml 对比
- **内容**: root/app-controller/go-vllm-api 三份 config 模型定义/元数据/Redis DB 完全不一致
- **影响**: Python/Go 展示不同模型列表, 模型切换可能失败
- **日期**: 2026-04-30

### 发现 2: Docker 网络全链路错误 (P0)
- **来源**: frontend/nginx.conf, docker-compose.yml, main.go, backend-client.js
- **内容**: 4处硬编码192.168.7.103, frontend Docker nginx用localhost, 端口映射错
- **影响**: Docker 环境下服务完全不可达
- **日期**: 2026-04-30

### 发现 3: Go admin_whitelist.go 未提交 (P0)
- **来源**: git status `?? go-vllm-api/internal/middleware/admin_whitelist.go`
- **内容**: main.go 已引用此middleware但文件未commit → Go服务编译依赖此文件
- **影响**: 任何clone/CI都会编译失败
- **日期**: 2026-04-30

### 发现 4: B端无鉴权 (P0)
- **来源**: app-controller/main.py 只有CORS+RateLimit+Timeout中间件
- **内容**: 所有 /manage/* POST/PUT/DELETE 裸暴露
- **影响**: 任何人可操作引擎启停/模型切换
- **日期**: 2026-04-30

### 发现 5: GGUF模型配置类型错误 (P1)
- **来源**: app-controller/config.yaml
- **内容**: Gemma-4-31B-GGUF-Q4/Qwen3.6-35B-GGUF-Q4 service=vllm-aiclient(应为llama_cpp)
- **影响**: Python会尝试用vLLM subprocess启动GGUF模型, 必失败
- **日期**: 2026-04-30

### 发现 6: Redis DB不一致 (P1)
- **来源**: app-controller/config.yaml db=5, root/go db=0, docker-compose REDIS_DB=0
- **内容**: Python本地用db5, Docker用db0 → 数据隔离/碰撞
- **影响**: Docker和本地环境行为不一致
- **日期**: 2026-04-30

## 技术笔记
- Go admin_whitelist.go 实现了 IP CIDR 白名单 + GET/HEAD 只读放行 + 写操作内网限制
- Python 侧需实现类似中间件, 与 Go 端策略对齐
- root config.yaml 应作为唯一权威配置源, Docker mount 到各容器
