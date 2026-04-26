import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getGPUSummary } from '@/api/client'
import type { GPUSummary } from '@/types'
import { isAbortError } from '@/utils/request'

export const useGPUStore = defineStore('gpu', () => {
  const gpuSummary = ref<GPUSummary | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  let timer: number | null = null
  let subscriberCount = 0
  let activeController: AbortController | null = null

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

  const startPolling = () => {
    subscriberCount++
    if (timer) return
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
    refresh,
    startPolling,
    stopPolling,
  }
})
