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

const poolEntry = {
  name: 'qwen2',
  source: 'hf',
  size_b: 8 * 1024 * 1024 * 1024,
  quant: 'int4',
  required_gb: 8,
  feasible: true,
  local_path: '/models/qwen2',
  engine_type: 'vllm',
  download_status: 'completed' as const,
  running_status: 'stopped' as const,
  port: null,
  config_key: 'qwen2',
}

const searchResult = {
  name: 'qwen2',
  source: 'hf',
  size_b: 8 * 1024 * 1024 * 1024,
  quant: 'int4',
  required_gb: 8,
  feasible: true,
  model_id: 'qwen2',
  description: 'chat model',
}

const downloadTask = {
  task_id: 'dl-1',
  model_name: 'qwen2',
  source: 'hf',
  status: 'downloading' as const,
  progress_pct: 10,
  speed_mbps: 20,
  eta_seconds: 100,
  downloaded_bytes: 100,
  total_bytes: 1000,
  local_path: null,
  error_message: null,
  allow_patterns: null,
  ignore_patterns: null,
}

describe('useModelPoolStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('fetchPool填充pool', async () => {
    const models = [poolEntry]
    getPoolList.mockResolvedValue({ models, total: 1, page: 1, page_size: 20 })

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
    const results = [searchResult]
    searchModels.mockResolvedValue({ results, total: 1 })

    const store = useModelPoolStore()
    await store.searchModelsAction('qwen')

    expect(store.searchResults).toEqual(results)
    expect(store.searchTotal).toBe(1)
    expect(store.searching).toBe(false)
  })

  it('getRecommendation合并recommended+candidates', async () => {
    const recommended = searchResult
    const candidates = [{ ...searchResult, name: 'llama', model_id: 'llama' }, recommended]
    recommendModel.mockResolvedValue({
      recommended,
      gpu_info: { available: true, name: 'A100', total_gb: 80, used_gb: 40, free_gb: 40, safety_available_gb: 36 },
      candidates,
    })

    const store = useModelPoolStore()
    await store.getRecommendation('chat')

    expect(store.searchResults[0]).toEqual(recommended)
    expect(store.searchResults.length).toBe(2)
  })

  it('startDownloadAction成功后connectWS', async () => {
    startDownload.mockResolvedValue(downloadTask)

    const store = useModelPoolStore()
    const result = await store.startDownloadAction('qwen2')

    expect(result).toEqual(downloadTask)
    expect(store.downloads[0]).toEqual(downloadTask)
    expect(onDownloadMessage).toHaveBeenCalled()
  })

  it('deleteFromPoolAction成功后filter移除', async () => {
    getPoolList.mockResolvedValue({
      models: [poolEntry, { ...poolEntry, name: 'llama', config_key: 'llama' }],
      total: 2,
      page: 1,
      page_size: 20,
    })
    deleteFromPool.mockResolvedValue({ deleted: true, model_key: 'qwen2' })

    const store = useModelPoolStore()
    await store.fetchPool()
    await store.deleteFromPoolAction('qwen2')

    expect(store.pool).toEqual([{ ...poolEntry, name: 'llama', config_key: 'llama' }])
  })
})
