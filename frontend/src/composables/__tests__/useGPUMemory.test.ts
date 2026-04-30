import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/api/client', () => ({
  getGPUSummary: vi.fn(),
  getGPUMemoryCheck: vi.fn(),
  recommendModel: vi.fn(),
  checkModelMemory: vi.fn(),
  getEngineStatus: vi.fn(),
  switchEngine: vi.fn(),
}))

import * as apiClient from '@/api/client'
import { useGPUMemory } from '@/composables/useGPUMemory'

const getGPUSummary = vi.mocked(apiClient.getGPUSummary)
const recommendModel = vi.mocked(apiClient.recommendModel)
const checkModelMemory = vi.mocked(apiClient.checkModelMemory)
const getEngineStatus = vi.mocked(apiClient.getEngineStatus)
const switchEngine = vi.mocked(apiClient.switchEngine)

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
    const rec = {
      recommended: { name: 'qwen2', source: 'hf', size_b: null, quant: null, required_gb: null, feasible: true, model_id: 'qwen2', description: null },
      gpu_info: { available: true, name: 'A100', total_gb: 80, used_gb: 40, free_gb: 40, safety_available_gb: 36 },
      candidates: [],
    }
    recommendModel.mockResolvedValue(rec)

    const { recommend, recommendResult } = useGPUMemory()
    await recommend('chat')

    expect(recommendResult.value).toEqual(rec)
  })

  it('checkMemory填充memoryCheckResult', async () => {
    const checkData = {
      feasible: true,
      available_gb: 40,
      required_gb: 8,
      safety_margin_gb: 32,
      gpu_available: true,
      gpu_name: 'A100',
    }
    checkModelMemory.mockResolvedValue(checkData)

    const { checkMemory, memoryCheckResult } = useGPUMemory()
    await checkMemory('qwen2-7b')

    expect(memoryCheckResult.value).toEqual(checkData)
  })

  it('doSwitchEngine成功后乐观更新current_engine', async () => {
    const engineData = {
      vllm: { running: true, pid: 123, port: 8000, model: 'llama', uptime: 10 },
      sglang: { running: false, pid: null, port: null, model: null, uptime: null },
      llama_cpp: { running: false, pid: null, port: null, model: null, uptime: null },
      current_engine: 'vllm' as const,
    }
    getEngineStatus.mockResolvedValue(engineData)
    switchEngine.mockResolvedValue({ status: 'ok' })

    const { getEngines, doSwitchEngine, engineStatus } = useGPUMemory()
    await getEngines()

    expect(engineStatus.value!.current_engine).toBe('vllm')

    await doSwitchEngine('sglang')

    expect(engineStatus.value!.current_engine).toBe('sglang')
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
