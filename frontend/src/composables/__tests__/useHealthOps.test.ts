import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/api/client', () => ({
  getHealthAlert: vi.fn(),
  healthCheck: vi.fn(),
  getHealthDetailed: vi.fn(),
  getHealthHistory: vi.fn(),
}))

import * as apiClient from '@/api/client'
import { useHealthOps } from '@/composables/useHealthOps'

const getHealthAlert = vi.mocked(apiClient.getHealthAlert)
const healthCheck = vi.mocked(apiClient.healthCheck)
const getHealthDetailed = vi.mocked(apiClient.getHealthDetailed)
const getHealthHistory = vi.mocked(apiClient.getHealthHistory)

const alert = {
  should_alert: true,
  health_score: 72,
  status: 'warning' as const,
  alert_reasons: ['GPU温度高'],
  timestamp: '2026-01-01T00:00:00Z',
}

const detail = {
  overall_score: 88,
  status: 'healthy' as const,
  checks: {
    gpu: { available: true, utilization: 52, temperature: 68, memory_used_pct: 42 },
    go_backend: { reachable: true, response_time_ms: 10 },
    python_backend: { reachable: true, response_time_ms: 12 },
    vllm_service: { running: true, active_requests: 1 },
    redis: { available: true, connected: true },
  },
  alert_reasons: [],
  timestamp: '2026-01-01T00:00:00Z',
}

const history = [
  { timestamp: '2026-01-01T00:00:00Z', health_score: 90, status: 'healthy', alert_count: 0 },
]

describe('useHealthOps', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetchAlert填充healthAlert', async () => {
    getHealthAlert.mockResolvedValue(alert)

    const { fetchAlert, healthAlert, loading, error } = useHealthOps()
    await fetchAlert()

    expect(healthAlert.value).toEqual(alert)
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
  })

  it('fetchAlert失败清空healthAlert并设置error', async () => {
    getHealthAlert.mockRejectedValue(new Error('超时'))

    const { fetchAlert, healthAlert, error } = useHealthOps()
    await fetchAlert()

    expect(healthAlert.value).toBeNull()
    expect(error.value).toBe('超时')
  })

  it('fetchDetail填充healthDetail', async () => {
    getHealthDetailed.mockResolvedValue(detail)

    const { fetchDetail, healthDetail } = useHealthOps()
    await fetchDetail()

    expect(healthDetail.value).toEqual(detail)
  })

  it('fetchHistory填充healthHistory', async () => {
    getHealthHistory.mockResolvedValue(history)

    const { fetchHistory, healthHistory } = useHealthOps()
    await fetchHistory()

    expect(healthHistory.value).toEqual(history)
  })

  it('fetchHistory失败清空healthHistory', async () => {
    getHealthHistory.mockRejectedValue(new Error('无数据'))

    const { fetchHistory, healthHistory, error } = useHealthOps()
    await fetchHistory()

    expect(healthHistory.value).toEqual([])
    expect(error.value).toBe('无数据')
  })

  it('runCheck先调healthCheck再刷新alert+detail', async () => {
    healthCheck.mockResolvedValue({ status: 'ok' })
    getHealthAlert.mockResolvedValue({ ...alert, status: 'healthy', should_alert: false, alert_reasons: [] })
    getHealthDetailed.mockResolvedValue(detail)

    const { runCheck, healthAlert, healthDetail, loading, error } = useHealthOps()
    await runCheck()

    expect(healthCheck).toHaveBeenCalledOnce()
    expect(getHealthAlert).toHaveBeenCalledOnce()
    expect(getHealthDetailed).toHaveBeenCalledOnce()
    expect(healthAlert.value?.status).toBe('healthy')
    expect(healthDetail.value).toEqual(detail)
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
  })

  it('runCheck失败时设置error', async () => {
    healthCheck.mockRejectedValue(new Error('服务不可用'))

    const { runCheck, error } = useHealthOps()
    await runCheck()

    expect(error.value).toBe('服务不可用')
  })
})
