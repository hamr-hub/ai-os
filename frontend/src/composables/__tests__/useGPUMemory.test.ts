import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/api/client', () => ({
  getGPUSummary: vi.fn(),
  getGPUMemoryCheck: vi.fn(),
  recommendModel: vi.fn(),
  checkModelMemory: vi.fn(),
  getEngineStatus: vi.fn(),
  switchEngine: vi.fn(),
}))

import { getGPUSummary, recommendModel, checkModelMemory, getEngineStatus, switchEngine } from '@/api/client'
import { useGPUMemory } from '@/composables/useGPUMemory'

describe('useGPUMemory', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('getGPU填充gpuInfo', async () => {
    const gpuData = { status: 'available', current: { name: 'A100', utilization: 80 }, history: [] }
    getGPUSummary.mockResolvedValue(gpuData)

    const { getGPU, gpuInfo, loading, error } = useGPUMemory()
    await getGPU()

    expect(gpuInfo.value).toEqual(gpuData)
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
  })

  it('getGPU失败清空gpuInfo', async () => {
    getGPUSummary.mockRejectedValue(new Error('GPU离线'))

    const { getGPU, gpuInfo, error } = useGPUMemory()
    await getGPU()

    expect(gpuInfo.value).toBeNull()
    expect(error.value).toBe('GPU离线')
  })

  it('recommend填充recommendResult', async () => {
    const rec = { recommended: { name: 'qwen2' }, candidates: [] }
    recommendModel.mockResolvedValue(rec)

    const { recommend, recommendResult } = useGPUMemory()
    await recommend('chat')

    expect(recommendResult.value).toEqual(rec)
  })

  it('checkMemory填充memoryCheckResult', async () => {
    const checkData = { can_load: true, required_memory: 8 }
    checkModelMemory.mockResolvedValue(checkData)

    const { checkMemory, memoryCheckResult } = useGPUMemory()
    await checkMemory('qwen2-7b')

    expect(memoryCheckResult.value).toEqual(checkData)
  })

  it('doSwitchEngine成功后乐观更新current_engine', async () => {
    const engineData = { current_engine: 'vllm', available_engines: ['vllm', 'trt'] }
    getEngineStatus.mockResolvedValue(engineData)
    switchEngine.mockResolvedValue({ switched: true })

    const { getEngines, doSwitchEngine, engineStatus } = useGPUMemory()
    await getEngines()

    expect(engineStatus.value!.current_engine).toBe('vllm')

    await doSwitchEngine('trt')

    expect(engineStatus.value!.current_engine).toBe('trt')
  })

  it('doSwitchEngine失败设置error', async () => {
    switchEngine.mockRejectedValue(new Error('引擎忙'))

    const { doSwitchEngine, error, switchingEngine } = useGPUMemory()
    const result = await doSwitchEngine('vllm')

    expect(result).toBeNull()
    expect(error.value).toBe('引擎忙')
    expect(switchingEngine.value).toBe(false)
  })
})
