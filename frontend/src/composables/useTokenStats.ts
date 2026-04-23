import { ref, onMounted, onUnmounted, computed } from 'vue'
import { getTokenStats } from '@/api/client'
import type { TokenStats } from '@/types'

export function useTokenStats(intervalMs = 10000) {
  const stats = ref<TokenStats | null>(null)
  const loading = ref(false)
  const isRefreshing = ref(false)
  const error = ref<string | null>(null)
  let timer: number | null = null

  const fetch = async (manualRefresh = false) => {
    if (manualRefresh) {
      isRefreshing.value = true
    } else {
      loading.value = true
    }
    error.value = null
    try {
      stats.value = await getTokenStats()
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch token stats'
    } finally {
      loading.value = false
      isRefreshing.value = false
    }
  }

  const refresh = () => {
    fetch(true)
  }

  const startPolling = () => {
    if (timer) return
    timer = window.setInterval(fetch, intervalMs)
  }

  const stopPolling = () => {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  const totalTokens = computed(() => stats.value?.total_tokens ?? 0)
  const promptTokens = computed(() => stats.value?.total_prompt_tokens ?? 0)
  const completionTokens = computed(() => stats.value?.total_completion_tokens ?? 0)
  const modelStats = computed(() => stats.value?.models ?? {})

  const formatTokens = (n: number): string => {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
    return `${n}`
  }

  onMounted(() => {
    fetch()
    startPolling()
  })

  onUnmounted(() => {
    stopPolling()
  })

  return {
    stats,
    loading,
    isRefreshing,
    error,
    totalTokens,
    promptTokens,
    completionTokens,
    modelStats,
    formatTokens,
    fetch,
    refresh,
    startPolling,
    stopPolling,
  }
}
