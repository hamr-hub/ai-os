import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useGPU } from '@/composables/useGPU'

vi.mock('@/api/client', () => ({
  getGPUSummary: vi.fn().mockResolvedValue({
    status: 'available',
    current: {
      name: 'NVIDIA RTX 4090',
      gpu_count: 1,
      utilization: 45,
      temperature: 65,
      power_draw: 250,
      power_limit: 450,
      power_percent: 55,
      memory_utilization: 60,
      used_memory: 12884901888,
      available_memory: 8589934592,
      total_memory: 21474836480,
    },
    history: [],
  }),
}))

describe('useGPU', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
  })

  it('初始状态gpuSummary为null', () => {
    const { gpuSummary, loading } = useGPU()
    expect(gpuSummary.value).toBeNull()
    expect(loading.value).toBe(false)
  })

  it('refresh后填充数据', async () => {
    const { gpuSummary, refresh } = useGPU()
    await refresh()
    expect(gpuSummary.value).toBeTruthy()
    expect(gpuSummary.value!.status).toBe('available')
    expect(gpuSummary.value!.current!.name).toBe('NVIDIA RTX 4090')
  })

  it('formatMemory格式化字节', () => {
    const { formatMemory } = useGPU()
    expect(formatMemory(21474836480)).toBe('20.0 GB')
    expect(formatMemory(1048576)).toBe('1.0 MB')
    expect(formatMemory(1024)).toBe('1.0 KB')
    expect(formatMemory(500)).toBe('500 B')
  })

  it('formatPercentage格式化百分比', () => {
    const { formatPercentage } = useGPU()
    expect(formatPercentage(45.6)).toBe('45.6%')
  })

  it('getMemoryPercentage计算百分比', () => {
    const { getMemoryPercentage } = useGPU()
    expect(getMemoryPercentage(12884901888, 21474836480)).toBeCloseTo(60, 1)
    expect(getMemoryPercentage(0, 0)).toBe(0)
  })
})
