import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getGPUSummary } from '@/api/client'
import type { GPUSummary } from '@/types'
import { isAbortError } from '@/utils/request'
import { useMonitorWS } from '@/utils/monitorWebSocket'

export const useGPUStore = defineStore('gpu', () => {
  const gpuSummary = ref<GPUSummary | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const wsConnected = ref(false)
  let timer: number | null = null
  let subscriberCount = 0
  let activeController: AbortController | null = null
  let unsubscribeWS: (() => void) | null = null
  const monitorWS = useMonitorWS()

  const fetchGPUData = async (force = false) => {
    if (activeController) {
      if (!force) return
      activeController.abort()
    }

    const controller = new AbortController()
    activeController = controller
    loading.value = true
    error.value = null
    try {
      gpuSummary.value = await getGPUSummary({ signal: controller.signal })
    } catch (err) {
      if (!isAbortError(err)) {
        error.value = err instanceof Error ? err.message : 'Failed to fetch GPU data'
      }
    } finally {
      if (activeController === controller) {
        activeController = null
        loading.value = false
      }
    }
  }

  const handleWSMessage = (data: any) => {
    if (data.gpu) {
      gpuSummary.value = {
        current: data.gpu,
        status: data.gpu.status || 'available',
        models: data.models || gpuSummary.value?.models || {},
        current_model: data.current_model || gpuSummary.value?.current_model,
        default_model: data.default_model || gpuSummary.value?.default_model,
      }
      loading.value = false
      error.value = null
    }
  }

  const startPolling = () => {
    subscriberCount++
    if (timer) return

    unsubscribeWS = monitorWS.subscribe('monitor_state_sync', handleWSMessage)
    wsConnected.value = monitorWS.connected.value

    fetchGPUData()
    timer = window.setInterval(fetchGPUData, 30000)
  }

  const stopPolling = () => {
    subscriberCount = Math.max(0, subscriberCount - 1)
    if (subscriberCount === 0 && timer) {
      clearInterval(timer)
      timer = null
    }
    if (subscriberCount === 0 && activeController) {
      activeController.abort()
      activeController = null
    }
    if (subscriberCount === 0 && unsubscribeWS) {
      unsubscribeWS()
      unsubscribeWS = null
    }
    if (subscriberCount === 0) {
      wsConnected.value = false
    }
  }

  const refresh = () => fetchGPUData(true)

  const gpuCurrent = computed(() => gpuSummary.value?.current ?? null)
  const gpuStatus = computed(() => gpuSummary.value?.status ?? 'unavailable')

  return {
    gpuSummary,
    gpuCurrent,
    gpuStatus,
    loading,
    error,
    wsConnected,
    refresh,
    startPolling,
    stopPolling,
  }
})
