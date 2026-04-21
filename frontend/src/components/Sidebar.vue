<script setup lang="ts">
import { useRouter, useRoute } from 'vue-router'
import {
  LayoutDashboard,
  Cpu,
  Server,
  MessageSquare,
  TestTube,
  ChevronLeft,
  ChevronRight,
} from 'lucide-vue-next'
import { useAppStore } from '@/stores/app'

const router = useRouter()
const route = useRoute()
const store = useAppStore()

const navItems = [
  { name: 'dashboard', label: '仪表盘', icon: LayoutDashboard },
  { name: 'gpu', label: 'GPU 监控', icon: Cpu },
  { name: 'models', label: '模型管理', icon: Server },
  { name: 'chat', label: '聊天测试', icon: MessageSquare },
  { name: 'test', label: '模型检测', icon: TestTube },
]

const isActive = (name: string) => route.name === name

const navigateTo = (name: string) => {
  router.push({ name })
}
</script>

<template>
  <aside
    class="fixed left-0 top-0 h-full bg-slate-800 border-r border-slate-700 z-40 transition-all duration-300"
    :class="store.sidebarCollapsed ? 'w-16' : 'w-56'"
  >
    <div class="flex flex-col h-full">
      <div class="p-4 border-b border-slate-700">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center flex-shrink-0">
            <Server class="w-6 h-6 text-white" />
          </div>
          <div v-if="!store.sidebarCollapsed" class="overflow-hidden">
            <h1 class="text-lg font-bold text-white truncate">AI Controller</h1>
            <p class="text-xs text-slate-400 truncate">模型管理平台</p>
          </div>
        </div>
      </div>

      <nav class="flex-1 p-4 space-y-2">
        <button
          v-for="item in navItems"
          :key="item.name"
          @click="navigateTo(item.name)"
          class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200"
          :class="isActive(item.name) ? 'bg-blue-600 text-white' : 'text-slate-400 hover:bg-slate-700 hover:text-white'"
        >
          <component :is="item.icon" class="w-5 h-5 flex-shrink-0" />
          <span v-if="!store.sidebarCollapsed" class="font-medium">{{ item.label }}</span>
        </button>
      </nav>

      <div class="p-4 border-t border-slate-700">
        <button
          @click="store.toggleSidebar"
          class="w-full flex items-center justify-center py-2 text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
        >
          <ChevronLeft v-if="!store.sidebarCollapsed" class="w-5 h-5" />
          <ChevronRight v-else class="w-5 h-5" />
        </button>
      </div>
    </div>
  </aside>
</template>
