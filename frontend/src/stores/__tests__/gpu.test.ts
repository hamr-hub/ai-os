import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    getGPUSummary: vi.fn(),
  }
})

import * as apiClient from '@/api/client'
import { useGPUStore } from '@/stores/gpu'

const getGPUSummary = vi.mocked(apiClient.getGPUSummary)

const gpuData = {
  status: 'available' as const,
  current: {
    name: 'A100',
    gpu_count: 1,
    utilization: 80,
    temperature: 65,
    power_draw: 220,
    power_limit: 300,
    power_percent: 73,
    memory_utilization: 50,
    used_memory: 40,
    available_memory: 40,
    total_memory: 80,
  },
  history: [],
}

describe('useGPUStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('refresh填充gpuSummary', async () => {
    getGPUSummary.mockResolvedValue(gpuData)

    const store = useGPUStore()
    await store.refresh()

    expect(store.gpuSummary).toEqual(gpuData)
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })

  it('refresh失败设置error', async () => {
    getGPUSummary.mockRejectedValue(new Error('GPU离线'))

    const store = useGPUStore()
    await store.refresh()

    expect(store.error).toBe('GPU离线')
    expect(store.loading).toBe(false)
  })

  it('AbortError不写入error', async () => {
    const abortErr = new DOMException('Aborted', 'AbortError')
    getGPUSummary.mockRejectedValue(abortErr)

    const store = useGPUStore()
    await store.refresh()

    expect(store.error).toBeNull()
  })

  it('subscriberCount控制轮询启停', async () => {
    getGPUSummary.mockResolvedValue(gpuData)

    const store = useGPUStore()
    store.startPolling()

    expect(getGPUSummary).toHaveBeenCalled()

    store.stopPolling()
  })

  it('gpuCurrent和gpuStatus computed正确', async () => {
    getGPUSummary.mockResolvedValue(gpuData)

    const store = useGPUStore()
    await store.refresh()

    expect(store.gpuCurrent).toEqual(gpuData.current)
    expect(store.gpuStatus).toBe('available')
  })

  it('gpuCurrent为null当gpuSummary无数据', () => {
    const store = useGPUStore()
    expect(store.gpuCurrent).toBeNull()
    expect(store.gpuStatus).toBe('unavailable')
  })
})
