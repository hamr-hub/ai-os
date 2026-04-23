# AIClient2API 与 app-controller 集成指南

## 概述

本文档详细说明如何将 AIClient2API (Node.js) 与 app-controller (Python) 进行对接，实现完整的 AI 模型服务管理功能。

## 架构说明

```
┌──────────────────────────┐
│    AIClient2API          │  ← Node.js 前端代理层
│   (Auth + Proxy + UI)    │
└──────────┬───────────────┘
           │ OpenAI 协议转发
           ▼
┌──────────────────────────┐
│   app-controller         │  ← Python 控制层（核心大脑）
│  (FastAPI + Scheduler)   │
└──────────┬───────────────┘
           │
     ┌─────┼─────┐
     ▼     ▼     ▼
┌────────┐ ┌──────┐ ┌──────────┐
│ Redis  │ │GPU监控│ │systemctl │
│ 队列   │ │nvidia │ │模型启停  │
└────────┘ └──────┘ └──────────┘
           │
           ▼
┌──────────────────────────┐
│      vLLM Instance       │  ← 实际推理层
└──────────────────────────┘
```

## 配置步骤

### 1. 配置 AIClient2API

在 AIClient2API 的配置文件中添加自定义渠道：

```json
// /root/ai-os/aiclient2api/configs/provider_pools.json
{
  "openai-custom": [
    {
      "customName": "app-controller",
      "checkModelName": "",
      "checkHealth": true,
      "concurrencyLimit": 32,
      "queueLimit": 100,
      "OPENAI_API_KEY": "123456",
      "OPENAI_BASE_URL": "http://localhost:35001",
      "supportedModels": [
        "Gemma-4-31B-Abliterated",
        "Qwen3.6-35B-A3B",
        "llama-3.3-70b-8.0bpw"
      ]
    }
  ]
}
```

### 2. 启动 app-controller

```bash
cd /root/ai-os/app-controller
./start.sh
```

### 3. 启动 AIClient2API

```bash
cd /root/ai-os/aiclient2api
docker-compose up -d
```

## API 接口映射

AIClient2API 调用以下 app-controller 接口：

| AIClient2API 请求 | app-controller 端点 | 说明 |
|------------------|-------------------|------|
| 获取模型列表 | `GET /v1/models` | 返回可用模型列表 |
| 聊天补全 | `POST /v1/chat/completions` | OpenAI 兼容的聊天接口 |
| Embeddings | `POST /v1/embeddings` | 嵌入向量生成 |
| 健康检查 | `GET /health` | 服务健康状态 |

## 核心功能

### 1. 模型自动启动

当 AIClient2API 请求一个未运行的模型时，app-controller 会：
1. 检查显存是否充足
2. 自动启动对应的 vLLM 服务
3. 等待模型加载完成
4. 转发请求到 vLLM

### 2. 并发控制

- 通过 Redis 实现请求计数
- 超过并发限制时返回 429 错误
- 支持请求队列缓冲

### 3. 显存管理

- 实时监控 GPU 显存
- 自动清理显存碎片
- 智能切换模型时释放显存

### 4. 流式响应支持

完全支持 OpenAI 流式响应协议，确保流畅的 UI 体验。

## 测试验证

运行集成测试脚本验证对接：

```bash
cd /root/ai-os/app-controller
python test_aiclient_integration.py
```

## 环境变量配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `PORT` | 35000 | 服务监听端口 |
| `HOST` | 0.0.0.0 | 监听地址 |
| `REDIS_URL` | redis://localhost:6379 | Redis 连接地址 |
| `LOG_LEVEL` | INFO | 日志级别 |

## 故障排除

### 常见问题

1. **连接失败**: 确保 app-controller 正在运行且端口可访问
2. **模型启动失败**: 检查 systemd 服务配置和权限
3. **显存不足**: 关闭其他模型或增加 GPU 内存
4. **流式响应异常**: 检查网络超时设置

### 日志查看

```bash
# 查看 app-controller 日志
tail -f /root/ai-os/app-controller/logs/app.log

# 查看 AIClient2API 日志
docker logs aiclient -f
```

## 性能优化建议

1. **启用预加载**: 在 config.yaml 中设置 `preload: true`
2. **调整并发限制**: 根据 GPU 性能调整 `concurrency_limit`
3. **使用连接池**: 保持 HTTP 连接复用
4. **启用缓存**: 模型列表等数据自动缓存

## 安全注意事项

1. 限制 API 访问来源
2. 使用强密码保护 Redis
3. 定期更新依赖库
4. 监控异常请求模式