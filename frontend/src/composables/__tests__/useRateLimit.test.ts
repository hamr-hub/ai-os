import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/api/client', () => ({
  getQueueStatus: vi.fn(),
  getRateLimitConfig: vi.fn(),
  updateRateLimitConfig: vi.fn(),
  getRateLimitStats: vi.fn(),
}))

import * as apiClient from '@/api/client'
import { useRateLimit } from '@/composables/useRateLimit'

const getQueueStatus = vi.mocked(apiClient.getQueueStatus)
const getRateLimitConfig = vi.mocked(apiClient.getRateLimitConfig)
const updateRateLimitConfig = vi.mocked(apiClient.updateRateLimitConfig)
const getRateLimitStats = vi.mocked(apiClient.getRateLimitStats)

describe('useRateLimit', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetchQueueStatus填充queueStatus', async () => {
    const queue = {
      qwen2: { active_requests: 5, concurrency_limit: 10, can_accept: true },
    }
    getQueueStatus.mockResolvedValue(queue)

    const { fetchQueueStatus, queueStatus, loading, error } = useRateLimit()
    await fetchQueueStatus()

    expect(queueStatus.value).toEqual(queue)
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
  })

  it('fetchQueueStatus失败清空queueStatus', async () => {
    getQueueStatus.mockRejectedValue(new Error('超时'))

    const { fetchQueueStatus, queueStatus, error } = useRateLimit()
    await fetchQueueStatus()

    expect(queueStatus.value).toBeNull()
    expect(error.value).toBe('超时')
  })

  it('fetchConfig填充rateLimitConfig', async () => {
    const config = { ip_qps_limit: 100, ip_qps_window_seconds: 60, concurrency_limit: 10, queue_timeout_seconds: 30, whitelist_ips: [], rate_limited_paths: [] }
    getRateLimitConfig.mockResolvedValue(config)

    const { fetchConfig, rateLimitConfig } = useRateLimit()
    await fetchConfig()

    expect(rateLimitConfig.value).toEqual(config)
  })

  it('fetchStats填充rateLimitStats', async () => {
    const stats = { total_rejected: 10, recent_429_count: 5, rejection_by_ip: {}, rejection_by_path: {}, current_queue_depth: 0, timestamp: '2026-01-01' }
    getRateLimitStats.mockResolvedValue(stats)

    const { fetchStats, rateLimitStats } = useRateLimit()
    await fetchStats()

    expect(rateLimitStats.value).toEqual(stats)
  })

  it('doUpdateConfig成功时更新rateLimitConfig并返回true', async () => {
    const newConf = { ip_qps_limit: 200 }
    updateRateLimitConfig.mockResolvedValue({ ip_qps_limit: 200, ip_qps_window_seconds: 60, concurrency_limit: 10, queue_timeout_seconds: 30, whitelist_ips: [], rate_limited_paths: [] })

    const { doUpdateConfig, rateLimitConfig, loading } = useRateLimit()
    const result = await doUpdateConfig(newConf)

    expect(result).toBe(true)
    expect(rateLimitConfig.value?.ip_qps_limit).toBe(200)
    expect(loading.value).toBe(false)
  })

  it('doUpdateConfig失败返回false并设置error', async () => {
    updateRateLimitConfig.mockRejectedValue(new Error('参数无效'))

    const { doUpdateConfig, error } = useRateLimit()
    const result = await doUpdateConfig({ ip_qps_limit: -1 })

    expect(result).toBe(false)
    expect(error.value).toBe('参数无效')
  })
})
