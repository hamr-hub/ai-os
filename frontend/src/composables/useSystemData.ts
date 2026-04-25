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
        } catch (err) {
          console.warn('[useSystemData] Queue status fetch failed:', err)
          queueStatusRef.value = null
        }
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch system status'
      if (!systemStatus.value) {
        systemStatus.value = null
      }
    }

    try {
      const [healthResult, historyResult] = await Promise.allSettled([
        getHealthAlert(),
        getSystemHistory(toValue(initialCount)),
      ])

      if (healthResult.status === 'fulfilled') {
        healthAlert.value = healthResult.value
      } else if (!error.value) {
        error.value =
          healthResult.reason instanceof Error
            ? healthResult.reason.message
            : 'Failed to fetch health alert'
      }

      if (historyResult.status === 'fulfilled') {
        systemHistory.value = historyResult.value.history
      } else if (!error.value) {
        error.value =
          historyResult.reason instanceof Error
            ? historyResult.reason.message
            : 'Failed to fetch system history'
      }
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
