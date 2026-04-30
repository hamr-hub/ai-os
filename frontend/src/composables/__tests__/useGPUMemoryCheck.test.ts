import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/api/client', () => ({
  getGPUMemoryCheck: vi.fn(),
  recommendModel: vi.fn(),
  checkModelMemory: vi.fn(),
}))

import { getGPUMemoryCheck, recommendModel, checkModelMemory } from '@/api/client'
import { useGPUMemoryCheck } from '@/composables/useGPUMemoryCheck'

describe('useGPUMemoryCheck', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetchMemoryInfo填充memoryInfo', async () => {
    const info = { total_memory: 80, used_memory: 40, available_memory: 40 }
    getGPUMemoryCheck.mockResolvedValue(info)

    const { fetchMemoryInfo, memoryInfo, loading, error } = useGPUMemoryCheck()
    await fetchMemoryInfo()

    expect(memoryInfo.value).toEqual(info)
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
  })

  it('fetchMemoryInfo失败清空memoryInfo并设置error', async () => {
    getGPUMemoryCheck.mockRejectedValue(new Error('无GPU'))

    const { fetchMemoryInfo, memoryInfo, error } = useGPUMemoryCheck()
    await fetchMemoryInfo()

    expect(memoryInfo.value).toBeNull()
    expect(error.value).toBe('无GPU')
  })

  it('getRecommendation填充recommendation', async () => {
    const rec = { recommended: { name: 'qwen2' }, candidates: [] }
    recommendModel.mockResolvedValue(rec)

    const { getRecommendation, recommendation } = useGPUMemoryCheck()
    await getRecommendation('chat')

    expect(recommendation.value).toEqual(rec)
  })

  it('checkModel双重输出(赋值ref+返回值)', async () => {
    const checkResult = { can_load: true, required_memory: 8 }
    checkModelMemory.mockResolvedValue(checkResult)

    const { checkModel, checkResult: checkRef } = useGPUMemoryCheck()
    const returned = await checkModel('qwen2-7b')

    expect(checkRef.value).toEqual(checkResult)
    expect(returned).toEqual(checkResult)
  })

  it('checkModel失败返回null并设置error', async () => {
    checkModelMemory.mockRejectedValue(new Error('显存不足'))

    const { checkModel, error, checkResult: checkRef } = useGPUMemoryCheck()
    const returned = await checkModel('huge-model')

    expect(returned).toBeNull()
    expect(error.value).toBe('显存不足')
  })
})
