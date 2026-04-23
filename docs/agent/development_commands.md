# 开发命令手册

> ai-os 项目常用命令

---

## 前端开发

### 启动开发服务器
```bash
cd frontend
pnpm dev
# 访问 http://localhost:5173
```

### 构建生产版本
```bash
cd frontend
pnpm build
# 输出到 frontend/dist/
```

### 代码检查
```bash
cd frontend
pnpm lint              # 检查并自动修复
pnpm lint:check        # 仅检查
```

### 类型检查
```bash
cd frontend
pnpm typecheck
# 或
vue-tsc --noEmit
```

### 代码格式化
```bash
cd frontend
pnpm format
# 使用 Prettier 格式化
```

---

## 后端开发

### 启动开发服务器
```bash
cd app-controller
python main.py
# 访问 http://localhost:8000
```

### 使用 Uvicorn
```bash
cd app-controller
uvicorn main:app --reload --host 0.0.0.0 --port 35000
```

### 运行测试
```bash
cd app-controller
pytest
pytest --cov=core      # 带覆盖率
```

### 代码检查
```bash
cd app-controller
ruff check .
ruff check . --fix     # 自动修复
```

### 格式化
```bash
cd app-controller
ruff format .
```

---

## API 网关

### 启动网关
```bash
cd aiclient2api
docker-compose up -d
```

### 查看日志
```bash
cd aiclient2api
docker-compose logs -f
```

---

## Docker 命令

### 构建所有服务
```bash
docker-compose build
```

### 启动所有服务
```bash
docker-compose up -d
```

### 查看服务状态
```bash
docker-compose ps
```

### 停止所有服务
```bash
docker-compose down
```

### 查看日志
```bash
docker-compose logs -f
```

---

## Git 命令

### 日常流程
```bash
# 拉取最新代码
git pull origin main

# 创建功能分支
git checkout -b feature/my-feature

# 提交更改
git add .
git commit -m "feat(scope): 描述"

# 推送分支
git push origin feature/my-feature
```

### Commit 规范
```
feat(frontend): 添加用户设置页面
fix(backend): 修复 API 响应格式
refactor(api): 重构认证逻辑
docs(readme): 更新安装说明
test(frontend): 添加组件测试
chore(docker): 更新 Dockerfile
```

---

## AI Flow 命令

### 需求交付
```bash
# 完整流程
/ai-flow T123456

# 或从文档开始
/ai-flow https://docs.corp.kuaishou.com/...
```

### 技术方案
```bash
/tech-solution
```

### 研发资产
```bash
/rd-asset-review
```

### 环境检查
```bash
/ai-flow-preflight-check
```

---

## 依赖管理

### 前端依赖
```bash
cd frontend
pnpm install           # 安装依赖
pnpm add package       # 添加依赖
pnpm add -D package    # 添加开发依赖
pnpm update            # 更新依赖
```

### 后端依赖
```bash
cd app-controller
pip install -r requirements.txt
pip freeze > requirements.txt  # 导出依赖
```

---

## 调试技巧

### Vue DevTools
- 安装 Vue DevTools 浏览器扩展
- 查看组件树和状态

### FastAPI 调试
```bash
# 启用调试模式
uvicorn main:app --reload --log-level debug
```

### API 文档
- 访问 http://localhost:8000/docs
- Swagger UI 自动文档

---

## 常见问题

### 端口占用
```bash
# 查找占用进程
lsof -i :5173
lsof -i :8000

# 终止进程
kill -9 <PID>
```

### 依赖问题
```bash
# 清除依赖缓存
cd frontend
rm -rf node_modules pnpm-lock.yaml
pnpm install

cd ../app-controller
rm -rf venv
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

> 更新于 2026-04-22
