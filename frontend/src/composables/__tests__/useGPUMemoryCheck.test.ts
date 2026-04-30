import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/api/client', () => ({
  getGPUMemoryCheck: vi.fn(),
  recommendModel: vi.fn(),
  checkModelMemory: vi.fn(),
}))

import * as apiClient from '@/api/client'
import { useGPUMemoryCheck } from '@/composables/useGPUMemoryCheck'

const getGPUMemoryCheck = vi.mocked(apiClient.getGPUMemoryCheck)
const recommendModel = vi.mocked(apiClient.recommendModel)
const checkModelMemory = vi.mocked(apiClient.checkModelMemory)

const memoryInfo = {
  available: true,
  total_gb: 80,
  used_gb: 40,
  free_gb: 40,
  safety_available_gb: 36,
  gpu_name: 'A100',
  method: 'nvidia_smi' as const,
}

const recommendation = {
  recommended: {
    name: 'qwen2',
    source: 'hf',
    size_b: 8 * 1024 * 1024 * 1024,
    quant: 'int4',
    required_gb: 8,
    feasible: true,
    model_id: 'qwen2',
    description: 'chat model',
  },
  gpu_info: { available: true, name: 'A100', total_gb: 80, used_gb: 40, free_gb: 40, safety_available_gb: 36 },
  candidates: [],
}

const checkResult = {
  feasible: true,
  available_gb: 40,
  required_gb: 8,
  safety_margin_gb: 32,
  gpu_available: true,
  gpu_name: 'A100',
}

describe('useGPUMemoryCheck', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetchMemoryInfo填充memoryInfo', async () => {
    getGPUMemoryCheck.mockResolvedValue(memoryInfo)

    const { fetchMemoryInfo, memoryInfo: infoRef, loading, error } = useGPUMemoryCheck()
    await fetchMemoryInfo()

    expect(infoRef.value).toEqual(memoryInfo)
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
  })

  it('fetchMemoryInfo失败清空memoryInfo并设置error', async () => {
    getGPUMemoryCheck.mockRejectedValue(new Error('无GPU'))

    const { fetchMemoryInfo, memoryInfo: infoRef, error } = useGPUMemoryCheck()
    await fetchMemoryInfo()

    expect(infoRef.value).toBeNull()
    expect(error.value).toBe('无GPU')
  })

  it('getRecommendation填充recommendation', async () => {
    recommendModel.mockResolvedValue(recommendation)

    const { getRecommendation, recommendation: recommendationRef } = useGPUMemoryCheck()
    await getRecommendation('chat')

    expect(recommendationRef.value).toEqual(recommendation)
  })

  it('checkModel双重输出(赋值ref+返回值)', async () => {
    checkModelMemory.mockResolvedValue(checkResult)

    const { checkModel, checkResult: checkRef } = useGPUMemoryCheck()
    const returned = await checkModel('qwen2-7b')

    expect(checkRef.value).toEqual(checkResult)
    expect(returned).toEqual(checkResult)
  })

  it('checkModel失败返回null并设置error', async () => {
    checkModelMemory.mockRejectedValue(new Error('显存不足'))

    const { checkModel, error } = useGPUMemoryCheck()
    const returned = await checkModel('huge-model')

    expect(returned).toBeNull()
    expect(error.value).toBe('显存不足')
  })
})
