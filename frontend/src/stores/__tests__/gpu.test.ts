import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    getGPUSummary: vi.fn(),
  }
})

import { getGPUSummary } from '@/api/client'
import { useGPUStore } from '@/stores/gpu'

describe('useGPUStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('refresh填充gpuSummary', async () => {
    const gpuData = { status: 'available', current: { name: 'A100', utilization: 80 }, history: [] }
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
    const gpuData = { status: 'available', current: { name: 'A100', utilization: 80 }, history: [] }
    getGPUSummary.mockResolvedValue(gpuData)

    const store = useGPUStore()
    store.startPolling()

    expect(getGPUSummary).toHaveBeenCalled()

    store.stopPolling()
  })

  it('gpuCurrent和gpuStatus computed正确', async () => {
    const gpuData = { status: 'available', current: { name: 'A100', utilization: 80 }, history: [] }
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
