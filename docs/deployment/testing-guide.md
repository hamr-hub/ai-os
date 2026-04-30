# 测试指南

## 测试环境端口配置

### 开发环境测试

| 测试对象 | 访问地址 | 端口 |
|---------|---------|------|
| 前端页面 | http://localhost:30001 | 30001 |
| Python 后端 API | http://localhost:35000 | 35000 |
| Python API 文档 | http://localhost:35000/docs | 35000 |
| Go 后端 API | http://localhost:35001 | 35001 |
| aiclient2api | http://localhost:3000 | 3000 |
| Redis | localhost:6379 | 6379 |

### Docker 环境测试

| 测试对象 | 访问地址 | 端口 |
|---------|---------|------|
| 前端页面 | http://localhost:30000 | 30000 |
| Python 后端 API | http://localhost:35000 | 35000 |
| Go 后端 API | http://localhost:35001 | 35001 |
| aiclient2api | http://localhost:3000 | 3000 |

## 健康检查测试

### 1. Python 后端服务

```bash
# 基础健康检查
curl -s http://localhost:35000/health | python -m json.tool

# Node.js 集成状态
curl -s http://localhost:35000/api/v1/status | python -m json.tool
```

### 2. Go 后端服务

```bash
# 基础健康检查
curl -s http://localhost:35001/health | python -m json.tool

# 模型列表
curl -s http://localhost:35001/v1/models | python -m json.tool
```

### 3. aiclient2api (开源项目+GPU插件, Node后端)

```bash
# 健康检查
curl -s http://localhost:3000/health

# C端推理测试（通过 Node 后端 provider 路由到 Go 限流代理）
curl -s http://localhost:3000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"Gemma-4-31B-Abliterated","messages":[{"role":"user","content":"Hello"}],"max_tokens":50}'
```

### 4. Redis 连接

```bash
# 直接连接
redis-cli -h localhost -p 6379 ping

# Docker 内连接
docker exec ai-os-redis redis-cli ping

# 检查 Redis 信息
docker exec ai-os-redis redis-cli info server
```

### 5. 前端页面

```bash
# 页面可访问性
curl -s -o /dev/null -w "%{http_code}" http://localhost:30001
# 预期输出：200
```

## 接口联调测试

### 1. 模型管理接口 (Python 后端 35000)

```bash
# 获取模型列表
curl -s http://localhost:35000/manage/models | python -m json.tool

# 启动模型
curl -X POST http://localhost:35000/manage/models/Gemma-4-31B-Abliterated/start

# 停止模型
curl -X POST http://localhost:35000/manage/models/Gemma-4-31B-Abliterated/stop

# 设为默认模型
curl -X POST http://localhost:35000/manage/models/Gemma-4-31B-Abliterated/default
```

### 2. GPU 监控接口 (Python 后端 35000)

```bash
# GPU 状态
curl -s http://localhost:35000/manage/gpu | python -m json.tool

# GPU 历史数据
curl -s "http://localhost:35000/manage/gpu/history?count=120" | python -m json.tool
```

### 3. 聊天补全接口 (Go 后端 35001)

```bash
# 通过 Go 后端直接调用
curl http://localhost:35001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Gemma-4-31B-Abliterated",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 50
  }'

# 通过 aiclient2api 网关调用
curl http://localhost:3000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Gemma-4-31B-Abliterated",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 50
  }'

# 流式响应测试
curl http://localhost:35001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Gemma-4-31B-Abliterated",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 50,
    "stream": true
  }'
```

### 4. 指标接口 (Go 后端 35001)

```bash
# 系统指标
curl -s http://localhost:35001/manage/metrics | python -m json.tool
```

## 前端 E2E 测试

### 手动测试流程

1. **仪表盘页面**
   - 开发环境访问 http://localhost:30001
   - Docker/生产环境访问 http://localhost:30000
   - 验证 GPU 监控数据显示
   - 验证模型列表加载
   - 验证使用统计图表渲染

2. **模型管理页面**
   - 点击侧边栏"模型管理"
   - 验证模型列表显示
   - 测试启动/停止模型操作
   - 测试设为默认模型操作

3. **Chat 页面**
   - 点击侧边栏"Chat"
   - 选择模型
   - 发送消息，验证响应
   - 测试流式输出

4. **主题切换**
   - 点击侧边栏底部主题按钮
   - 验证 light / dark / system 三种主题切换

