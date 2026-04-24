import { ref, onMounted, onUnmounted, computed, type MaybeRefOrGetter, toValue } from 'vue'
import { getTokenStats, getTokenHistory } from '@/api/client'
import { formatTimeLabel } from '@/utils/format'
import type { TokenStats } from '@/types'

export function useTokenHistory(intervalMs = 30000, initialCount: MaybeRefOrGetter<number> = 60) {
  const tokenStats = ref<TokenStats | null>(null)
  const tokenHistory = ref<
    Array<{ timestamp: string; total: number; prompt: number; completion: number }>
  >([])
  const loading = ref(false)
  const isRefreshing = ref(false)
  const error = ref<string | null>(null)
  let timer: number | null = null

  const fetchTokenData = async (manualRefresh = false) => {
    if (manualRefresh) {
      isRefreshing.value = true
    } else {
      loading.value = true
    }

    error.value = null

    try {
      const [stats, historyData] = await Promise.all([
        getTokenStats(),
        getTokenHistory(toValue(initialCount)),
      ])

      tokenStats.value = stats

      // Convert server history format to internal format
      tokenHistory.value = historyData.history.map((entry: any) => ({
        timestamp: entry.timestamp,
        total: entry.total_tokens,
        prompt: entry.prompt_tokens,
        completion: entry.completion_tokens,
      }))
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Token统计获取失败'
    } finally {
      loading.value = false
      isRefreshing.value = false
    }
  }

  const refresh = () => fetchTokenData(true)

  const startPolling = () => {
    if (timer) return
    timer = window.setInterval(fetchTokenData, intervalMs)
  }

  const stopPolling = () => {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

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

  onMounted(() => {
    fetchTokenData()
    startPolling()
  })

  onUnmounted(() => {
    stopPolling()
  })

  return {
    tokenStats,
    tokenHistory,
    tokenTimeLabels,
    tokenTotalDataset,
    loading,
    isRefreshing,
    error,
    fetchTokenData,
    refresh,
    startPolling,
    stopPolling,
  }
}
