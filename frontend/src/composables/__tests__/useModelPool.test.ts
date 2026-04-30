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

const poolEntry = {
  name: 'qwen2-7b',
  source: 'hf',
  size_b: 14 * 1024 * 1024 * 1024,
  quant: 'int4',
  required_gb: 14,
  feasible: true,
  local_path: '/models/qwen2-7b',
  engine_type: 'vllm',
  download_status: 'completed' as const,
  running_status: 'stopped' as const,
  port: null,
  config_key: 'qwen2-7b',
}

describe('useModelPool', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('list解构{models,total}填充poolList和total', async () => {
    const models = [poolEntry, { ...poolEntry, name: 'llama-8b', config_key: 'llama-8b' }]
    getPoolList.mockResolvedValue({ models, total: 2, page: 1, page_size: 20 })

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
    getPoolDetail.mockResolvedValue(poolEntry)

    const { detail, currentDetail } = useModelPool()
    await detail('qwen2-7b')

    expect(currentDetail.value).toEqual(poolEntry)
  })

  it('load返回结果', async () => {
    const result = { success: true, model: 'qwen2-7b', engine: 'vllm', port: 8000 }
    loadFromPool.mockResolvedValue(result)

    const { load } = useModelPool()
    const resp = await load('qwen2-7b', 'vllm')

    expect(loadFromPool).toHaveBeenCalledWith('qwen2-7b', 'vllm')
    expect(resp).toEqual(result)
  })

  it('remove成功后从poolList中filter移除', async () => {
    const models = [poolEntry, { ...poolEntry, name: 'llama-8b', config_key: 'llama-8b' }]
    getPoolList.mockResolvedValue({ models, total: 2, page: 1, page_size: 20 })
    deleteFromPool.mockResolvedValue({ deleted: true, model_key: 'qwen2-7b' })

    const { list, remove, poolList, total } = useModelPool()
    await list()
    await remove('qwen2-7b')

    expect(poolList.value).toEqual([{ ...poolEntry, name: 'llama-8b', config_key: 'llama-8b' }])
    expect(total.value).toBe(1)
  })

  it('remove失败设置error', async () => {
    deleteFromPool.mockRejectedValue(new Error('文件占用'))

    const { remove, error } = useModelPool()
    await remove('busy-model')

    expect(error.value).toBe('文件占用')
  })
})
