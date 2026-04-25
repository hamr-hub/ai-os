<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ChevronDown, Plug, RefreshCw, Trash2, CheckCircle2, AlertCircle, XCircle, Globe, Server, Cpu } from 'lucide-vue-next'
import { useServerStore, type BackendType } from '@/stores/server'
import { useAppStore } from '@/stores/app'

const serverStore = useServerStore()
const appStore = useAppStore()
const panelOpen = ref(false)
const inputUrl = ref(serverStore.activeUrl)
const inputType = ref<BackendType>(serverStore.backendType)

const statusConfig = computed(() => {
  switch (serverStore.connectionStatus) {
    case 'online':
      return {
        class: 'online',
        icon: CheckCircle2,
        bgColor: 'rgba(34, 197, 94, 0.15)',
        borderColor: 'rgba(34, 197, 94, 0.35)',
        textColor: '#22c55e',
        glowColor: 'rgba(34, 197, 94, 0.3)'
      }
    case 'checking':
      return {
        class: 'checking',
        icon: AlertCircle,
        bgColor: 'rgba(245, 158, 11, 0.15)',
        borderColor: 'rgba(245, 158, 11, 0.35)',
        textColor: '#f59e0b',
        glowColor: 'rgba(245, 158, 11, 0.3)'
      }
    default:
      return {
        class: 'offline',
        icon: XCircle,
        bgColor: 'rgba(239, 68, 68, 0.15)',
        borderColor: 'rgba(239, 68, 68, 0.35)',
        textColor: '#ef4444',
        glowColor: 'rgba(239, 68, 68, 0.3)'
      }
  }
})

const backendConfig = computed(() => {
  switch (serverStore.backendType) {
    case 'go':
      return {
        label: 'Go Backend',
        shortLabel: 'GO',
        icon: Server,
        color: '#06b6d4',
        bgColor: 'rgba(6, 182, 212, 0.12)',
        borderColor: 'rgba(6, 182, 212, 0.3)'
      }
    case 'python':
      return {
        label: 'Python Backend',
        shortLabel: 'PY',
        icon: Cpu,
        color: '#f59e0b',
        bgColor: 'rgba(245, 158, 11, 0.12)',
        borderColor: 'rgba(245, 158, 11, 0.3)'
      }
    default:
      return {
        label: 'Auto Detect',
        shortLabel: 'AUTO',
        icon: Globe,
        color: '#8b5cf6',
        bgColor: 'rgba(139, 92, 246, 0.12)',
        borderColor: 'rgba(139, 92, 246, 0.3)'
      }
  }
})

const statusText = computed(() => {
  if (serverStore.connectionStatus === 'online') return '在线'
  if (serverStore.connectionStatus === 'checking') return '检测中'
  return '离线'
})

