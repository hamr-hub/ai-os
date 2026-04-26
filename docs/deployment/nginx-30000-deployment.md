# Nginx 30000 端口部署指南

## 概述

使用 systemd 管理 nginx 30000 端口服务，实现开机自启动。前端静态文件直接从 `dist` 目录提供服务，无需构建独立的 dist_30000 目录。

## 架构说明

```
用户 → nginx:30000 (前端静态文件 + 反向代理)
         ↓
     /api/* → Python 后端 (192.168.7.103:35000)
     /v1/*  → Go 后端 (192.168.7.103:35001)
     /ws/*  → Python WebSocket (192.168.7.103:35000)
     /health → Go 健康检查 (192.168.7.103:35001)
```

## 文件清单

| 文件 | 路径 | 说明 |
|------|------|------|
| Nginx 配置 | `/etc/nginx/nginx_30000.conf` | 独立 nginx 配置文件 |
| Systemd 服务 | `/etc/systemd/system/nginx-30000.service` | 服务单元文件 |
| 前端构建 | `/root/ai-os/frontend/dist` | 前端生产构建目录 |

## 部署步骤

### 1. 构建前端

```bash
cd /root/ai-os/frontend
pnpm build
```

### 2. 安装配置文件

```bash
# 复制 nginx 配置
sudo cp /root/ai-os/frontend/nginx_30000.conf /etc/nginx/nginx_30000.conf

# 复制 systemd 服务文件
sudo cp /root/ai-os/frontend/nginx-30000.service /etc/systemd/system/nginx-30000.service
```

### 3. 启动服务

```bash
# 重新加载 systemd 配置
sudo systemctl daemon-reload

# 启用开机自启动
sudo systemctl enable nginx-30000.service

# 启动服务
sudo systemctl start nginx-30000.service

# 检查状态
sudo systemctl status nginx-30000.service
```

## 常用命令

```bash
# 查看服务状态
sudo systemctl status nginx-30000.service

# 重启服务
sudo systemctl restart nginx-30000.service

# 停止服务
sudo systemctl stop nginx-30000.service

# 查看日志
sudo journalctl -u nginx-30000.service -f

# 重新加载配置（不停机）
sudo nginx -s reload -c /etc/nginx/nginx_30000.conf

# 测试配置文件
sudo nginx -t -c /etc/nginx/nginx_30000.conf
```

## 配置说明

### 后端代理配置

| 路径 | 目标 | 说明 |
|------|------|------|
| `/api/manage/` | `<后端IP>:35000/manage/` | Python 管理接口 |
| `/api/health` | `<后端IP>:35001/health` | Go 健康检查 |
| `/api/health/detailed` | `<后端IP>:35001/health/detailed` | Go 详细健康检查 |
| `/api/` | `<后端IP>:35000/manage/` | Python 通用接口 |
| `/v1/` | `<后端IP>:35001/v1/` | Go vLLM 接口 |
| `/manage/` | `<后端IP>:35000/manage/` | Python 管理接口 |
| `/ws/` | `<后端IP>:35000/ws/` | Python WebSocket |
| `/health` | `<后端IP>:35001/health` | Go 健康检查 |

> **注意**: 配置中的 `<后端IP>` 需替换为实际后端服务器 IP，示例文档中使用 `192.168.7.103`。

### 注意事项

1. **后端端口固定**: Python 后端固定使用 `35000` 端口，Go 后端固定使用 `35001` 端口
2. **局域网 IP**: 所有代理使用后端服务器 IP（示例: `192.168.7.103`）
3. **前端目录**: 直接使用 `dist` 目录，无需额外复制
4. **PID 文件**: 独立 PID 文件 `/var/run/nginx_30000.pid`，与系统 nginx 不冲突

---

> 创建于 2026-04-26