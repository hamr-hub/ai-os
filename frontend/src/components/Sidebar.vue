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
    class="fixed left-0 top-0 h-full z-40 transition-all duration-300 ease-out"
    :class="store.sidebarCollapsed ? 'w-16' : 'w-56'"
    style="background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);"
  >
    <div class="flex flex-col h-full py-4">
      <div class="px-4 mb-6">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 gradient-primary">
            <Server class="w-6 h-6 text-white" />
          </div>
          <div v-if="!store.sidebarCollapsed" class="overflow-hidden fade-in">
            <h1 class="text-lg font-bold text-white truncate">AI Controller</h1>
            <p class="text-xs text-slate-400 truncate">模型管理平台</p>
          </div>
        </div>
      </div>

      <nav class="flex-1 px-3 space-y-1">
        <button
          v-for="(item, index) in navItems"
          :key="item.name"
          @click="navigateTo(item.name)"
          class="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200 relative group"
          :class="isActive(item.name) ? 'gradient-primary text-white shadow-lg shadow-primary/30' : 'text-slate-400 hover:bg-slate-700/50 hover:text-white'"
          :style="{ animationDelay: `${index * 50}ms` }"
        >
          <component :is="item.icon" class="w-5 h-5 flex-shrink-0 transition-transform duration-200" :class="{ 'group-hover:scale-110': !isActive(item.name) }" />
          <span v-if="!store.sidebarCollapsed" class="font-medium truncate fade-in">{{ item.label }}</span>
          <div
            v-if="isActive(item.name)"
            class="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 rounded-r-full gradient-primary"
          ></div>
        </button>
      </nav>

      <div class="px-3 pt-4 border-t border-slate-700/50">
        <button
          @click="store.toggleSidebar"
          class="w-full flex items-center justify-center py-2.5 text-slate-400 hover:text-white hover:bg-slate-700/50 rounded-xl transition-all duration-200"
        >
          <ChevronLeft v-if="!store.sidebarCollapsed" class="w-5 h-5" />
          <ChevronRight v-else class="w-5 h-5" />
        </button>
      </div>
    </div>
  </aside>
</template>
