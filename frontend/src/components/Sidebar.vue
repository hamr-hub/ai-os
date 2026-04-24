<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  LayoutDashboard,
  Server,
  Bot,
  Sun,
  Moon,
  Monitor,
  Zap,
  PanelLeftClose,
  PanelLeftOpen,
  Activity,
  MessageSquare,
  BookOpen,
} from 'lucide-vue-next'
import { useAppStore } from '@/stores/app'

const router = useRouter()
const route = useRoute()
const store = useAppStore()

const navItems = [
  { name: 'dashboard', label: '仪表盘', icon: LayoutDashboard },
  { name: 'monitor', label: '实时监控', icon: Activity },
  { name: 'models', label: '模型管理', icon: Server },
    { name: 'agent', label: 'Agent', icon: Bot },
  { name: 'docs', label: '文档', icon: BookOpen },
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
  if (store.sidebarCollapsed) return ''
  if (store.theme === 'system') return '跟随系统'
  return store.actualTheme === 'dark' ? '深色模式' : '浅色模式'
})

const toggleCollapse = () => {
  store.toggleSidebar()
}
</script>

<template>
  <aside class="sidebar" :class="{ collapsed: store.sidebarCollapsed }">
    <div class="sidebar-inner">
      <div class="logo-section">
        <div class="logo-icon">
          <Zap class="w-5 h-5 text-white" />
        </div>
        <transition name="fade">
          <div v-if="!store.sidebarCollapsed" class="logo-text">
            <h1 class="logo-title">AI OS</h1>
          </div>
        </transition>
        <button class="collapse-btn" @click="toggleCollapse" :title="store.sidebarCollapsed ? '展开' : '折叠'">
          <PanelLeftClose v-if="!store.sidebarCollapsed" class="w-4 h-4" />
          <PanelLeftOpen v-else class="w-4 h-4" />
        </button>
      </div>

      <nav class="nav-section">
        <button
          v-for="item in navItems"
          :key="item.name"
          @click="navigateTo(item.name)"
          class="nav-item"
          :class="{ active: isActive(item.name) }"
          :title="store.sidebarCollapsed ? item.label : ''"
        >
          <component :is="item.icon" class="nav-icon" />
          <transition name="fade">
            <span v-if="!store.sidebarCollapsed" class="nav-label">{{ item.label }}</span>
          </transition>
        </button>
      </nav>

      <div class="bottom-section">
        <button class="nav-item theme-btn" @click="cycleTheme" :title="store.sidebarCollapsed ? '切换主题' : ''">
          <component :is="themeIcon" class="nav-icon" />
          <transition name="fade">
            <span v-if="!store.sidebarCollapsed" class="nav-label">{{ themeLabel }}</span>
          </transition>
        </button>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  position: fixed;
  left: 0;
  top: var(--topbar-height);
  width: var(--sidebar-width);
  height: calc(100vh - var(--topbar-height));
  z-index: 50;
  display: flex;
  flex-direction: column;
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border-card);
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.sidebar.collapsed {
  width: var(--sidebar-collapsed-width);
}

.sidebar-inner {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.logo-section {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border-bottom: 1px solid var(--border-primary);
  min-height: 56px;
}

.sidebar.collapsed .logo-section {
  justify-content: center;
  padding: 16px 12px;
}

.logo-icon {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-dark) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(var(--color-primary-rgb), 0.3), 0 0 20px rgba(var(--color-primary-rgb), 0.15);
  flex-shrink: 0;
  transition: box-shadow 0.3s;
}
.sidebar:hover .logo-icon {
  box-shadow: 0 4px 16px rgba(var(--color-primary-rgb), 0.4), 0 0 30px rgba(var(--color-primary-rgb), 0.2);
}

.logo-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.5px;
  white-space: nowrap;
}

.collapse-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  color: var(--text-muted);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all 0.2s;
  margin-left: auto;
  flex-shrink: 0;
}

.collapse-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.sidebar.collapsed .collapse-btn {
  margin-left: 0;
  position: absolute;
  right: -12px;
  top: 16px;
  width: 24px;
  height: 24px;
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  box-shadow: var(--shadow);
  z-index: 60;
  border-radius: 6px;
}

.nav-section {
  flex: 1;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow-y: auto;
}

.sidebar.collapsed .nav-section {
  padding: 8px 8px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  color: var(--text-muted);
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s ease;
  cursor: pointer;
  border: none;
  background: transparent;
  text-align: left;
  width: 100%;
  white-space: nowrap;
  overflow: hidden;
  position: relative;
}

.nav-item:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
  transform: translateX(2px);
  box-shadow: 0 0 8px rgba(var(--color-primary-rgb), 0.05);
}

.nav-item.active {
  color: var(--color-primary);
  background: rgba(var(--color-primary-rgb), 0.1);
  box-shadow: 0 0 12px rgba(var(--color-primary-rgb), 0.08);
}

[data-theme='dark'] .nav-item.active {
  background: rgba(var(--color-primary-rgb), 0.15);
}

.nav-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 20px;
  background: linear-gradient(180deg, var(--color-primary) 0%, var(--color-primary-dark) 100%);
  border-radius: 0 3px 3px 0;
}

.sidebar.collapsed .nav-item {
  justify-content: center;
  padding: 10px;
  gap: 0;
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
  padding: 8px;
  border-top: 1px solid var(--border-primary);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.sidebar.collapsed .bottom-section {
  padding: 8px 8px;
}

.fade-enter-active { transition: opacity 0.2s ease; }
.fade-leave-active { transition: opacity 0.1s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
