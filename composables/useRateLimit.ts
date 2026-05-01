import { ref, type Ref } from 'vue'
import { getQueueStatus, getRateLimitConfig, updateRateLimitConfig, getRateLimitStats } from '@/api/client'
import type { QueueStatus, RateLimitConfig, RateLimitStats } from '@/types'

interface RawRateLimitConfig {
  ip_qps_limit?: number
  ip_qps_window_seconds?: number
  max_requests?: number
  window_seconds?: number
  concurrency_limit?: number
  queue_timeout_seconds?: number
  whitelist_ips?: string[]
  rate_limited_paths?: string[]
}

interface RawRateLimitStats {
  total_rejected?: number
  recent_429_count?: number
  rejection_by_ip?: Record<string, number>
  rejection_by_path?: Record<string, number>
  current_queue_depth?: number
  total_requests?: number
  rate_limited_requests?: number
  timestamp?: string
}

const normalizeRateLimitConfig = (payload: unknown): RateLimitConfig => {
  const raw = (payload ?? {}) as RawRateLimitConfig
  return {
    ip_qps_limit: raw.ip_qps_limit ?? raw.max_requests ?? 0,
    ip_qps_window_seconds: raw.ip_qps_window_seconds ?? raw.window_seconds ?? 60,
    concurrency_limit: raw.concurrency_limit ?? 0,
    queue_timeout_seconds: raw.queue_timeout_seconds ?? 0,
    whitelist_ips: Array.isArray(raw.whitelist_ips) ? raw.whitelist_ips : [],
    rate_limited_paths: Array.isArray(raw.rate_limited_paths) ? raw.rate_limited_paths : [],
  }
}

const normalizeRateLimitStats = (payload: unknown): RateLimitStats => {
  const raw = (payload ?? {}) as RawRateLimitStats
  return {
    total_rejected: raw.total_rejected ?? raw.rate_limited_requests ?? 0,
    recent_429_count: raw.recent_429_count ?? raw.rate_limited_requests ?? 0,
    rejection_by_ip: raw.rejection_by_ip ?? {},
    rejection_by_path: raw.rejection_by_path ?? {},
    current_queue_depth: raw.current_queue_depth ?? 0,
    timestamp: raw.timestamp ?? new Date().toISOString(),
  }
}

const denormalizeRateLimitConfig = (payload: Partial<RateLimitConfig>) => ({
  max_requests: payload.ip_qps_limit,
  window_seconds: payload.ip_qps_window_seconds,
  concurrency_limit: payload.concurrency_limit,
  queue_timeout_seconds: payload.queue_timeout_seconds,
  whitelist_ips: payload.whitelist_ips,
  rate_limited_paths: payload.rate_limited_paths,
})

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
      const response = await getRateLimitConfig()
      rateLimitConfig.value = normalizeRateLimitConfig(response)
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
      const response = await getRateLimitStats()
      rateLimitStats.value = normalizeRateLimitStats(response)
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
      const response = await updateRateLimitConfig(denormalizeRateLimitConfig(newConfig))
      rateLimitConfig.value = normalizeRateLimitConfig(response)
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
