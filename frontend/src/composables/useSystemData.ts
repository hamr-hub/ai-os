import { ref, onMounted, onUnmounted } from 'vue'
import { getSystemStatus, getQueueStatus, getHealthAlert } from '@/api/client'
import type { SystemStatus, QueueStatus, HealthAlert, SystemHistoryEntry } from '@/types'

const MAX_HISTORY = 30

export function useSystemData(intervalMs = 10000) {
  const systemStatus = ref<SystemStatus | null>(null)
  const queueStatus = ref<QueueStatus | null>(null)
  const healthAlert = ref<HealthAlert | null>(null)
  const systemHistory = ref<SystemHistoryEntry[]>([])
  const loading = ref(false)
  const isRefreshing = ref(false)
  const error = ref<string | null>(null)
  let timer: number | null = null

  const fetch = async (manualRefresh = false) => {
    if (manualRefresh) {
      isRefreshing.value = true
    } else {
      loading.value = true
    }
    error.value = null
    try {
      systemStatus.value = await getSystemStatus()
      if (systemStatus.value) {
        systemHistory.value.push({
          timestamp: systemStatus.value.timestamp,
          cpu_percent: systemStatus.value.cpu.percent,
          memory_percent: systemStatus.value.memory.percent,
        })
        if (systemHistory.value.length > MAX_HISTORY) {
          systemHistory.value.shift()
        }
      }
    } catch (err) {
      console.error('Failed to fetch system status:', err)
    }
    try {
      queueStatus.value = await getQueueStatus()
    } catch (err) {
      console.error('Failed to fetch queue status:', err)
    }
    try {
      healthAlert.value = await getHealthAlert()
    } catch (err) {
      console.error('Failed to fetch health alert:', err)
    }
    loading.value = false
    isRefreshing.value = false
  }

  const refresh = () => {
    fetch(true)
  }

  const startPolling = () => {
    if (timer) return
    timer = window.setInterval(fetch, intervalMs)
  }

  const stopPolling = () => {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  onMounted(() => {
    fetch()
    startPolling()
  })

  onUnmounted(() => {
    stopPolling()
  })

  return {
    systemStatus,
    queueStatus,
    healthAlert,
    systemHistory,
    loading,
    isRefreshing,
    error,
    refresh,
    fetch,
    startPolling,
    stopPolling,
  }
}
