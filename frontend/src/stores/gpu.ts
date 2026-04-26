import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getGPUSummary } from '@/api/client'
import type { GPUSummary } from '@/types'

export const useGPUStore = defineStore('gpu', () => {
  const gpuSummary = ref<GPUSummary | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  let timer: number | null = null
  let subscriberCount = 0

  const fetchGPUData = async () => {
    loading.value = true
    error.value = null
    try {
      gpuSummary.value = await getGPUSummary()
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch GPU data'
    } finally {
      loading.value = false
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
  }

  const refresh = () => fetchGPUData()

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
