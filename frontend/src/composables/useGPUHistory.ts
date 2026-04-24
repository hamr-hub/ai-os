import { ref, onMounted, onUnmounted, unref, type MaybeRefOrGetter } from 'vue'
import { getGPUHistory } from '@/api/client'
import type { GPUHistoryEntry } from '@/types'

export function useGPUHistory(count: MaybeRefOrGetter<number> = 120, intervalMs = 10000) {
  const gpuHistory = ref<GPUHistoryEntry[]>([])
  const loading = ref(false)
  const isRefreshing = ref(false)
  const error = ref<string | null>(null)
  let timer: number | null = null

  const fetchGPUHistory = async (manualRefresh = false) => {
    if (manualRefresh) {
      isRefreshing.value = true
    } else {
      loading.value = true
    }

    error.value = null

    try {
      const res = await getGPUHistory(Number(unref(count)))
      gpuHistory.value = res?.history ?? []
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'GPU历史数据获取失败'
    } finally {
      loading.value = false
      isRefreshing.value = false
    }
  }

  const refresh = () => fetchGPUHistory(true)

  const startPolling = () => {
    if (timer) return
    timer = window.setInterval(fetchGPUHistory, intervalMs)
  }

  const stopPolling = () => {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  onMounted(() => {
    fetchGPUHistory()
    startPolling()
  })

  onUnmounted(() => {
    stopPolling()
  })

  return {
    gpuHistory,
    loading,
    isRefreshing,
    error,
    fetchGPUHistory,
    refresh,
    startPolling,
    stopPolling,
  }
}
