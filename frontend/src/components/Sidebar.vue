<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  LayoutDashboard,
  Cpu,
  Server,
  MessageSquare,
  TestTube,
  ChevronLeft,
  ChevronRight,
  Sun,
  Moon,
  Monitor,
} from 'lucide-vue-next'
import { useAppStore } from '@/stores/app'
import ConversationList from '@/components/ConversationList.vue'

const router = useRouter()
const route = useRoute()
const store = useAppStore()

const navItems = [
  { name: 'dashboard', label: '仪表盘', icon: LayoutDashboard },
  { name: 'gpu', label: 'GPU 监控', icon: Cpu },
  { name: 'models', label: '模型管理', icon: Server },
  { name: 'chat', label: '聊天', icon: MessageSquare },
  { name: 'test', label: '模型检测', icon: TestTube },
]

const isActive = (name: string) => route.name === name

const navigateTo = (name: string) => {
  router.push({ name })
}

const cycleTheme = () => {
  const themes: Array<'light' | 'dark' | 'system'> = ['light', 'dark', 'system']
  const currentIndex = themes.indexOf(store.theme)
  const nextIndex = (currentIndex + 1) % themes.length
  store.setTheme(themes[nextIndex])
}

const themeIcon = computed(() => {
  if (store.theme === 'system') return Monitor
  return store.actualTheme === 'dark' ? Moon : Sun
})
</script>

<template>
  <aside
    class="fixed left-0 top-0 h-full z-40 transition-all duration-300 ease-out flex flex-col bg-secondary/95 backdrop-blur-md border-r border-primary"
    :class="store.sidebarCollapsed ? 'w-16' : 'w-64'"
  >
    <div class="flex items-center gap-3 p-4 border-b border-primary">
      <div class="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 gradient-primary shadow-lg">
        <Server class="w-6 h-6 text-white" />
      </div>
      <div v-if="!store.sidebarCollapsed" class="overflow-hidden fade-in">
        <h1 class="text-lg font-bold text-primary truncate">AI Controller</h1>
        <p class="text-xs text-muted truncate">模型管理平台</p>
      </div>
    </div>

    <div v-if="route.name === 'chat'" class="flex-1 overflow-hidden">
      <ConversationList v-if="!store.sidebarCollapsed" />
      <div v-else class="flex flex-col items-center gap-2 py-4">
        <button
          @click="navigateTo('chat')"
          class="w-10 h-10 rounded-xl flex items-center justify-center transition-all"
          :class="isActive('chat') ? 'gradient-primary text-white shadow-lg' : 'text-muted hover:bg-hover'"
        >
          <MessageSquare class="w-5 h-5" />
        </button>
      </div>
    </div>

    <nav v-else class="flex-1 px-3 py-4 space-y-1">
      <button
        v-for="(item, index) in navItems"
        :key="item.name"
        @click="navigateTo(item.name)"
        class="w-full flex items-center gap-3 px-3 py-3 rounded-xl transition-all duration-200 relative group"
        :class="isActive(item.name) ? 'gradient-primary text-white shadow-lg scale-[1.02]' : 'text-secondary hover:bg-hover hover:scale-[1.02]'"
        :style="{ animationDelay: `${index * 50}ms` }"
      >
        <component :is="item.icon" class="w-5 h-5 flex-shrink-0" />
        <span v-if="!store.sidebarCollapsed" class="font-medium truncate fade-in">{{ item.label }}</span>
        <div
          v-if="isActive(item.name) && store.sidebarCollapsed"
          class="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 rounded-r-full gradient-primary"
        ></div>
      </button>
    </nav>

    <div class="p-3 border-t border-primary space-y-2">
      <button
        @click="cycleTheme"
        class="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all text-secondary hover:bg-hover"
        :title="`当前: ${store.theme === 'system' ? '跟随系统' : store.actualTheme === 'dark' ? '深色' : '浅色'}`"
      >
        <component :is="themeIcon" class="w-5 h-5 flex-shrink-0" />
        <span v-if="!store.sidebarCollapsed" class="text-sm truncate fade-in">
          {{ store.theme === 'system' ? '跟随系统' : store.actualTheme === 'dark' ? '深色模式' : '浅色模式' }}
        </span>
      </button>

      <button
        @click="store.toggleSidebar"
        class="w-full flex items-center justify-center py-2.5 text-muted hover:text-primary hover:bg-hover rounded-xl transition-all"
      >
        <ChevronLeft v-if="!store.sidebarCollapsed" class="w-5 h-5" />
        <ChevronRight v-else class="w-5 h-5" />
      </button>
    </div>
  </aside>
</template>
