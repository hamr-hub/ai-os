# AIOS-ARCH-FIX 任务清单

> 来源: tech-solution.yaml | 范围: P0+P1 | 测试覆盖目标: 80%

---

## 任务概览 (12 任务: 3 test + 9 code)

| ID | 优先级 | 类型 | 标题 | 依赖 |
|----|--------|------|------|------|
| T1-test | P0 | test | Python admin_whitelist 单元测试 | 无 |
| T2-test | P0 | test | Python config 统一加载测试 | 无 |
| T3-test | P1 | test | Go admin_whitelist 单元测试 | 无 |
| P0-1 | P0 | code | 统一配置文件(root config.yaml) | T2-test |
| P0-2 | P0 | code | Python admin_whitelist 中间件 | T1-test |
| P0-3 | P0 | code | git add admin_whitelist.go | T3-test |
| P0-4 | P0 | code | frontend nginx.conf Docker修复 | 无 |
| P1-1 | P1 | code | docker-compose.yml 修复 | P0-1,P0-4 |
| P1-2 | P1 | code | Vite dev proxy 端口对齐 | 无 |
| P1-3 | P1 | code | 硬编码IP→环境变量 | 无 |
| P1-4 | P1 | code | Python/Go config 加载适配 | P0-1,T2-test |
| P1-5 | P1 | code | 删除冗余配置副本 | P1-4 |

---

## P0 任务详解

### T1-test: Python admin_whitelist 中间件测试
- 文件: `app-controller/tests/test_admin_whitelist.py`
- 场景: 内网IP POST放行, 外网IP POST 403, 任何IP GET放行

### T2-test: Python config 统一加载测试
- 文件: `app-controller/tests/test_config_unified_loading.py`
- 场景: 从root config加载 model_groups/vllm_params/feature_flags/engines/llama_cpp

### P0-1: 统一配置文件
- 合3份config为root config.yaml
- 修正: GGUF service=llama_cpp, Gemma-4 supports_images=true, Redis db=0

### P0-2: Python admin_whitelist 中间件
- 与Go admin_whitelist.go 策略对齐
- 注册到 main.py 中间件栈

### P0-3: git add admin_whitelist.go
- 提交untracked文件, Go可编译

### P0-4: frontend nginx.conf Docker修复
- upstreams改Docker服务名
- 加/ws/ WebSocket路由
- listen 80

---

## P1 任务详解

### P1-1: docker-compose.yml 修复
- frontend 30000:80, go-vllm-api config mount root config
- aiclient/go 加环境变量

### P1-2: Vite dev proxy 端口对齐
- VITE_BACKEND→35000, VITE_GATEWAY→35001

### P1-3: 硬编码IP→环境变量
- main.go/backend-client.js/nginx_30000.conf

### P1-4: Python/Go config 加载适配
- 扩展config.py/config.go加载root config所有字段

### P1-5: 删除冗余配置副本
- git rm app-controller/config.yaml, go-vllm-api/configs/config.yaml