const formatTime = (timestamp: number) => {
  const diff = Date.now() - timestamp
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}小时前`
  const days = Math.floor(hours / 24)
  return `${days}天前`
}

const applyServer = async () => {
  serverStore.switchServer(inputUrl.value, inputType.value)
  panelOpen.value = false
  const online = await serverStore.checkConnection()
  if (online) {
    appStore.success(`已切换到 ${serverStore.currentLabel}`)
    return
  }
  appStore.error(serverStore.lastErrorMessage || `无法连接到 ${serverStore.currentLabel}`)
}

const useHistory = async (url: string, type: BackendType) => {
  inputUrl.value = url
  inputType.value = type
  serverStore.switchServer(url, type)
  panelOpen.value = false
  const online = await serverStore.checkConnection()
  if (online) {
    appStore.success(`已切换到 ${serverStore.currentLabel}`)
    return
  }
  appStore.error(serverStore.lastErrorMessage || `无法连接到 ${serverStore.currentLabel}`)
}

const useLocalProxy = async () => {
  inputUrl.value = ''
  inputType.value = 'auto'
  serverStore.switchServer('', 'auto')
  panelOpen.value = false
  const online = await serverStore.checkConnection()
  if (online) {
    appStore.success('已切换到本地代理')
    return
  }
  appStore.error(serverStore.lastErrorMessage || '本地代理不可用')
}

const removeHistory = (url: string) => {
  serverStore.removeHistory(url)
}

const refreshStatus = async () => {
  const online = await serverStore.checkConnection()
  if (online) {
    appStore.success('连接状态正常', 2000)
    return
  }
  appStore.warning(serverStore.lastErrorMessage || '连接检测失败', 3000)
}

const handleClickOutside = (event: MouseEvent) => {
  const target = event.target as HTMLElement
  if (!target.closest('.topbar-panel-wrap')) {
    panelOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<template>
  <header class="topbar">
    <div class="topbar-left">
      <div class="server-meta">
        <div class="status-badge" :class="statusConfig.class">
          <component :is="statusConfig.icon" class="status-icon" />
          <span class="status-text">{{ statusText }}</span>
        </div>
        <div class="server-info">
          <span class="server-url">{{ serverStore.currentLabel }}</span>
          <div class="server-tags">
            <div
              class="backend-tag"
              :style="{
                background: backendConfig.bgColor,
                borderColor: backendConfig.borderColor,
                color: backendConfig.color
              }"
            >
              <component :is="backendConfig.icon" class="tag-icon" />
              <span>{{ backendConfig.shortLabel }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="topbar-right topbar-panel-wrap">
      <button class="topbar-icon-btn" title="刷新连接状态" @click.stop="refreshStatus">
        <RefreshCw
          class="w-4 h-4"
          :class="{ 'animate-spin': serverStore.connectionStatus === 'checking' }"
        />
      </button>
      <button
        class="topbar-switch-btn"
        :class="{ active: panelOpen }"
        @click.stop="panelOpen = !panelOpen"
      >
        <Plug class="w-4 h-4" />
        <span>切换服务</span>
        <ChevronDown class="w-4 h-4 chevron" :class="{ rotate: panelOpen }" />
      </button>

      <div v-if="panelOpen" class="topbar-panel">
        <!-- 当前连接状态卡片 -->
        <div class="connection-card" :class="statusConfig.class">
          <div class="connection-header">
            <div class="connection-title">
              <component :is="statusConfig.icon" class="connection-status-icon" />
              <span>当前连接</span>
            </div>
            <div class="connection-badge" :style="{ color: statusConfig.textColor }">
              {{ statusText }}
            </div>
          </div>
          <div class="connection-body">
            <div class="connection-backend">
              <div
                class="backend-icon-wrap"
                :style="{ background: backendConfig.bgColor }"
              >
                <component :is="backendConfig.icon" class="backend-icon" :style="{ color: backendConfig.color }" />
              </div>
              <div class="backend-info">
                <div class="backend-name">{{ backendConfig.label }}</div>
                <div class="backend-url">{{ serverStore.currentLabel }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 手动连接区域 -->
        <div class="panel-section">
          <div class="section-header">
            <div class="section-icon-wrap manual">
              <Plug class="section-icon" />
            </div>
            <div class="section-title">手动连接</div>
          </div>
          <div class="panel-form">
            <div class="input-group">
              <Globe class="input-icon" />
              <input v-model="inputUrl" class="server-input" placeholder="http://host:port" />
            </div>
            <div class="input-group select-group">
              <select v-model="inputType" class="server-select">
                <option value="auto">Auto</option>
                <option value="go">Go</option>
                <option value="python">Python</option>
              </select>
            </div>
          </div>
          <div class="panel-actions">
            <button class="panel-btn ghost" @click="useLocalProxy">
              <Server class="btn-icon" />
              <span>本地代理</span>
            </button>
            <button class="panel-btn primary" @click="applyServer">
              <Plug class="btn-icon" />
              <span>连接</span>
            </button>
          </div>
        </div>

        <!-- 历史记录 -->
        <div v-if="serverStore.history.length" class="panel-section history-section">
          <div class="section-header">
            <div class="section-icon-wrap history">
              <RefreshCw class="section-icon" />
            </div>
            <div class="section-title">历史连接</div>
            <span class="history-count">{{ serverStore.history.length }}</span>
          </div>
          <div class="history-list">
            <div
              v-for="item in serverStore.history"
              :key="item.url"
              class="history-item"
              :class="{ active: item.url === serverStore.activeUrl }"
            >
              <button class="history-main" @click="useHistory(item.url, item.backendType)">
                <div class="history-content">
                  <div class="history-url-row">
                    <span class="history-type-badge" :class="item.backendType">{{ item.backendType.toUpperCase() }}</span>
                    <span class="history-url">{{ item.url }}</span>
                  </div>
                  <div class="history-meta">
                    <span class="history-time">{{ formatTime(item.lastUsedAt) }}</span>
                  </div>
                </div>
                <div v-if="item.url === serverStore.activeUrl" class="active-indicator">
                  <CheckCircle2 class="w-4 h-4" />
                </div>
              </button>
              <button class="history-delete" @click.stop="removeHistory(item.url)">
                <Trash2 class="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </header>
</template>

<style scoped>
.topbar {
  --topbar-bg-start: rgba(11, 15, 28, 0.98);
  --topbar-bg-end: rgba(11, 15, 28, 0.95);
  --topbar-border: rgba(99, 102, 241, 0.1);
  --topbar-line-start: rgba(99, 102, 241, 0.3);
  --topbar-line-mid: rgba(6, 182, 212, 0.4);
  --panel-color-scheme: dark;
  --icon-btn-bg: rgba(99, 102, 241, 0.08);
  --icon-btn-border: rgba(99, 102, 241, 0.15);
  --icon-btn-hover-bg: rgba(99, 102, 241, 0.15);
  --icon-btn-hover-border: rgba(99, 102, 241, 0.3);
  --icon-btn-hover-shadow: 0 0 16px rgba(99, 102, 241, 0.2);
  --switch-btn-bg: linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(6, 182, 212, 0.08) 100%);
  --switch-btn-hover-bg: linear-gradient(135deg, rgba(99, 102, 241, 0.18) 0%, rgba(6, 182, 212, 0.12) 100%);
  --switch-btn-active-bg: linear-gradient(135deg, rgba(99, 102, 241, 0.25) 0%, rgba(6, 182, 212, 0.15) 100%);
  --switch-btn-border: rgba(99, 102, 241, 0.2);
  --switch-btn-hover-border: rgba(99, 102, 241, 0.35);
  --switch-btn-active-border: rgba(99, 102, 241, 0.5);
  --switch-btn-hover-shadow: 0 4px 20px rgba(99, 102, 241, 0.25);
  --switch-btn-active-shadow: 0 0 24px rgba(99, 102, 241, 0.3);
  --panel-bg: rgba(11, 15, 28, 0.95);
  --panel-border: rgba(99, 102, 241, 0.2);
  --panel-shadow:
    0 24px 64px rgba(0, 0, 0, 0.5),
    0 0 0 1px rgba(99, 102, 241, 0.1);
  --panel-arrow-bg: rgba(16, 20, 35, 0.98);
  --panel-arrow-border: rgba(99, 102, 241, 0.15);
  --connection-badge-bg: rgba(255, 255, 255, 0.05);
  --panel-section-bg: rgba(99, 102, 241, 0.04);
  --panel-section-border: rgba(99, 102, 241, 0.1);
  --section-icon-manual-bg: linear-gradient(135deg, rgba(99, 102, 241, 0.15) 0%, rgba(139, 92, 246, 0.1) 100%);
  --section-icon-history-bg: linear-gradient(135deg, rgba(6, 182, 212, 0.15) 0%, rgba(99, 102, 241, 0.1) 100%);
  --section-icon-color: #818cf8;
  --history-count-bg: rgba(99, 102, 241, 0.1);
  --input-bg: rgba(11, 15, 28, 0.5);
  --input-focus-bg: rgba(11, 15, 28, 0.8);
  --input-border: rgba(99, 102, 241, 0.15);
  --input-focus-border: rgba(99, 102, 241, 0.4);
  --input-focus-ring: 0 0 0 3px rgba(99, 102, 241, 0.1);
  --subtle-btn-bg: rgba(99, 102, 241, 0.08);
  --subtle-btn-border: rgba(99, 102, 241, 0.15);
  --subtle-btn-hover-bg: rgba(99, 102, 241, 0.15);
  --subtle-btn-hover-border: rgba(99, 102, 241, 0.3);
  --subtle-btn-hover-color: #818cf8;
  --primary-btn-bg: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
  --primary-btn-hover-bg: linear-gradient(135deg, #7c7ff5 0%, #6366f1 100%);
  --primary-btn-border: rgba(99, 102, 241, 0.4);
  --primary-btn-shadow: 0 4px 16px rgba(99, 102, 241, 0.3);
  --primary-btn-hover-shadow: 0 6px 24px rgba(99, 102, 241, 0.4);
  --history-item-bg: rgba(11, 15, 28, 0.4);
  --history-item-hover-bg: rgba(99, 102, 241, 0.08);
  --history-item-active-bg: rgba(99, 102, 241, 0.12);
  --history-item-hover-border: rgba(99, 102, 241, 0.2);
  --history-item-active-border: rgba(99, 102, 241, 0.35);
  --delete-btn-bg: rgba(11, 15, 28, 0.4);
  --delete-btn-hover-bg: rgba(239, 68, 68, 0.15);
  --delete-btn-hover-border: rgba(239, 68, 68, 0.3);
  --delete-btn-hover-color: #ef4444;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: var(--topbar-height);
  z-index: 80;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: linear-gradient(180deg, var(--topbar-bg-start) 0%, var(--topbar-bg-end) 100%);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--topbar-border);
}

.topbar::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent 0%,
    var(--topbar-line-start) 20%,
    var(--topbar-line-mid) 50%,
    var(--topbar-line-start) 80%,
    transparent 100%
  );
}

:global([data-theme='light']) .topbar {
  --topbar-bg-start: rgba(255, 255, 255, 0.96);
  --topbar-bg-end: rgba(248, 250, 252, 0.92);
  --topbar-border: rgba(99, 102, 241, 0.08);
  --topbar-line-start: rgba(99, 102, 241, 0.18);
  --topbar-line-mid: rgba(6, 182, 212, 0.22);
  --panel-color-scheme: light;
  --icon-btn-bg: rgba(99, 102, 241, 0.06);
  --icon-btn-border: rgba(99, 102, 241, 0.12);
  --icon-btn-hover-bg: rgba(99, 102, 241, 0.12);
  --icon-btn-hover-border: rgba(99, 102, 241, 0.18);
  --icon-btn-hover-shadow: 0 8px 20px rgba(99, 102, 241, 0.12);
  --switch-btn-bg: linear-gradient(135deg, rgba(99, 102, 241, 0.08) 0%, rgba(6, 182, 212, 0.06) 100%);
  --switch-btn-hover-bg: linear-gradient(135deg, rgba(99, 102, 241, 0.14) 0%, rgba(6, 182, 212, 0.1) 100%);
  --switch-btn-active-bg: linear-gradient(135deg, rgba(99, 102, 241, 0.16) 0%, rgba(6, 182, 212, 0.12) 100%);
  --switch-btn-border: rgba(99, 102, 241, 0.14);
  --switch-btn-hover-border: rgba(99, 102, 241, 0.22);
  --switch-btn-active-border: rgba(99, 102, 241, 0.28);
  --switch-btn-hover-shadow: 0 10px 24px rgba(99, 102, 241, 0.12);
  --switch-btn-active-shadow: 0 12px 30px rgba(99, 102, 241, 0.14);
  --panel-bg: rgba(255, 255, 255, 0.96);
  --panel-border: rgba(99, 102, 241, 0.14);
  --panel-shadow:
    0 20px 48px rgba(15, 23, 42, 0.12),
    0 0 0 1px rgba(99, 102, 241, 0.06);
  --panel-arrow-bg: rgba(255, 255, 255, 0.98);
  --panel-arrow-border: rgba(99, 102, 241, 0.12);
  --connection-badge-bg: rgba(99, 102, 241, 0.08);
  --panel-section-bg: rgba(99, 102, 241, 0.05);
  --panel-section-border: rgba(99, 102, 241, 0.12);
  --section-icon-manual-bg: linear-gradient(135deg, rgba(99, 102, 241, 0.12) 0%, rgba(139, 92, 246, 0.08) 100%);
  --section-icon-history-bg: linear-gradient(135deg, rgba(6, 182, 212, 0.12) 0%, rgba(99, 102, 241, 0.08) 100%);
  --section-icon-color: #6366f1;
  --history-count-bg: rgba(99, 102, 241, 0.08);
  --input-bg: rgba(255, 255, 255, 0.92);
  --input-focus-bg: rgba(255, 255, 255, 1);
  --input-border: rgba(99, 102, 241, 0.12);
  --input-focus-border: rgba(99, 102, 241, 0.24);
  --input-focus-ring: 0 0 0 3px rgba(99, 102, 241, 0.08);
  --subtle-btn-bg: rgba(99, 102, 241, 0.06);
  --subtle-btn-border: rgba(99, 102, 241, 0.12);
  --subtle-btn-hover-bg: rgba(99, 102, 241, 0.12);
  --subtle-btn-hover-border: rgba(99, 102, 241, 0.18);
  --subtle-btn-hover-color: #6366f1;
  --primary-btn-bg: linear-gradient(135deg, #6366f1 0%, #5b68f6 100%);
  --primary-btn-hover-bg: linear-gradient(135deg, #7075f8 0%, #6366f1 100%);
  --primary-btn-border: rgba(99, 102, 241, 0.2);
  --primary-btn-shadow: 0 10px 24px rgba(99, 102, 241, 0.18);
  --primary-btn-hover-shadow: 0 14px 28px rgba(99, 102, 241, 0.22);
  --history-item-bg: rgba(241, 245, 249, 0.95);
  --history-item-hover-bg: rgba(99, 102, 241, 0.08);
  --history-item-active-bg: rgba(99, 102, 241, 0.1);
  --history-item-hover-border: rgba(99, 102, 241, 0.16);
  --history-item-active-border: rgba(99, 102, 241, 0.24);
  --delete-btn-bg: rgba(241, 245, 249, 0.95);
  --delete-btn-hover-bg: rgba(239, 68, 68, 0.1);
  --delete-btn-hover-border: rgba(239, 68, 68, 0.18);
  --delete-btn-hover-color: #dc2626;
}

.topbar-left,
.topbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.server-meta {
  display: flex;
  align-items: center;
  gap: 14px;
}

.status-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  border: 1px solid transparent;
  transition: all 0.3s ease;
}

.status-badge.online {
  background: rgba(34, 197, 94, 0.12);
  border-color: rgba(34, 197, 94, 0.3);
  color: #22c55e;
  box-shadow: 0 0 12px rgba(34, 197, 94, 0.15);
}

.status-badge.checking {
  background: rgba(245, 158, 11, 0.12);
  border-color: rgba(245, 158, 11, 0.3);
  color: #f59e0b;
  box-shadow: 0 0 12px rgba(245, 158, 11, 0.15);
}

.status-badge.offline {
  background: rgba(239, 68, 68, 0.12);
  border-color: rgba(239, 68, 68, 0.3);
  color: #ef4444;
  box-shadow: 0 0 12px rgba(239, 68, 68, 0.15);
}

.status-icon {
  width: 14px;
  height: 14px;
}

.server-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.server-url {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  max-width: min(40vw, 400px);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.server-tags {
  display: flex;
  align-items: center;
  gap: 8px;
}

.backend-tag {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 700;
  border: 1px solid;
  letter-spacing: 0.5px;
}

.tag-icon {
  width: 12px;
  height: 12px;
}

.topbar-icon-btn,
.topbar-switch-btn,
.panel-btn,
.history-delete,
.history-main {
  border: none;
  cursor: pointer;
  font-family: inherit;
}

.topbar-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: var(--icon-btn-bg);
  color: var(--text-secondary);
  border: 1px solid var(--icon-btn-border);
  transition: all 0.25s ease;
}

.topbar-icon-btn:hover {
  color: #818cf8;
  background: var(--icon-btn-hover-bg);
  border-color: var(--icon-btn-hover-border);
  box-shadow: var(--icon-btn-hover-shadow);
  transform: translateY(-1px);
}

.topbar-switch-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 36px;
  padding: 0 16px;
  border-radius: 10px;
  background: var(--switch-btn-bg);
  color: var(--text-primary);
  border: 1px solid var(--switch-btn-border);
  font-size: 13px;
  font-weight: 600;
  transition: all 0.25s ease;
}

.topbar-switch-btn:hover {
  background: var(--switch-btn-hover-bg);
  border-color: var(--switch-btn-hover-border);
  box-shadow: var(--switch-btn-hover-shadow);
  transform: translateY(-1px);
}

.topbar-switch-btn.active {
  background: var(--switch-btn-active-bg);
  border-color: var(--switch-btn-active-border);
  box-shadow: var(--switch-btn-active-shadow);
}

.chevron {
  transition: transform 0.3s ease;
}

.chevron.rotate {
  transform: rotate(180deg);
}

.topbar-panel-wrap {
  position: relative;
}

.topbar-panel {
  position: absolute;
  top: calc(100% + 12px);
  right: 0;
  width: 420px;
  padding: 14px;
  border-radius: 16px;
  background: var(--panel-bg);
  border: 1px solid var(--panel-border);
  box-shadow: var(--panel-shadow);
  backdrop-filter: blur(24px);
  color-scheme: var(--panel-color-scheme);
}

.topbar-panel::before {
  content: '';
  position: absolute;
  top: -6px;
  right: 24px;
  width: 12px;
  height: 12px;
  background: var(--panel-arrow-bg);
  border-left: 1px solid var(--panel-arrow-border);
  border-top: 1px solid var(--panel-arrow-border);
  transform: rotate(45deg);
}

/* 连接状态卡片 */
.connection-card {
  padding: 18px;
  border-radius: 14px;
  border: 1px solid;
  margin-bottom: 20px;
  transition: all 0.3s ease;
}

.connection-card.online {
  background: linear-gradient(135deg, rgba(34, 197, 94, 0.08) 0%, rgba(34, 197, 94, 0.04) 100%);
  border-color: rgba(34, 197, 94, 0.25);
  box-shadow: 0 4px 20px rgba(34, 197, 94, 0.1);
}

.connection-card.checking {
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.08) 0%, rgba(245, 158, 11, 0.04) 100%);
  border-color: rgba(245, 158, 11, 0.25);
  box-shadow: 0 4px 20px rgba(245, 158, 11, 0.1);
}

.connection-card.offline {
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.08) 0%, rgba(239, 68, 68, 0.04) 100%);
  border-color: rgba(239, 68, 68, 0.25);
  box-shadow: 0 4px 20px rgba(239, 68, 68, 0.1);
}

.connection-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.connection-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 700;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.connection-status-icon {
  width: 16px;
  height: 16px;
}

.connection-card.online .connection-status-icon {
  color: #22c55e;
}

.connection-card.checking .connection-status-icon {
  color: #f59e0b;
}

.connection-card.offline .connection-status-icon {
  color: #ef4444;
}

.connection-badge {
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 700;
  background: var(--connection-badge-bg);
}

.connection-backend {
  display: flex;
  align-items: center;
  gap: 14px;
}

.backend-icon-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 14px;
}

.backend-icon {
  width: 24px;
  height: 24px;
}

.backend-info {
  flex: 1;
  min-width: 0;
}

.backend-name {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.backend-url {
  font-size: 12px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 面板分区 */
.panel-section {
  padding: 20px;
  border-radius: 14px;
  background: var(--panel-section-bg);
  border: 1px solid var(--panel-section-border);
}

.panel-section + .panel-section {
  margin-top: 16px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.section-icon-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
}

.section-icon-wrap.manual {
  background: var(--section-icon-manual-bg);
}

.section-icon-wrap.history {
  background: var(--section-icon-history-bg);
}

.section-icon {
  width: 14px;
  height: 14px;
  color: var(--section-icon-color);
}

.section-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.history-count {
  margin-left: auto;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 700;
  color: var(--text-tertiary);
  background: var(--history-count-bg);
}

/* 表单样式 */
.panel-form {
  display: grid;
  grid-template-columns: 1fr 100px;
  gap: 10px;
  margin-bottom: 14px;
}

.input-group {
  position: relative;
}

.input-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  width: 16px;
  height: 16px;
  color: var(--text-tertiary);
  pointer-events: none;
}

.server-input {
  width: 100%;
  height: 42px;
  padding: 0 12px 0 38px;
  border-radius: 10px;
  border: 1px solid var(--input-border);
  background: var(--input-bg);
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
  transition: all 0.25s ease;
}

.server-input::placeholder {
  color: var(--text-tertiary);
}

.server-input:focus {
  border-color: var(--input-focus-border);
  background: var(--input-focus-bg);
  box-shadow: var(--input-focus-ring);
}

.select-group::after {
  content: '';
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  width: 0;
  height: 0;
  border-left: 4px solid transparent;
  border-right: 4px solid transparent;
  border-top: 4px solid var(--text-tertiary);
  pointer-events: none;
}

.server-select {
  width: 100%;
  height: 42px;
  padding: 0 30px 0 12px;
  border-radius: 10px;
  border: 1px solid var(--input-border);
  background: var(--input-bg);
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
  cursor: pointer;
  appearance: none;
  transition: all 0.25s ease;
}

.server-select:focus {
  border-color: var(--input-focus-border);
  background: var(--input-focus-bg);
  box-shadow: var(--input-focus-ring);
}

.server-select option {
  background: var(--bg-card);
  color: var(--text-primary);
}

/* 按钮样式 */
.panel-actions {
  display: flex;
  gap: 10px;
}

.panel-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 40px;
  padding: 0 16px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  transition: all 0.25s ease;
}

.btn-icon {
  width: 14px;
  height: 14px;
}

.panel-btn.ghost {
  background: var(--subtle-btn-bg);
  color: var(--text-secondary);
  border: 1px solid var(--subtle-btn-border);
}

.panel-btn.ghost:hover {
  background: var(--subtle-btn-hover-bg);
  border-color: var(--subtle-btn-hover-border);
  color: var(--subtle-btn-hover-color);
  transform: translateY(-1px);
}

.panel-btn.primary {
  background: var(--primary-btn-bg);
  color: #fff;
  border: 1px solid var(--primary-btn-border);
  box-shadow: var(--primary-btn-shadow);
}

.panel-btn.primary:hover {
  background: var(--primary-btn-hover-bg);
  box-shadow: var(--primary-btn-hover-shadow);
  transform: translateY(-1px);
}

/* 历史记录 */
.history-section {
  padding: 16px;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 220px;
  overflow-y: auto;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.history-item.active .history-main {
  background: var(--history-item-active-bg);
  border-color: var(--history-item-active-border);
}

.history-main {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 10px;
  background: var(--history-item-bg);
  border: 1px solid transparent;
  color: var(--text-primary);
  text-align: left;
  transition: all 0.2s ease;
}

.history-main:hover {
  background: var(--history-item-hover-bg);
  border-color: var(--history-item-hover-border);
}

.history-content {
  flex: 1;
  min-width: 0;
}

.history-url-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.history-type-badge {
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 700;
}

.history-type-badge.go {
  background: rgba(6, 182, 212, 0.15);
  color: #06b6d4;
}

.history-type-badge.python {
  background: rgba(245, 158, 11, 0.15);
  color: #f59e0b;
}

.history-type-badge.auto {
  background: rgba(139, 92, 246, 0.15);
  color: #8b5cf6;
}

.history-url {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-meta {
  font-size: 11px;
  color: var(--text-tertiary);
}

.active-indicator {
  color: #22c55e;
}

.history-delete {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: var(--delete-btn-bg);
  color: var(--text-tertiary);
  border: 1px solid transparent;
  transition: all 0.2s ease;
}

.history-delete:hover {
  background: var(--delete-btn-hover-bg);
  border-color: var(--delete-btn-hover-border);
  color: var(--delete-btn-hover-color);
}
</style>
