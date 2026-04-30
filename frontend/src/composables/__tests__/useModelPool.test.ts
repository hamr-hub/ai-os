import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/api/client', () => ({
  getPoolList: vi.fn(),
  getPoolDetail: vi.fn(),
  loadFromPool: vi.fn(),
  deleteFromPool: vi.fn(),
}))

import * as apiClient from '@/api/client'
import { useModelPool } from '@/composables/useModelPool'

const getPoolList = vi.mocked(apiClient.getPoolList)
const getPoolDetail = vi.mocked(apiClient.getPoolDetail)
const loadFromPool = vi.mocked(apiClient.loadFromPool)
const deleteFromPool = vi.mocked(apiClient.deleteFromPool)

describe('useModelPool', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('list解构{models,total}填充poolList和total', async () => {
    const models = [
      { config_key: 'qwen2-7b', model_name: 'qwen2-7b' },
      { config_key: 'llama-8b', model_name: 'llama-8b' },
    ]
    getPoolList.mockResolvedValue({ models, total: 2 })

    const { list, poolList, total, loading, error } = useModelPool()
    await list()

    expect(poolList.value).toEqual(models)
    expect(total.value).toBe(2)
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
  })

  it('list失败清空poolList并设置error', async () => {
    getPoolList.mockRejectedValue(new Error('服务不可用'))

    const { list, poolList, error } = useModelPool()
    await list()

    expect(poolList.value).toEqual([])
    expect(error.value).toBe('服务不可用')
  })

  it('detail填充currentDetail', async () => {
    const entry = { config_key: 'qwen2-7b', model_name: 'qwen2-7b', size_gb: 14 }
    getPoolDetail.mockResolvedValue(entry)

    const { detail, currentDetail } = useModelPool()
    await detail('qwen2-7b')

    expect(currentDetail.value).toEqual(entry)
  })

  it('load返回结果', async () => {
    const result = { loaded: true }
    loadFromPool.mockResolvedValue(result)

    const { load } = useModelPool()
    const resp = await load('qwen2-7b', 'vllm')

    expect(loadFromPool).toHaveBeenCalledWith('qwen2-7b', 'vllm')
    expect(resp).toEqual(result)
  })

  it('remove成功后从poolList中filter移除', async () => {
    const models = [
      { config_key: 'qwen2-7b', model_name: 'qwen2-7b' },
      { config_key: 'llama-8b', model_name: 'llama-8b' },
    ]
    getPoolList.mockResolvedValue({ models, total: 2 })
    deleteFromPool.mockResolvedValue({ deleted: true })

    const { list, remove, poolList, total } = useModelPool()
    await list()
    await remove('qwen2-7b')

    expect(poolList.value).toEqual([{ config_key: 'llama-8b', model_name: 'llama-8b' }])
    expect(total.value).toBe(1)
  })

  it('remove失败设置error', async () => {
    deleteFromPool.mockRejectedValue(new Error('文件占用'))

    const { remove, error } = useModelPool()
    await remove('busy-model')

    expect(error.value).toBe('文件占用')
  })
})
