import { ref, computed, toValue, type MaybeRefOrGetter } from 'vue'
import { getTokenStats, getTokenHistory } from '@/api/client'
import { usePolling } from '@/composables/usePolling'
import { formatTimeLabel } from '@/utils/format'
import type { TokenStats } from '@/types'

export function useTokenHistory(intervalMs = 30000, initialCount: MaybeRefOrGetter<number> = 60) {
  const tokenStats = ref<TokenStats | null>(null)
  const tokenHistory = ref<
    Array<{ timestamp: string; total: number; prompt: number; completion: number }>
  >([])

  const { loading, isRefreshing, error, refresh } = usePolling(
    async (signal) => {
      const [stats, historyData] = await Promise.all([
        getTokenStats({ signal }),
        getTokenHistory(toValue(initialCount), { signal }),
      ])

      tokenStats.value = stats

      tokenHistory.value = historyData.history.map((entry: any) => ({
        timestamp: entry.timestamp,
        total: entry.total_tokens,
        prompt: entry.prompt_tokens,
        completion: entry.completion_tokens,
      }))
    },
    intervalMs
  )

  const tokenTimeLabels = computed(() =>
    tokenHistory.value.map((entry) => formatTimeLabel(entry.timestamp))
  )
  const tokenTotalDataset = computed(() => [
    {
      label: 'Total Tokens',
      data: tokenHistory.value.map((entry) => entry.total),
      borderColor: '#8b5cf6',
      backgroundColor: 'rgba(139, 92, 246, 0.08)',
      fill: true,
      tension: 0.4,
      pointRadius: 0,
      borderWidth: 2,
    },
    {
      label: 'Prompt Tokens',
      data: tokenHistory.value.map((entry) => entry.prompt),
      borderColor: '#3b82f6',
      backgroundColor: 'rgba(59, 130, 246, 0.05)',
      fill: false,
      tension: 0.4,
      pointRadius: 0,
      borderWidth: 1.5,
    },
    {
      label: 'Completion Tokens',
      data: tokenHistory.value.map((entry) => entry.completion),
      borderColor: '#22c55e',
      backgroundColor: 'rgba(34, 197, 94, 0.05)',
      fill: false,
      tension: 0.4,
      pointRadius: 0,
      borderWidth: 1.5,
    },
  ])

  return {
    tokenStats,
    tokenHistory,
    tokenTimeLabels,
    tokenTotalDataset,
    loading,
    isRefreshing,
    error,
    refresh,
  }
}
