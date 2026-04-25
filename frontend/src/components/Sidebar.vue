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
  BookOpen,
  ShieldCheck,
  Cpu,
} from 'lucide-vue-next'
import { useAppStore } from '@/stores/app'
import { useGPU } from '@/composables/useGPU'

const router = useRouter()
const route = useRoute()
const store = useAppStore()
const { gpuSummary } = useGPU()

const groups = [
  {
    title: '核心控制',
    items: [
      { name: 'dashboard', label: '总览面板', icon: LayoutDashboard },
      { name: 'models', label: '模型调度', icon: Server },
      { name: 'benchmarks', label: '模型评测', icon: ShieldCheck },
      { name: 'agent', label: 'AI Agent', icon: Bot },
    ],
  },
  {
    title: '数据监控',
    items: [
      { name: 'monitor', label: '实时性能', icon: Activity },
      { name: 'docs', label: '系统文档', icon: BookOpen },
    ],
  },
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
  if (store.theme === 'system') return '系统跟随'
  return store.actualTheme === 'dark' ? '深色视觉' : '浅色视觉'
})

const gpuInfo = computed(() => gpuSummary.value?.current)

const toggleCollapse = () => {
  store.toggleSidebar()
}
</script>

<template>
  <aside class="sidebar animate-scan-v" :class="{ collapsed: store.sidebarCollapsed }">
    <div class="sidebar-inner">
      <!-- Logo 区域 -->
      <div class="logo-section" @click="navigateTo('dashboard')">
        <div class="logo-icon neon-glow-primary">
          <Zap class="w-5 h-5 text-white" />
        </div>
        <transition name="fade">
          <div v-if="!store.sidebarCollapsed" class="logo-text">
            <h1 class="logo-title digital-font">AI OS <span class="v-tag">v2.0</span></h1>
            <p class="logo-subtitle">Neural Controller</p>
          </div>
        </transition>
      </div>

      <!-- 导航分组 -->
      <div class="nav-container scrollbar-none">
        <div v-for="group in groups" :key="group.title" class="nav-group">
          <transition name="fade">
            <h3 v-if="!store.sidebarCollapsed" class="group-title">{{ group.title }}</h3>
          </transition>
          <div class="group-items">
            <button
              v-for="item in group.items"
              :key="item.name"
              class="nav-item hover-trigger"
              :class="{ active: isActive(item.name) }"
              @click="navigateTo(item.name)"
            >
              <component :is="item.icon" class="nav-icon" />
              <transition name="fade">
                <span v-if="!store.sidebarCollapsed" class="nav-label">{{ item.label }}</span>
              </transition>
              <div v-if="isActive(item.name)" class="active-glow"></div>
            </button>
          </div>
        </div>
      </div>

      <!-- 底部系统仪表盘 -->
      <div class="bottom-section">
        <transition name="fade">
          <div v-if="!store.sidebarCollapsed && gpuInfo" class="gpu-widget tech-border">
            <div class="widget-header">
              <Cpu class="w-3.5 h-3.5 text-primary" />
              <span class="widget-title digital-font">GPU STATUS</span>
            </div>
            <div class="widget-body">
              <div class="stat-row">
                <span class="stat-label">LOAD</span>
                <span
                  class="stat-value digital-font"
                  :class="(gpuInfo.utilization ?? 0) > 80 ? 'text-red-400' : 'text-green-400'"
                >
                  {{ gpuInfo.utilization?.toFixed(0) ?? '--' }}%
                </span>
              </div>
              <div class="stat-bar-bg">
                <div
                  class="stat-bar-fill"
                  :style="{ width: (gpuInfo.utilization ?? 0) + '%' }"
                  :class="(gpuInfo.utilization ?? 0) > 80 ? 'bg-red-500' : 'bg-green-500'"
                ></div>
              </div>
              <div class="stat-row mt-2">
                <span class="stat-label">VRAM</span>
                <span class="stat-value digital-font"
                  >{{ (gpuInfo.used_memory / 1024)?.toFixed(1) ?? '--' }}G</span
                >
              </div>
            </div>
          </div>
        </transition>

        <div class="action-buttons">
          <button class="action-btn" :title="themeLabel" @click="cycleTheme">
            <component :is="themeIcon" class="w-4.5 h-4.5" />
          </button>
          <button
            class="action-btn"
            :title="store.sidebarCollapsed ? '展开' : '收起'"
            @click="toggleCollapse"
          >
            <PanelLeftOpen v-if="store.sidebarCollapsed" class="w-4.5 h-4.5" />
            <PanelLeftClose v-else class="w-4.5 h-4.5" />
          </button>
          <button class="action-btn" title="系统安全">
            <ShieldCheck class="w-4.5 h-4.5" />
          </button>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  position: fixed;
  left: 0;
  top: 0;
  width: var(--sidebar-width);
  height: 100vh;
  z-index: 100;
  background: var(--bg-sidebar);
  border-right: 1px solid rgba(99, 102, 241, 0.15);
  transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 4px 0 24px rgba(0, 0, 0, 0.4);
}

.sidebar.collapsed {
  width: var(--sidebar-collapsed-width);
}

.sidebar-inner {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.logo-section {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 24px 20px;
  cursor: pointer;
}

.logo-icon {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-dark) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.logo-title {
  font-size: 18px;
  font-weight: 800;
  color: var(--text-primary);
  margin: 0;
  line-height: 1;
}

.v-tag {
  font-size: 10px;
  background: rgba(99, 102, 241, 0.2);
  color: var(--color-primary-light);
  padding: 1px 4px;
  border-radius: 4px;
  vertical-align: top;
  margin-left: 2px;
}

.logo-subtitle {
  font-size: 10px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-top: 4px;
}

.nav-container {
  flex: 1;
  padding: 12px;
  overflow-y: auto;
}

.nav-group {
  margin-bottom: 20px;
}

.group-title {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 1px;
  padding: 0 12px 8px;
}

.group-items {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border-radius: 12px;
  color: var(--text-sidebar);
  border: 1px solid transparent;
  background: transparent;
  cursor: pointer;
  width: 100%;
  position: relative;
  overflow: hidden;
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-primary);
}

.nav-item.active {
  background: rgba(99, 102, 241, 0.08);
  border-color: rgba(99, 102, 241, 0.2);
  color: var(--color-primary-light);
}

.nav-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.nav-label {
  font-size: 14px;
  font-weight: 500;
}

.active-glow {
  position: absolute;
  left: 0;
  top: 25%;
  height: 50%;
  width: 3px;
  background: var(--color-primary);
  border-radius: 0 4px 4px 0;
  box-shadow: 0 0 10px var(--color-primary);
}

.sidebar.collapsed .nav-item {
  justify-content: center;
  padding: 12px;
}

.bottom-section {
  padding: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}

.gpu-widget {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 12px;
  padding: 12px;
  margin-bottom: 16px;
}

.widget-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
}

.widget-title {
  font-size: 10px;
  color: var(--text-muted);
}

.stat-row {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  margin-bottom: 4px;
}

.stat-label {
  color: var(--text-muted);
}

.stat-bar-bg {
  height: 4px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 2px;
  overflow: hidden;
}

.stat-bar-fill {
  height: 100%;
  transition: width 0.5s ease;
}

.action-buttons {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}

.action-btn {
  flex: 1;
  height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 10px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover {
  background: rgba(99, 102, 241, 0.1);
  color: var(--color-primary-light);
  border-color: rgba(99, 102, 241, 0.2);
}

.sidebar.collapsed .gpu-widget {
  display: none;
}

.sidebar.collapsed .action-buttons {
  flex-direction: column;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
