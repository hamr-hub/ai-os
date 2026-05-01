import { computed, onMounted, onUnmounted } from 'vue'
import { useGPUStore } from '@/stores/gpu'
import { formatBytes, formatTimeLabel } from '@/utils/format'

export function useGPU() {
  const store = useGPUStore()

  const isRefreshing = computed(() => store.loading)
  const isAutoRefreshEnabled = computed(() => true)

  const formatMemory = (bytes: number): string => formatBytes(bytes)
  const formatTimestamp = (timestamp: string): string => formatTimeLabel(timestamp)
  const formatPercentage = (value: number): string => `${value.toFixed(1)}%`
  const getMemoryPercentage = (used: number, total: number): number => {
    if (total === 0) return 0
    return (used / total) * 100
  }

  onMounted(() => {
    store.startPolling()
  })

  onUnmounted(() => {
    store.stopPolling()
  })

  return {
    gpuSummary: computed(() => store.gpuSummary),
    loading: computed(() => store.loading),
    error: computed(() => store.error),
    isRefreshing,
    isAutoRefreshEnabled,
    refresh: store.refresh,
    startPolling: store.startPolling,
    stopPolling: store.stopPolling,
    toggleAutoRefresh: () => {},
    formatMemory,
    formatTimestamp,
    formatPercentage,
    getMemoryPercentage,
  }
}
