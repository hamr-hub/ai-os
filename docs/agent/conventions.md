# 编码约定

> ai-os 项目开发规范（代码层面，项目规则见 [.codeflicker/rules.md](../../.codeflicker/rules.md)）

---

## Vue 3

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
  @apply flex flex-col gap-4;
}
</style>
```

### Props 定义
```ts
// 推荐: 类型推断
interface Props { id: string; name?: string }
const props = defineProps<Props>()

// 避免: 运行时声明
const props = defineProps({ id: { type: String, required: true } })
```

### 响应式
```ts
const count = ref(0)                  // 简单值
const user = reactive({ name: '', age: 0 })  // 对象
const doubled = computed(() => count.value * 2)  // 计算属性
```

---

## TypeScript

```ts
// 接口优先
interface User { id: string; name: string; email: string }

// 联合类型
type Status = 'pending' | 'active' | 'inactive'

// 泛型响应
interface ApiResponse<T> { data: T; status: number; message: string }

// 参数对象化
function fetchUsers(options: { page?: number; limit?: number } = {}): Promise<User[]> { ... }
```

---

## Python (FastAPI)

```python
from fastapi import APIRouter, HTTPException
from typing import Optional

router = APIRouter()

@router.get("/users/{user_id}")
async def get_user(user_id: str) -> Optional[User]:
    user = await user_service.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
```

---

## 样式 (Tailwind CSS)

```vue
<!-- 推荐: utility-first -->
<button class="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600">

<!-- 避免: 内联样式 -->
<button style="padding: 8px 16px; background: blue;">
```

---

## Git 与安全

详见 [.codeflicker/rules.md](../../.codeflicker/rules.md) 的 Git Commit 格式和安全约束部分。

---

> 更新于 2026-04-24
