import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/client', () => ({
  getPoolList: vi.fn(),
  loadFromPool: vi.fn(),
  deleteFromPool: vi.fn(),
  searchModels: vi.fn(),
  recommendModel: vi.fn(),
  startDownload: vi.fn(),
  cancelDownload: vi.fn(),
  listDownloads: vi.fn(),
}))

vi.mock('@/utils/downloadWebSocket', () => ({
  onDownloadMessage: vi.fn(() => vi.fn()),
}))

import * as apiClient from '@/api/client'
import { onDownloadMessage } from '@/utils/downloadWebSocket'
import { useModelPoolStore } from '@/stores/modelPool'

const getPoolList = vi.mocked(apiClient.getPoolList)
const deleteFromPool = vi.mocked(apiClient.deleteFromPool)
const startDownload = vi.mocked(apiClient.startDownload)
const searchModels = vi.mocked(apiClient.searchModels)
const recommendModel = vi.mocked(apiClient.recommendModel)

describe('useModelPoolStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('fetchPool填充pool', async () => {
    const models = [{ config_key: 'qwen2', model_name: 'qwen2' }]
    getPoolList.mockResolvedValue({ models, total: 1 })

    const store = useModelPoolStore()
    await store.fetchPool()

    expect(store.pool).toEqual(models)
    expect(store.loading).toBe(false)
  })

  it('fetchPool失败设置error', async () => {
    getPoolList.mockRejectedValue(new Error('不可用'))

    const store = useModelPoolStore()
    await store.fetchPool()

    expect(store.error).toBe('不可用')
  })

  it('searchModelsAction填充searchResults', async () => {
    const results = [{ name: 'qwen2' }]
    searchModels.mockResolvedValue({ results, total: 1 })

    const store = useModelPoolStore()
    await store.searchModelsAction('qwen')

    expect(store.searchResults).toEqual(results)
    expect(store.searchTotal).toBe(1)
    expect(store.searching).toBe(false)
  })

  it('getRecommendation合并recommended+candidates', async () => {
    const recommended = { name: 'qwen2' }
    const candidates = [{ name: 'llama' }, { name: 'qwen2' }]
    recommendModel.mockResolvedValue({ recommended, candidates })

    const store = useModelPoolStore()
    await store.getRecommendation('chat')

    expect(store.searchResults[0]).toEqual(recommended)
    expect(store.searchResults.length).toBe(2)
  })

  it('startDownloadAction成功后connectWS', async () => {
    const task = { task_id: 'dl-1', model_name: 'qwen2', status: 'downloading' }
    startDownload.mockResolvedValue(task)

    const store = useModelPoolStore()
    const result = await store.startDownloadAction('qwen2')

    expect(result).toEqual(task)
    expect(store.downloads[0]).toEqual(task)
    expect(onDownloadMessage).toHaveBeenCalled()
  })

  it('deleteFromPoolAction成功后filter移除', async () => {
    getPoolList.mockResolvedValue({
      models: [
        { config_key: 'qwen2', model_name: 'qwen2' },
        { config_key: 'llama', model_name: 'llama' },
      ],
      total: 2,
    })
    deleteFromPool.mockResolvedValue({})

    const store = useModelPoolStore()
    await store.fetchPool()
    await store.deleteFromPoolAction('qwen2')

    expect(store.pool).toEqual([{ config_key: 'llama', model_name: 'llama' }])
  })
})
