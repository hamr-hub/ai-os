import { ref, type Ref } from 'vue'
import { getQueueStatus, getRateLimitConfig, updateRateLimitConfig, getRateLimitStats } from '@/api/client'
import type { QueueStatus, RateLimitConfig, RateLimitStats } from '@/types'

export function useRateLimit() {
  const queueStatus: Ref<QueueStatus | null> = ref(null)
  const rateLimitConfig: Ref<RateLimitConfig | null> = ref(null)
  const rateLimitStats: Ref<RateLimitStats | null> = ref(null)
  const loading = ref(false)
  const error: Ref<string | null> = ref(null)

  const fetchQueueStatus = async () => {
    loading.value = true
    error.value = null
    try {
      queueStatus.value = await getQueueStatus()
    } catch (e: unknown) {
      error.value = (e as Error).message || '获取排队状态失败'
      queueStatus.value = null
    } finally {
      loading.value = false
    }
  }

  const fetchConfig = async () => {
    loading.value = true
    error.value = null
    try {
      rateLimitConfig.value = await getRateLimitConfig()
    } catch (e: unknown) {
      error.value = (e as Error).message || '获取限流配置失败'
      rateLimitConfig.value = null
    } finally {
      loading.value = false
    }
  }

  const fetchStats = async () => {
    loading.value = true
    error.value = null
    try {
      rateLimitStats.value = await getRateLimitStats()
    } catch (e: unknown) {
      error.value = (e as Error).message || '获取限流统计失败'
      rateLimitStats.value = null
    } finally {
      loading.value = false
    }
  }

  const doUpdateConfig = async (newConfig: Partial<RateLimitConfig>) => {
    loading.value = true
    error.value = null
    try {
      rateLimitConfig.value = await updateRateLimitConfig(newConfig)
      return true
    } catch (e: unknown) {
      error.value = (e as Error).message || '更新限流配置失败'
      return false
    } finally {
      loading.value = false
    }
  }

  return {
    queueStatus,
    rateLimitConfig,
    rateLimitStats,
    loading,
    error,
    fetchQueueStatus,
    fetchConfig,
    fetchStats,
    doUpdateConfig,
  }
}
