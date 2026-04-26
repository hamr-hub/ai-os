import { ref, computed } from 'vue'
import { getGPUSummary } from '@/api/client'
import { formatBytes, formatTimeLabel } from '@/utils/format'
import { usePolling } from '@/composables/usePolling'
import type { GPUSummary } from '@/types'

export function useGPU() {
  const gpuSummary = ref<GPUSummary | null>(null)

  const { loading, isRefreshing, error, refresh, startPolling, stopPolling } = usePolling(
    async () => {
      gpuSummary.value = await getGPUSummary()
    },
    30000
  )

  const isAutoRefreshEnabled = computed(() => true)

  const formatMemory = (bytes: number): string => formatBytes(bytes)

  const formatTimestamp = (timestamp: string): string => formatTimeLabel(timestamp)

  const formatPercentage = (value: number): string => {
    return `${value.toFixed(1)}%`
  }

  const getMemoryPercentage = (used: number, total: number): number => {
    if (total === 0) return 0
    return (used / total) * 100
  }

  return {
    gpuSummary,
    loading,
    error,
    isRefreshing,
    isAutoRefreshEnabled,
    refresh,
    startPolling,
    stopPolling,
    toggleAutoRefresh: () => {},
    formatMemory,
    formatTimestamp,
    formatPercentage,
    getMemoryPercentage,
  }
}
