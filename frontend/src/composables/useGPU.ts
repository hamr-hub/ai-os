import { ref, onMounted, onUnmounted, computed } from 'vue'
import { getGPUSummary } from '@/api/client'
import type { GPUSummary } from '@/types'

export function useGPU() {
  const gpuSummary = ref<GPUSummary | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const isRefreshing = ref(false)
  let refreshInterval: number | null = null

  const fetchGPUData = async (manualRefresh = false) => {
    if (manualRefresh) {
      isRefreshing.value = true
    } else {
      loading.value = true
    }
    error.value = null
    try {
      gpuSummary.value = await getGPUSummary()
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch GPU data'
      console.error('Failed to fetch GPU data:', err)
    } finally {
      loading.value = false
      isRefreshing.value = false
    }
  }

  const refresh = () => {
    fetchGPUData(true)
  }

  const startAutoRefresh = () => {
    if (refreshInterval) return
    refreshInterval = window.setInterval(fetchGPUData, 3000)
  }

  const stopAutoRefresh = () => {
    if (refreshInterval) {
      clearInterval(refreshInterval)
      refreshInterval = null
    }
  }

  const toggleAutoRefresh = () => {
    if (refreshInterval) {
      stopAutoRefresh()
    } else {
      startAutoRefresh()
    }
  }

  const isAutoRefreshEnabled = computed(() => refreshInterval !== null)

  const formatMemory = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
  }

  const formatTimestamp = (timestamp: string): string => {
    const date = new Date(timestamp)
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }

  const formatPercentage = (value: number): string => {
    return `${value.toFixed(1)}%`
  }

  const getMemoryPercentage = (used: number, total: number): number => {
    if (total === 0) return 0
    return (used / total) * 100
  }

  onMounted(() => {
    fetchGPUData()
    startAutoRefresh()
  })

  onUnmounted(() => {
    stopAutoRefresh()
  })

  return {
    gpuSummary,
    loading,
    error,
    isRefreshing,
    isAutoRefreshEnabled,
    fetchGPUData,
    refresh,
    startAutoRefresh,
    stopAutoRefresh,
    toggleAutoRefresh,
    formatMemory,
    formatTimestamp,
    formatPercentage,
    getMemoryPercentage,
  }
}
