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
    const queue = { active_requests: 5, queued_requests: 2 }
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
    const config = { max_requests: 100, max_tokens: 5000 }
    getRateLimitConfig.mockResolvedValue(config)

    const { fetchConfig, rateLimitConfig } = useRateLimit()
    await fetchConfig()

    expect(rateLimitConfig.value).toEqual(config)
  })

  it('fetchStats填充rateLimitStats', async () => {
    const stats = { total_requests: 500, rejected: 10 }
    getRateLimitStats.mockResolvedValue(stats)

    const { fetchStats, rateLimitStats } = useRateLimit()
    await fetchStats()

    expect(rateLimitStats.value).toEqual(stats)
  })

  it('doUpdateConfig成功时更新rateLimitConfig并返回true', async () => {
    const newConf = { max_requests: 200 }
    updateRateLimitConfig.mockResolvedValue(newConf)

    const { doUpdateConfig, rateLimitConfig, loading } = useRateLimit()
    const result = await doUpdateConfig(newConf)

    expect(result).toBe(true)
    expect(rateLimitConfig.value).toEqual(newConf)
    expect(loading.value).toBe(false)
  })

  it('doUpdateConfig失败返回false并设置error', async () => {
    updateRateLimitConfig.mockRejectedValue(new Error('参数无效'))

    const { doUpdateConfig, error } = useRateLimit()
    const result = await doUpdateConfig({ max_requests: -1 })

    expect(result).toBe(false)
    expect(error.value).toBe('参数无效')
  })
})
