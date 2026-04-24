<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ChevronDown, Plug, RefreshCw, Trash2 } from 'lucide-vue-next'
import { useServerStore, type BackendType } from '@/stores/server'
import { useAppStore } from '@/stores/app'

const serverStore = useServerStore()
const appStore = useAppStore()
const panelOpen = ref(false)
const inputUrl = ref(serverStore.activeUrl)
const inputType = ref<BackendType>(serverStore.backendType)

const statusClass = computed(() => {
  if (serverStore.connectionStatus === 'online') return 'online'
  if (serverStore.connectionStatus === 'checking') return 'warning'
  return 'error'
})

const backendLabel = computed(() => {
  if (serverStore.backendType === 'auto') return 'AUTO'
  return serverStore.backendType.toUpperCase()
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
  await serverStore.checkConnection()
  appStore.success(`已切换到 ${serverStore.currentLabel}`)
}

const useHistory = async (url: string, type: BackendType) => {
  inputUrl.value = url
  inputType.value = type
  serverStore.switchServer(url, type)
  panelOpen.value = false
  await serverStore.checkConnection()
  appStore.success(`已切换到 ${serverStore.currentLabel}`)
}

const useLocalProxy = async () => {
  inputUrl.value = ''
  inputType.value = 'auto'
  serverStore.switchServer('', 'auto')
  panelOpen.value = false
  await serverStore.checkConnection()
  appStore.success('已切换到本地代理')
}

const removeHistory = (url: string) => {
  serverStore.removeHistory(url)
}

const refreshStatus = async () => {
  await serverStore.checkConnection()
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
        <span class="status-dot" :class="statusClass"></span>
        <span class="server-url">{{ serverStore.currentLabel }}</span>
        <span class="server-tag">{{ backendLabel }}</span>
        <span class="server-state">{{ statusText }}</span>
      </div>
    </div>

    <div class="topbar-right topbar-panel-wrap">
      <button class="topbar-icon-btn" @click.stop="refreshStatus" title="刷新连接状态">
        <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': serverStore.connectionStatus === 'checking' }" />
      </button>
      <button class="topbar-switch-btn" @click.stop="panelOpen = !panelOpen">
        <Plug class="w-4 h-4" />
        <span>切换服务</span>
        <ChevronDown class="w-4 h-4" />
      </button>

      <div v-if="panelOpen" class="topbar-panel card-base">
        <div class="panel-section">
          <div class="panel-title">当前连接</div>
          <div class="current-server">
            <span class="status-dot" :class="statusClass"></span>
            <span class="current-server-text">{{ serverStore.currentLabel }}</span>
          </div>
        </div>

        <div class="panel-section">
          <div class="panel-title">手动连接</div>
          <div class="panel-form">
            <input v-model="inputUrl" class="server-input" placeholder="http://host:port" />
            <select v-model="inputType" class="server-select">
              <option value="auto">Auto</option>
              <option value="go">Go</option>
              <option value="python">Python</option>
            </select>
          </div>
          <div class="panel-actions">
            <button class="panel-btn ghost" @click="useLocalProxy">本地代理</button>
            <button class="panel-btn primary" @click="applyServer">连接</button>
          </div>
        </div>

        <div class="panel-section" v-if="serverStore.history.length">
          <div class="panel-title">历史地址</div>
          <div class="history-list">
            <div v-for="item in serverStore.history" :key="item.url" class="history-item" :class="{ active: item.url === serverStore.activeUrl }">
              <button class="history-main" @click="useHistory(item.url, item.backendType)">
                <span class="history-url">{{ item.url }}</span>
                <span class="history-meta">{{ item.backendType.toUpperCase() }} · {{ formatTime(item.lastUsedAt) }}</span>
              </button>
              <button class="history-delete" @click.stop="removeHistory(item.url)">
                <Trash2 class="w-3.5 h-3.5" />
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
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: var(--topbar-height);
  z-index: 80;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  background: var(--bg-sidebar);
  border-bottom: 1px solid var(--border-card);
}

.topbar-left,
.topbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.server-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.server-url {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  max-width: min(46vw, 520px);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.server-tag,
.server-state {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  border: 1px solid var(--border-card);
  color: var(--text-secondary);
  background: var(--bg-card);
}

.topbar-icon-btn,
.topbar-switch-btn,
.panel-btn,
.history-delete,
.history-main {
  border: none;
  cursor: pointer;
}

.topbar-icon-btn,
.topbar-switch-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 30px;
  padding: 0 12px;
  border-radius: 10px;
  background: var(--bg-card);
  color: var(--text-secondary);
  border: 1px solid var(--border-card);
  transition: all 0.2s ease;
}

.topbar-icon-btn:hover,
.topbar-switch-btn:hover,
.panel-btn:hover,
.history-delete:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.topbar-panel-wrap {
  position: relative;
}

.topbar-panel {
  position: absolute;
  top: calc(100% + 10px);
  right: 0;
  width: 420px;
  padding: 14px;
  border-radius: 14px;
  background: var(--bg-card);
}

.panel-section + .panel-section {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--border-primary);
}

.panel-title {
  margin-bottom: 10px;
  font-size: 12px;
  font-weight: 700;
  color: var(--text-secondary);
}

.current-server {
  display: flex;
  align-items: center;
  gap: 10px;
}

.current-server-text,
.history-url {
  font-size: 13px;
  color: var(--text-primary);
  word-break: break-all;
}

.panel-form {
  display: grid;
  grid-template-columns: 1fr 92px;
  gap: 10px;
}

.server-input,
.server-select {
  height: 38px;
  border-radius: 10px;
  border: 1px solid var(--border-card);
  background: var(--bg-input);
  color: var(--text-primary);
  padding: 0 12px;
  outline: none;
}

.panel-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 10px;
}

.panel-btn {
  height: 34px;
  padding: 0 14px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 600;
}

.panel-btn.ghost {
  background: var(--bg-secondary);
  color: var(--text-secondary);
}

.panel-btn.primary {
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-dark) 100%);
  color: #fff;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 240px;
  overflow-y: auto;
}

.history-item {
  display: flex;
  align-items: stretch;
  gap: 8px;
}

.history-item.active .history-main {
  border-color: rgba(var(--color-primary-rgb), 0.45);
  background: rgba(var(--color-primary-rgb), 0.12);
}

.history-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 12px;
  background: var(--bg-secondary);
  color: var(--text-primary);
  border: 1px solid transparent;
}

.history-meta {
  font-size: 11px;
  color: var(--text-tertiary);
}

.history-delete {
  width: 34px;
  border-radius: 10px;
  background: var(--bg-secondary);
  color: var(--text-muted);
  border: 1px solid transparent;
}
</style>
