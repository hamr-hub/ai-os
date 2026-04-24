import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export type BackendType = 'go' | 'python' | 'auto'
export type ConnectionStatus = 'checking' | 'online' | 'offline'

interface ServerHistoryEntry {
  url: string
  backendType: BackendType
  addedAt: number
  lastUsedAt: number
}

interface StoredServerConfig {
  activeUrl: string
  backendType: BackendType
}

const CONFIG_STORAGE_KEY = 'server-config'
const HISTORY_STORAGE_KEY = 'server-history'
const MAX_HISTORY = 10

const normalizeUrl = (url: string) => url.trim().replace(/\/+$/, '')

export const useServerStore = defineStore('server', () => {
  const activeUrl = ref('')
  const backendType = ref<BackendType>('auto')
  const connectionStatus = ref<ConnectionStatus>('checking')
  const lastCheckedAt = ref<number | null>(null)
  const history = ref<ServerHistoryEntry[]>([])
  const pendingRemoteUrl = ref('')

  const manageBase = computed(() => (activeUrl.value ? `${activeUrl.value}/manage` : '/manage'))
  const v1Base = computed(() => (activeUrl.value ? `${activeUrl.value}/v1` : '/v1'))
  const healthUrl = computed(() => (activeUrl.value ? `${activeUrl.value}/health` : '/health'))
  const currentLabel = computed(() => activeUrl.value || '本地代理')

  const saveConfig = () => {
    const payload: StoredServerConfig = {
      activeUrl: activeUrl.value,
      backendType: backendType.value,
    }
    localStorage.setItem(CONFIG_STORAGE_KEY, JSON.stringify(payload))
  }

  const saveHistory = () => {
    localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(history.value))
  }

  const syncHistory = (url: string, type: BackendType) => {
    if (!url) return
    const now = Date.now()
    const existing = history.value.find((item) => item.url === url)
    if (existing) {
      existing.backendType = type
      existing.lastUsedAt = now
    } else {
      history.value.unshift({
        url,
        backendType: type,
        addedAt: now,
        lastUsedAt: now,
      })
    }
    history.value.sort((a, b) => b.lastUsedAt - a.lastUsedAt)
    history.value = history.value.slice(0, MAX_HISTORY)
    saveHistory()
  }

  const switchServer = (url: string, type: BackendType = backendType.value) => {
    const normalized = normalizeUrl(url)
    activeUrl.value = normalized
    backendType.value = type
    saveConfig()
    syncHistory(normalized, type)
  }

  const removeHistory = (url: string) => {
    history.value = history.value.filter((item) => item.url !== url)
    saveHistory()
  }

  const checkConnection = async () => {
    connectionStatus.value = 'checking'
    try {
      const controller = new AbortController()
      const timeout = window.setTimeout(() => controller.abort(), 5000)
      const response = await fetch(healthUrl.value, { signal: controller.signal })
      window.clearTimeout(timeout)
      if (response.ok) {
        connectionStatus.value = 'online'
      } else {
        connectionStatus.value = 'offline'
        if (activeUrl.value) {
          activeUrl.value = ''
          saveConfig()
        }
      }
    } catch {
      connectionStatus.value = 'offline'
      if (activeUrl.value) {
        activeUrl.value = ''
        saveConfig()
      }
    } finally {
      lastCheckedAt.value = Date.now()
    }
  }

  const initFromStorage = () => {
    const savedConfig = localStorage.getItem(CONFIG_STORAGE_KEY)
    if (savedConfig) {
      try {
        const parsed = JSON.parse(savedConfig) as StoredServerConfig
        const savedUrl = normalizeUrl(parsed.activeUrl ?? '')
        backendType.value = parsed.backendType ?? 'auto'
        pendingRemoteUrl.value = savedUrl
      } catch {}
    }

    const savedHistory = localStorage.getItem(HISTORY_STORAGE_KEY)
    if (savedHistory) {
      try {
        const parsed = JSON.parse(savedHistory) as ServerHistoryEntry[]
        history.value = parsed
          .map((item) => ({
            url: normalizeUrl(item.url),
            backendType: item.backendType ?? 'auto',
            addedAt: item.addedAt ?? Date.now(),
            lastUsedAt: item.lastUsedAt ?? item.addedAt ?? Date.now(),
          }))
          .filter((item) => item.url)
          .sort((a, b) => b.lastUsedAt - a.lastUsedAt)
          .slice(0, MAX_HISTORY)
      } catch {}
    }
  }

  const validateRemoteConnection = async () => {
    const savedUrl = pendingRemoteUrl.value
    if (!savedUrl) return
    try {
      const controller = new AbortController()
      const timeout = window.setTimeout(() => controller.abort(), 3000)
      const response = await fetch(`${savedUrl}/health`, { signal: controller.signal })
      window.clearTimeout(timeout)
      if (response.ok) {
        activeUrl.value = savedUrl
        connectionStatus.value = 'online'
        syncHistory(savedUrl, backendType.value)
      } else {
        activeUrl.value = ''
        connectionStatus.value = 'offline'
      }
    } catch {
      activeUrl.value = ''
      connectionStatus.value = 'offline'
    }
    saveConfig()
    pendingRemoteUrl.value = ''
  }

  return {
    activeUrl,
    backendType,
    connectionStatus,
    lastCheckedAt,
    history,
    manageBase,
    v1Base,
    healthUrl,
    currentLabel,
    switchServer,
    removeHistory,
    checkConnection,
    initFromStorage,
    validateRemoteConnection,
  }
})
