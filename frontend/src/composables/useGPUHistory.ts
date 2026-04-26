import { ref, toValue, type MaybeRefOrGetter } from 'vue'
import { getGPUHistory } from '@/api/client'
import { usePolling } from '@/composables/usePolling'
import type { GPUHistoryEntry } from '@/types'

export function useGPUHistory(count: MaybeRefOrGetter<number> = 120, intervalMs = 10000) {
  const gpuHistory = ref<GPUHistoryEntry[]>([])

  const { loading, isRefreshing, error, refresh } = usePolling(async (signal) => {
    const res = await getGPUHistory(Number(toValue(count)), { signal })
    gpuHistory.value = res?.history ?? []
  }, intervalMs)

  return {
    gpuHistory,
    loading,
    isRefreshing,
    error,
    refresh,
  }
}
