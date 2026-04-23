import { ref, onMounted, onUnmounted } from 'vue'
import { getSystemStatus, getQueueStatus, getHealthAlert } from '@/api/client'
import type { SystemStatus, QueueStatus, HealthAlert } from '@/types'

export function useSystemData(intervalMs = 10000) {
  const systemStatus = ref<SystemStatus | null>(null)
  const queueStatus = ref<QueueStatus | null>(null)
  const healthAlert = ref<HealthAlert | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  let timer: number | null = null

  const fetch = async () => {
    loading.value = true
    error.value = null
    try {
      systemStatus.value = await getSystemStatus()
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
  }

  const refresh = () => {
    fetch()
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
    loading,
    error,
    refresh,
    fetch,
    startPolling,
    stopPolling,
  }
}