5. **项目文档页面**
   - 点击侧边栏"项目文档"
   - 验证左侧目录树渲染
   - 验证点击文档项切换内容
   - 验证代码块高亮显示

## Docker 环境联调测试

### 完整测试脚本

```bash
#!/bin/bash
set -e

echo "=== AI OS Docker 联调测试 ==="

# 1. 检查所有容器运行
echo "1. 检查容器状态..."
docker compose ps

# 2. Redis 连通性
echo "2. 测试 Redis..."
docker exec ai-os-redis redis-cli ping

# 3. Python 后端健康检查
echo "3. 测试 Python 后端..."
curl -sf http://localhost:35000/health && echo " OK" || echo " FAIL"

# 4. Go 后端健康检查
echo "4. 测试 Go 后端..."
curl -sf http://localhost:35001/health && echo " OK" || echo " FAIL"

# 5. aiclient2api 健康检查
echo "5. 测试 aiclient2api..."
curl -sf http://localhost:3000/health && echo " OK" || echo " FAIL"

# 6. 前端页面
echo "6. 测试前端..."
curl -sf http://localhost:30000 > /dev/null && echo " OK" || echo " FAIL"

# 7. API 代理链路
echo "7. 测试 API 代理..."
curl -sf http://localhost:30000/api/models > /dev/null && echo " OK" || echo " FAIL"

# 8. 模型列表
echo "8. 获取模型列表..."
curl -s http://localhost:35000/manage/models | python -m json.tool

echo "=== 测试完成 ==="
```

### 网络连通性测试

```bash
# 检查 Docker 网络
docker network inspect ai-os-network

# 容器间 DNS 解析
docker exec ai-os-controller ping -c 1 redis
docker exec ai-os-controller ping -c 1 aiclient

# 端口映射验证
docker port ai-os-frontend
docker port ai-os-controller
docker port ai-os-go-vllm-api
docker port ai-os-aiclient
docker port ai-os-redis
```

## 性能测试

### API 延迟测试

```bash
# Python 后端延迟
curl -o /dev/null -s -w "Total: %{time_total}s\n" \
  http://localhost:35000/manage/models

# Go 后端延迟
curl -o /dev/null -s -w "Total: %{time_total}s\n" \
  http://localhost:35001/health

# 通过 Nginx 代理延迟
curl -o /dev/null -s -w "Total: %{time_total}s\n" \
  http://localhost:30000/api/models

# 通过 aiclient2api 网关延迟
curl -o /dev/null -s -w "Total: %{time_total}s\n" \
  http://localhost:3000/api/models
```

### 并发压力测试

```bash
# 安装 hey (HTTP 压力测试工具)
# go install github.com/rakyll/hey@latest

# 50 并发，100 请求
hey -n 100 -c 50 http://localhost:35001/v1/models
```

## 常见测试问题

### 问题 1：前端 API 请求 404

**原因**：前端代理路由与后端真实路由不一致，或 `proxy_pass` 地址不正确

**解决**：修改 `frontend/nginx.conf` 或 `frontend/vite.config.ts`，确保：
- `/api/*` 代理到 Python 后端 `/manage/*`
- `/api/health*`、`/health*`、`/v1/*` 代理到 Go 后端
- 容器内代理地址使用 Docker 服务名

```nginx
location /api/manage/ {
    proxy_pass http://python_backend/manage/;  # upstream: ai-controller:35000
}
location = /api/health {
    proxy_pass http://go_backend/health;
}
location /v1/ {
    proxy_pass http://go_backend/v1/;          # upstream: go-vllm-api:35001
}
```

### 问题 2：Redis 连接超时

**原因**：容器间网络不通或 Redis URL 配置错误

**解决**：

```bash
# 检查 Redis 容器状态
docker compose ps redis

# 检查环境变量
docker exec ai-os-controller env | grep REDIS

# 确认使用 Docker 内部地址
# REDIS_URL=redis://redis:6379（不是 localhost）
```

### 问题 3：GPU 不可用

**原因**：NVIDIA Container Toolkit 未安装或 GPU 动动问题

**解决**：

```bash
# 检查宿主机 GPU
nvidia-smi

# 检查 Docker GPU 支持
docker run --rm --gpus all nvidia/cuda:12.1.1-base-ubuntu22.04 nvidia-smi

# 重新安装 nvidia-container-toolkit
sudo apt install nvidia-container-toolkit
sudo systemctl restart docker
```
