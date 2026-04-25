# 开发命令手册

> ai-os 项目常用命令

---

## 前端

```bash
cd frontend
pnpm dev              # 开发服务器 http://localhost:30001
pnpm build            # 生产构建 → dist/
pnpm lint             # 检查并自动修复
pnpm lint:check       # 仅检查
pnpm typecheck        # 类型检查
pnpm format           # Prettier 格式化
```

## Python 后端

```bash
cd app-controller
python main.py                            # 启动 http://localhost:35000
uvicorn main:app --reload --port 35000    # 热更新模式
pytest                                    # 运行测试
pytest --cov=core                         # 带覆盖率
ruff check .                              # 代码检查
ruff check . --fix                        # 自动修复
ruff format .                             # 格式化
```

## Go 后端

```bash
cd go-vllm-api
go run cmd/server/main.go --port 35001    # 启动 http://localhost:35001
```

## API 网关

```bash
cd aiclient2api
docker compose up -d                      # 启动 http://localhost:3000
docker compose logs -f                    # 查看日志
```

## Docker 全栈

```bash
docker compose build                      # 构建所有镜像
docker compose up -d                      # 启动所有服务
docker compose ps                         # 查看状态
docker compose down                       # 停止所有服务
docker compose logs -f                    # 查看日志
```

## 依赖管理

```bash
# 前端
cd frontend
pnpm install                              # 安装依赖
pnpm add <package>                        # 添加依赖
pnpm add -D <package>                     # 开发依赖

# 后端
cd app-controller
pip install -r requirements.txt
pip freeze > requirements.txt             # 导出依赖
```

## Git 规范

```
<type>(scope): <subject>

feat(frontend): 添加用户设置页面
fix(backend): 修复 API 响应格式
refactor(api): 重构认证逻辑
docs(readme): 更新安装说明
test(frontend): 添加组件测试
chore(docker): 更新 Dockerfile
```

---

> 更新于 2026-04-24
