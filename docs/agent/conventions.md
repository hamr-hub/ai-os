# 编码约定

> ai-os 项目开发规范

---

## 通用规范

### 文件命名
- Vue 组件: PascalCase (如 `UserProfile.vue`)
- TypeScript 文件: camelCase (如 `useAuth.ts`)
- Python 文件: snake_case (如 `user_service.py`)
- 常量文件: UPPER_SNAKE_CASE (如 `API_CONSTANTS.ts`)

### 目录结构
- `components/` - 可复用组件
- `views/` - 页面级组件
- `composables/` - Vue Composables
- `api/` - API 调用封装
- `stores/` - Pinia 状态管理
- `types/` - TypeScript 类型定义

---

## Vue 3 规范

### 组件结构
```vue
<script setup lang="ts">
import { ref, computed } from 'vue'

interface Props {
  title: string
  count?: number
}

const props = withDefaults(defineProps<Props>(), {
  count: 0
})

const emit = defineEmits<{
  update: [value: number]
}>()

const localCount = ref(props.count)
</script>

<template>
  <div class="component-wrapper">
    <h2>{{ title }}</h2>
    <button @click="emit('update', localCount + 1)">
      Count: {{ localCount }}
    </button>
  </div>
</template>

<style scoped>
.component-wrapper {
  /* 样式 */
}
</style>
```

### Props 定义
```ts
// ✅ 推荐: 使用类型推断
interface Props {
  id: string
  name?: string
}
const props = defineProps<Props>()

// ❌ 避免: 运行时声明
const props = defineProps({
  id: { type: String, required: true },
  name: String
})
```

### 响应式状态
```ts
// 简单值
const count = ref(0)

// 对象
const user = reactive({
  name: 'Alice',
  age: 30
})

// 计算属性
const doubled = computed(() => count.value * 2)
```

---

## TypeScript 规范

### 类型定义
```ts
// 接口优先
interface User {
  id: string
  name: string
  email: string
}

// 联合类型
type Status = 'pending' | 'active' | 'inactive'

// 泛型
interface ApiResponse<T> {
  data: T
  status: number
  message: string
}
```

### 函数签名
```ts
// 明确返回类型
function fetchUser(id: string): Promise<User> {
  return api.get(`/users/${id}`)
}

// 参数对象化
interface FetchOptions {
  page?: number
  limit?: number
}

function fetchUsers(options: FetchOptions = {}): Promise<User[]> {
  // ...
}
```

---

## Python 规范

### 函数定义
```python
from typing import Optional, List

def get_user(user_id: str) -> Optional[User]:
    """获取用户信息
    
    Args:
        user_id: 用户ID
        
    Returns:
        User 对象或 None
    """
    pass

async def fetch_users(page: int = 1, limit: int = 20) -> List[User]:
    """异步获取用户列表"""
    pass
```

### FastAPI 路由
```python
from fastapi import APIRouter, HTTPException

router = APIRouter()

@router.get("/users/{user_id}")
async def get_user(user_id: str):
    user = await user_service.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
```

---

## 样式规范

### Tailwind CSS
```vue
<template>
  <!-- ✅ 推荐: utility-first -->
  <button class="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600">
    Click me
  </button>
  
  <!-- ❌ 避免: 内联样式 -->
  <button style="padding: 8px 16px; background: blue;">
    Click me
  </button>
</template>
```

### 自定义样式
```vue
<style scoped>
/* 使用 scoped 隔离 */
.container {
  @apply flex flex-col gap-4;
}
</style>
```

---

## Git 提交

### Commit 格式
```
<type>(scope): <subject>

<body>

<footer>
```

### Type 类型
- `feat`: 新功能
- `fix`: Bug 修复
- `refactor`: 重构
- `docs`: 文档
- `test`: 测试
- `chore`: 构建/工具

### 示例
```
feat(frontend): 添加用户设置页面

- 新增 SettingsView.vue
- 集成主题切换功能
- 添加 Pinia settings store

Closes #123
```

---

## 安全约束

### 环境变量
```bash
# .env.example
VITE_API_URL=http://localhost:8000
VITE_APP_TITLE=AI OS
```

### 禁止行为
- ❌ 硬编码 API 密钥
- ❌ 提交 `.env` 文件
- ❌ 前端存储敏感信息
- ✅ 使用环境变量
- ✅ 服务端验证权限

---

> 更新于 2026-04-22
