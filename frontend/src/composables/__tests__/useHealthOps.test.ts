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

describe('useHealthOps', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetchAlert填充healthAlert', async () => {
    const alert = { status: 'warning', message: 'GPU温度高' }
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
    const detail = { gpu_health: 'ok', services: [] }
    getHealthDetailed.mockResolvedValue(detail)

    const { fetchDetail, healthDetail } = useHealthOps()
    await fetchDetail()

    expect(healthDetail.value).toEqual(detail)
  })

  it('fetchHistory填充healthHistory', async () => {
    const history = [{ timestamp: '2026-01-01', event: 'check' }]
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
    healthCheck.mockResolvedValue({})
    getHealthAlert.mockResolvedValue({ status: 'healthy' })
    getHealthDetailed.mockResolvedValue({ gpu_health: 'ok' })

    const { runCheck, healthAlert, healthDetail, loading, error } = useHealthOps()
    await runCheck()

    expect(healthCheck).toHaveBeenCalledOnce()
    expect(getHealthAlert).toHaveBeenCalledOnce()
    expect(getHealthDetailed).toHaveBeenCalledOnce()
    expect(healthAlert.value).toEqual({ status: 'healthy' })
    expect(healthDetail.value).toEqual({ gpu_health: 'ok' })
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
