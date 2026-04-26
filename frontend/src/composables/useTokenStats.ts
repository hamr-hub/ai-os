import { ref, computed } from 'vue'
import { getTokenStats } from '@/api/client'
import { usePolling } from '@/composables/usePolling'
import { formatTokens } from '@/utils/format'
import type { TokenStats } from '@/types'

export function useTokenStats(intervalMs = 10000) {
  const stats = ref<TokenStats | null>(null)

  const { loading, isRefreshing, error, refresh } = usePolling(
    async () => {
      stats.value = await getTokenStats()
    },
    intervalMs
  )

  const totalTokens = computed(() => stats.value?.total_tokens ?? 0)
  const promptTokens = computed(
    () => stats.value?.total_prompt_tokens ?? stats.value?.prompt_tokens ?? 0
  )
  const completionTokens = computed(
    () => stats.value?.total_completion_tokens ?? stats.value?.completion_tokens ?? 0
  )
  const modelStats = computed(() => stats.value?.models ?? {})

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
    refresh,
  }
}
