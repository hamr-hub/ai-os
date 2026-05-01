import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useSystemData } from '@/composables/useSystemData'

const { mockGetSystemStatus, mockGetHealthAlert, mockGetSystemHistory } = vi.hoisted(() => ({
  mockGetSystemStatus: vi.fn().mockResolvedValue({
    cpu: { percent: 25, cores: 8, cores_physical: 4 },
    memory: { total_mb: 16384, available_mb: 8192, used_mb: 8192, percent: 50 },
    disk: { total_gb: 500, used_gb: 250, free_gb: 250, percent: 50 },
    queue: {
      model1: { active_requests: 2, concurrency_limit: 10, can_accept: true },
    },
    timestamp: '2026-04-23T00:00:00Z',
  }),
  mockGetHealthAlert: vi.fn().mockResolvedValue({
    should_alert: false,
    health_score: 85,
    status: 'healthy',
    alert_reasons: [],
    timestamp: '2026-04-23T00:00:00Z',
  }),
  mockGetSystemHistory: vi.fn().mockResolvedValue({
    history: [
      { cpu_percent: 20, memory_percent: 45, timestamp: '2026-04-23T00:00:00Z' },
      { cpu_percent: 25, memory_percent: 50, timestamp: '2026-04-23T00:01:00Z' },
    ],
    count: 2,
  }),
}))

vi.mock('@/api/client', () => ({
  getSystemStatus: mockGetSystemStatus,
  getHealthAlert: mockGetHealthAlert,
  getSystemHistory: mockGetSystemHistory,
}))

describe('useSystemData', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('初始状态为null', () => {
    const { systemStatus, queueStatus, healthAlert, loading } = useSystemData()
    expect(systemStatus.value).toBeNull()
    expect(queueStatus.value).toBeNull()
    expect(healthAlert.value).toBeNull()
    expect(loading.value).toBe(false)
  })

  it('fetch后填充数据', async () => {
    const { systemStatus, queueStatus, healthAlert, refresh } = useSystemData()
    await refresh()
    expect(systemStatus.value).toBeTruthy()
    expect(systemStatus.value!.cpu.percent).toBe(25)
    expect(queueStatus.value).toBeTruthy()
    expect(queueStatus.value!.model1.active_requests).toBe(2)
    expect(healthAlert.value).toBeTruthy()
    expect(healthAlert.value!.health_score).toBe(85)
  })

  it('refresh调用fetch', async () => {
    const { refresh, systemStatus } = useSystemData()
    await refresh()
    expect(systemStatus.value).toBeTruthy()
  })

  it('systemHistory填充数据', async () => {
    const { systemHistory, refresh } = useSystemData()
    await refresh()
    expect(systemHistory.value).toHaveLength(2)
    expect(systemHistory.value[0].cpu_percent).toBe(20)
  })
})
