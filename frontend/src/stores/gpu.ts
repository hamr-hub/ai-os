import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getGPUSummary } from '@/api/client'
import type { GPUSummary, GPUStatus } from '@/types'
import { isAbortError } from '@/utils/request'
import { useMonitorWS } from '@/utils/monitorWebSocket'

const toSummaryCurrent = (gpu: GPUStatus): GPUSummary['current'] => ({
  name: gpu.name,
  gpu_count: gpu.all_gpus?.length || gpu.gpu_count || 1,
  utilization: gpu.utilization,
  temperature: gpu.temperature,
  power_draw: gpu.power_draw,
  power_limit: gpu.power_limit,
  power_percent: gpu.power_percent,
  memory_utilization: gpu.memory_utilization,
  used_memory: gpu.used_memory,
  available_memory: gpu.available_memory,
  total_memory: gpu.total_memory,
  fan_speed: gpu.fan_speed,
  clock_sm: gpu.clock_sm,
  clock_mem: gpu.clock_mem,
  vllm_metrics: gpu.vllm_metrics,
})

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

  const handleWSMessage = (data: { gpu?: GPUStatus }) => {
    if (!data.gpu) return

    gpuSummary.value = {
      status: data.gpu.status || 'available',
      current: toSummaryCurrent(data.gpu),
      history: gpuSummary.value?.history || [],
    }
    loading.value = false
    error.value = null
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
