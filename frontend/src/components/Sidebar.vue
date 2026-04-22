<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  LayoutDashboard,
  Cpu,
  Server,
  MessageSquare,
  TestTube,
  Settings,
  Sun,
  Moon,
  Monitor,
  Zap,
} from 'lucide-vue-next'
import { useAppStore } from '@/stores/app'

const router = useRouter()
const route = useRoute()
const store = useAppStore()

const navItems = [
  { name: 'dashboard', label: '首页', icon: LayoutDashboard },
  { name: 'gpu', label: '性能监控', icon: Cpu },
  { name: 'models', label: '模型管理', icon: Server },
  { name: 'chat', label: 'AI 聊天', icon: MessageSquare },
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

const themeLabel = computed(() => {
  if (store.theme === 'system') return '跟随系统'
  return store.actualTheme === 'dark' ? '深色模式' : '浅色模式'
})
</script>

<template>
  <aside class="sidebar">
    <!-- Logo -->
    <div class="logo-section">
      <div class="logo-icon">
        <Zap class="w-6 h-6 text-white" />
      </div>
      <div class="logo-text">
        <h1 class="logo-title">GPU Control</h1>
      </div>
    </div>

    <!-- Navigation -->
    <nav class="nav-section">
      <button
        v-for="item in navItems"
        :key="item.name"
        @click="navigateTo(item.name)"
        class="nav-item"
        :class="{ active: isActive(item.name) }"
      >
        <component :is="item.icon" class="nav-icon" />
        <span class="nav-label">{{ item.label }}</span>
      </button>
    </nav>

    <!-- Bottom Section -->
    <div class="bottom-section">
      <button class="nav-item" @click="cycleTheme">
        <component :is="themeIcon" class="nav-icon" />
        <span class="nav-label">{{ themeLabel }}</span>
      </button>
      
      <button class="nav-item">
        <Settings class="nav-icon" />
        <span class="nav-label">设置</span>
      </button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  position: fixed;
  left: 0;
  top: 0;
  width: 200px;
  height: 100vh;
  z-index: 50;
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
  border-right: 1px solid rgba(255, 255, 255, 0.05);
}

.logo-section {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.logo-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(34, 197, 94, 0.3);
}

.logo-text {
  display: flex;
  flex-direction: column;
}

.logo-title {
  font-size: 16px;
  font-weight: 700;
  color: #f8fafc;
  letter-spacing: -0.5px;
}

.nav-section {
  flex: 1;
  padding: 12px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow-y: auto;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 10px;
  color: #94a3b8;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s ease;
  cursor: pointer;
  border: none;
  background: transparent;
  text-align: left;
  width: 100%;
}

.nav-item:hover {
  color: #f1f5f9;
  background: rgba(255, 255, 255, 0.05);
}

.nav-item.active {
  color: #22c55e;
  background: rgba(34, 197, 94, 0.1);
  position: relative;
}

.nav-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 20px;
  background: linear-gradient(180deg, #22c55e 0%, #16a34a 100%);
  border-radius: 0 3px 3px 0;
}

.nav-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.nav-label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.bottom-section {
  padding: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
</style>
