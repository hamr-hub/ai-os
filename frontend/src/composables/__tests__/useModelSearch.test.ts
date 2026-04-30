import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/api/client', () => ({
  searchModels: vi.fn(),
  recommendModel: vi.fn(),
  checkModelMemory: vi.fn(),
}))

import { searchModels, recommendModel, checkModelMemory } from '@/api/client'
import { useModelSearch } from '@/composables/useModelSearch'

describe('useModelSearch', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('search解构data.results填充results', async () => {
    const searchResults = [{ name: 'qwen2', source: 'hf' }, { name: 'llama', source: 'hf' }]
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
    const rec = { recommended: { name: 'qwen2' }, candidates: [] }
    recommendModel.mockResolvedValue(rec)

    const { recommend, recommendResult } = useModelSearch()
    await recommend('chat', 'hf')

    expect(recommendResult.value).toEqual(rec)
  })

  it('checkMemory返回结果但不存储到状态', async () => {
    const memResult = { can_load: true, required_memory: 8 }
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
