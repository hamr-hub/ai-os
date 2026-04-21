# Vue 工程完善和优化计划

## 一、项目现状分析

### 1.1 技术栈
- **框架**: Vue 3.5.13 + TypeScript
- **构建工具**: Vite 6.3.5
- **样式**: Tailwind CSS 3.4.19
- **图标**: lucide-vue-next
- **HTTP 客户端**: axios

### 1.2 项目结构
```
frontend/
├── src/
│   ├── components/
│   │   ├── GPUMonitor.vue      # GPU监控组件 ✓
│   │   ├── ModelManager.vue    # 模型管理组件 ✓
│   │   ├── ChatWindow.vue      # 聊天窗口组件 ✓
│   │   ├── ModelTester.vue     # 模型检测组件 ✓
│   │   └── HelloWorld.vue      # 未使用的示例组件 ✗
│   ├── composables/
│   │   ├── useGPU.ts           # GPU状态管理
│   │   └── useModels.ts        # 模型状态管理
│   ├── api/
│   │   └── client.ts           # API客户端
│   ├── types/
│   │   └── index.ts            # 类型定义
│   ├── App.vue                 # 根组件
│   ├── main.ts                 # 入口文件
│   └── style.css               # 全局样式
├── vite.config.ts              # Vite配置
├── package.json               # 依赖配置
└── tsconfig.json              # TypeScript配置（待完善）
```

### 1.3 现有问题分析

| 问题类型 | 问题描述 | 优先级 |
|---------|---------|-------|
| **配置缺失** | 缺少 tsconfig.json 路径别名配置 | 高 |
| **配置缺失** | 缺少 ESLint 和 Prettier 配置 | 中 |
| **代码质量** | API客户端缺少请求拦截器和错误处理 | 高 |
| **代码质量** | Composables缺少错误状态管理的完善 | 中 |
| **功能完善** | ChatWindow不支持流式响应 | 高 |
| **代码清理** | HelloWorld.vue未使用，需要删除 | 低 |
| **样式优化** | 缺少统一的主题色变量配置 | 中 |

---

## 二、优化计划

### 2.1 配置完善

#### 2.1.1 完善 tsconfig.json
- 添加路径别名配置
- 确保与 vite.config.ts 中的别名一致

#### 2.1.2 添加 ESLint 配置
- 安装 eslint, @typescript-eslint/eslint-plugin, eslint-plugin-vue
- 创建 .eslintrc.cjs 配置文件

#### 2.1.3 添加 Prettier 配置
- 安装 prettier, eslint-config-prettier, eslint-plugin-prettier
- 创建 .prettierrc 配置文件

### 2.2 API 客户端优化

#### 2.2.1 添加请求拦截器
- 统一处理请求头
- 添加请求超时处理

#### 2.2.2 添加响应拦截器
- 统一处理错误响应
- 实现全局错误提示机制

### 2.3 Composables 优化

#### 2.3.1 useGPU.ts 优化
- 添加更多格式化工具函数
- 增强错误处理

#### 2.3.2 useModels.ts 优化
- 添加模型列表刷新控制
- 完善状态管理逻辑

### 2.4 功能增强

#### 2.4.1 ChatWindow 流式响应支持
- 使用 axios 流式请求
- 实现打字机效果

#### 2.4.2 添加刷新按钮
- GPU监控添加手动刷新按钮
- 模型管理添加手动刷新按钮

#### 2.4.3 删除未使用文件
- 删除 HelloWorld.vue

### 2.5 样式优化

#### 2.5.1 统一主题色配置
- 在 style.css 中添加 Tailwind 主题变量
- 统一品牌色调

#### 2.5.2 添加动画效果
- 为卡片添加悬停动画
- 为按钮添加过渡效果

---

## 三、执行步骤

| 序号 | 任务 | 涉及文件 | 预估时间 |
|-----|------|---------|---------|
| 1 | 完善 tsconfig.json 路径别名 | tsconfig.json | 30分钟 |
| 2 | 添加 ESLint 配置 | .eslintrc.cjs, package.json | 30分钟 |
| 3 | 添加 Prettier 配置 | .prettierrc, package.json | 30分钟 |
| 4 | 优化 API 客户端拦截器 | src/api/client.ts | 60分钟 |
| 5 | 完善 useGPU composable | src/composables/useGPU.ts | 30分钟 |
| 6 | 完善 useModels composable | src/composables/useModels.ts | 30分钟 |
| 7 | 添加 ChatWindow 流式响应 | src/components/ChatWindow.vue | 60分钟 |
| 8 | 添加手动刷新按钮 | src/components/GPUMonitor.vue, src/components/ModelManager.vue | 30分钟 |
| 9 | 删除未使用文件 | src/components/HelloWorld.vue | 10分钟 |
| 10 | 优化主题样式 | src/style.css | 30分钟 |
| 11 | 运行构建测试 | package.json scripts | 30分钟 |

---

## 四、预期成果

### 4.1 代码质量提升
- ✅ 完整的 TypeScript 类型支持
- ✅ 统一的代码风格检查
- ✅ 完善的错误处理机制

### 4.2 功能增强
- ✅ 聊天窗口支持流式响应
- ✅ 手动刷新功能
- ✅ 更好的用户体验

### 4.3 项目结构优化
- ✅ 清理无用代码
- ✅ 统一的配置管理

---

## 五、依赖安装清单

```bash
# 开发依赖
npm install -D eslint @typescript-eslint/eslint-plugin @typescript-eslint/parser eslint-plugin-vue prettier eslint-config-prettier eslint-plugin-prettier
```

---

## 六、风险评估

| 风险 | 描述 | 应对措施 |
|-----|------|---------|
| 配置冲突 | ESLint 和 Prettier 规则冲突 | 使用 eslint-config-prettier 禁用冲突规则 |
| 类型错误 | tsconfig 路径别名配置错误 | 仔细核对 vite.config.ts 和 tsconfig.json |
| 构建失败 | 依赖版本不兼容 | 使用 LTS 版本依赖 |
| 功能回归 | 修改后影响现有功能 | 先运行测试再修改 |
