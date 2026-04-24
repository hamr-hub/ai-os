import { ref, onMounted, onUnmounted, computed, type MaybeRefOrGetter, toValue } from 'vue'
import { getSystemStatus, getHealthAlert, getSystemHistory, getQueueStatus } from '@/api/client'
import type { SystemStatus, HealthAlert, QueueStatus } from '@/types'

export function useSystemData(intervalMs = 10000, initialCount: MaybeRefOrGetter<number> = 60) {
  const systemStatus = ref<SystemStatus | null>(null)
  const healthAlert = ref<HealthAlert | null>(null)
  const systemHistory = ref<any[]>([])
  const queueStatusRef = ref<QueueStatus | null>(null)
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
      const status = await getSystemStatus()
      systemStatus.value = status
      if (status.queue) {
        queueStatusRef.value = status.queue
      } else {
        try {
          queueStatusRef.value = await getQueueStatus()
        } catch {
          queueStatusRef.value = null
        }
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch system status'
      systemStatus.value = null
    }
    try {
      healthAlert.value = await getHealthAlert()
    } catch (err) {
      if (!error.value)
        error.value = err instanceof Error ? err.message : 'Failed to fetch health alert'
      healthAlert.value = null
    }
    try {
      const historyData = await getSystemHistory(toValue(initialCount))
      systemHistory.value = historyData.history
    } catch (err) {
      if (!error.value)
        error.value = err instanceof Error ? err.message : 'Failed to fetch system history'
      systemHistory.value = []
    } finally {
      loading.value = false
      isRefreshing.value = false
    }
  }

  const refresh = () => {
    return fetch(true)
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

  const queueStatus = computed(() => queueStatusRef.value)

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
    startPolling,
    stopPolling,
  }
}
