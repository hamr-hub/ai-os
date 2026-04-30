import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/api/client', () => ({
  searchModels: vi.fn(),
  recommendModel: vi.fn(),
  checkModelMemory: vi.fn(),
}))

import * as apiClient from '@/api/client'
import { useModelSearch } from '@/composables/useModelSearch'

const searchModels = vi.mocked(apiClient.searchModels)
const recommendModel = vi.mocked(apiClient.recommendModel)
const checkModelMemory = vi.mocked(apiClient.checkModelMemory)

const searchResults = [
  {
    name: 'qwen2',
    source: 'hf',
    size_b: 8 * 1024 * 1024 * 1024,
    quant: 'int4',
    required_gb: 8,
    feasible: true,
    model_id: 'qwen2',
    description: 'chat model',
  },
  {
    name: 'llama',
    source: 'hf',
    size_b: 10 * 1024 * 1024 * 1024,
    quant: 'fp16',
    required_gb: 12,
    feasible: false,
    model_id: 'llama',
    description: 'llama model',
  },
]

const recommendResult = {
  recommended: searchResults[0],
  gpu_info: { available: true, name: 'A100', total_gb: 80, used_gb: 40, free_gb: 40, safety_available_gb: 36 },
  candidates: searchResults,
}

const memResult = {
  feasible: true,
  available_gb: 40,
  required_gb: 8,
  safety_margin_gb: 32,
  gpu_available: true,
  gpu_name: 'A100',
}

describe('useModelSearch', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('search解构data.results填充results', async () => {
    searchModels.mockResolvedValue({ results: searchResults, total: 2 })

    const { search, results, loading, error } = useModelSearch()
    await search('qwen')

    expect(results.value).toEqual(searchResults)
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
  })

  it('search失败清空results并设置error', async () => {
    searchModels.mockRejectedValue(new Error('搜索超时'))

    const { search, results, error } = useModelSearch()
    await search('fail')

    expect(results.value).toEqual([])
    expect(error.value).toBe('搜索超时')
  })

  it('recommend填充recommendResult', async () => {
    recommendModel.mockResolvedValue(recommendResult)

    const { recommend, recommendResult: resultRef } = useModelSearch()
    await recommend('chat', 'hf')

    expect(resultRef.value).toEqual(recommendResult)
  })

  it('checkMemory返回结果但不存储到状态', async () => {
    checkModelMemory.mockResolvedValue(memResult)

    const { checkMemory, loading, error } = useModelSearch()
    const result = await checkMemory('qwen2-7b')

    expect(result).toEqual(memResult)
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
  })

  it('checkMemory失败返回null并设置error', async () => {
    checkModelMemory.mockRejectedValue(new Error('显存不足'))

    const { checkMemory, error } = useModelSearch()
    const result = await checkMemory('huge-model')

    expect(result).toBeNull()
    expect(error.value).toBe('显存不足')
  })
})
