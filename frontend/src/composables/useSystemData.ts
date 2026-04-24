import { ref, onMounted, onUnmounted, computed, type MaybeRefOrGetter, toValue } from 'vue'
import { getSystemStatus, getHealthAlert, getSystemHistory } from '@/api/client'
import type { SystemStatus, HealthAlert } from '@/types'

export function useSystemData(intervalMs = 10000, initialCount: MaybeRefOrGetter<number> = 60) {
  const systemStatus = ref<SystemStatus | null>(null)
  const healthAlert = ref<HealthAlert | null>(null)
  const systemHistory = ref<any[]>([])
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
      const [status, alert, historyData] = await Promise.all([
        getSystemStatus(),
        getHealthAlert(),
        getSystemHistory(toValue(initialCount))
      ])
      systemStatus.value = status
      healthAlert.value = alert
      systemHistory.value = historyData.history
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch system data'
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

  const queueStatus = computed(() => systemStatus.value?.queue ?? null)

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
