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
  const lastErrorMessage = ref<string | null>(null)
  const history = ref<ServerHistoryEntry[]>([])

  const manageBase = computed(() => (activeUrl.value ? `${activeUrl.value}/manage` : '/api'))
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

  const checkConnection = async (maxAttempts = 2): Promise<boolean> => {
    connectionStatus.value = 'checking'
    lastErrorMessage.value = null

    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
      const controller = new AbortController()
      const timeout = window.setTimeout(() => controller.abort(), 5000)

      try {
        const response = await fetch(healthUrl.value, {
          signal: controller.signal,
          cache: 'no-store',
          headers: { Accept: 'application/json' },
        })

        if (response.ok) {
          connectionStatus.value = 'online'
          lastCheckedAt.value = Date.now()
          return true
        }

        lastErrorMessage.value = `HTTP ${response.status}`
      } catch (error) {
        if (error instanceof Error) {
          lastErrorMessage.value =
            error.name === 'AbortError' ? '连接超时' : error.message || '连接失败'
        } else {
          lastErrorMessage.value = '连接失败'
        }
      } finally {
        window.clearTimeout(timeout)
      }

      if (attempt < maxAttempts) {
        await new Promise((resolve) => window.setTimeout(resolve, attempt * 300))
      }
    }

    connectionStatus.value = 'offline'
    lastCheckedAt.value = Date.now()
    return false
  }

  const initFromStorage = () => {
    const savedConfig = localStorage.getItem(CONFIG_STORAGE_KEY)
    if (savedConfig) {
      try {
        const parsed = JSON.parse(savedConfig) as StoredServerConfig
        activeUrl.value = normalizeUrl(parsed.activeUrl ?? '')
        backendType.value = parsed.backendType ?? 'auto'
      } catch (err) {
        console.warn('[ServerStore] Failed to parse saved config:', err)
      }
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
      } catch (err) {
        console.warn('[ServerStore] Failed to parse saved history:', err)
      }
    }
  }

  return {
    activeUrl,
    backendType,
    connectionStatus,
    lastCheckedAt,
    lastErrorMessage,
    history,
    manageBase,
    v1Base,
    healthUrl,
    currentLabel,
    switchServer,
    removeHistory,
    checkConnection,
    initFromStorage,
  }
})
