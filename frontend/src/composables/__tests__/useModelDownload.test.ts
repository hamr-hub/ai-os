import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/client', () => ({
  startDownload: vi.fn(),
  getDownloadStatus: vi.fn(),
  cancelDownload: vi.fn(),
  listDownloads: vi.fn(),
}))

vi.mock('@/stores/server', () => ({
  useServerStore: vi.fn(() => ({
    activeUrl: 'http://localhost:3000',
  })),
}))

vi.stubGlobal('WebSocket', class MockWS {
  send = vi.fn()
  close = vi.fn()
  readyState = 1
  onopen: (() => void) | null = null
  onmessage: ((ev: { data: string }) => void) | null = null
  onclose: (() => void) | null = null
  onerror: (() => void) | null = null
  addEventListener = vi.fn()
  removeEventListener = vi.fn()
})

import * as apiClient from '@/api/client'
import { useModelDownload } from '@/composables/useModelDownload'

const startDownload = vi.mocked(apiClient.startDownload)
const getDownloadStatus = vi.mocked(apiClient.getDownloadStatus)
const cancelDownload = vi.mocked(apiClient.cancelDownload)
const listDownloads = vi.mocked(apiClient.listDownloads)

describe('useModelDownload', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('start成功创建下载任务', async () => {
    const task = { task_id: 'dl-1', model_name: 'qwen2', status: 'downloading' }
    startDownload.mockResolvedValue(task)

    const { start, currentTask, loading, error } = useModelDownload()
    const result = await start('qwen2')

    expect(result).toEqual(task)
    expect(currentTask.value).toEqual(task)
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
  })

  it('start失败设置error并返回null', async () => {
    startDownload.mockRejectedValue(new Error('磁盘不足'))

    const { start, error } = useModelDownload()
    const result = await start('big-model')

    expect(result).toBeNull()
    expect(error.value).toBe('磁盘不足')
  })

  it('start无task_id时currentTask不变', async () => {
    const result = { message: 'already downloading' }
    startDownload.mockResolvedValue(result)

    const { start, currentTask } = useModelDownload()
    await start('model')

    expect(currentTask.value).toBeNull()
  })

  it('getStatus更新currentTask', async () => {
    const updated = { task_id: 'dl-1', status: 'downloading', progress_pct: 50 }
    getDownloadStatus.mockResolvedValue(updated)

    const { getStatus, currentTask } = useModelDownload()
    const result = await getStatus('dl-1')

    expect(result).toEqual(updated)
    expect(currentTask.value).toEqual(updated)
  })

  it('cancel调用cancelDownload', async () => {
    cancelDownload.mockResolvedValue({ cancelled: true })

    const { cancel } = useModelDownload()
    const result = await cancel('dl-1')

    expect(cancelDownload).toHaveBeenCalledWith('dl-1')
    expect(result).toEqual({ cancelled: true })
  })

  it('list填充tasks', async () => {
    const downloadTasks = [
      { task_id: 'dl-1', model_name: 'qwen2', status: 'completed' },
      { task_id: 'dl-2', model_name: 'llama', status: 'downloading' },
    ]
    listDownloads.mockResolvedValue(downloadTasks)

    const { list, tasks } = useModelDownload()
    const result = await list()

    expect(result).toEqual(downloadTasks)
    expect(tasks.value).toEqual(downloadTasks)
  })

  it('connectDownloadWS创建WebSocket连接', () => {
    const { connectDownloadWS } = useModelDownload()
    connectDownloadWS()
  })

  it('disconnectWS关闭连接', () => {
    const { connectDownloadWS, disconnectWS, wsConnected } = useModelDownload()
    connectDownloadWS()
    disconnectWS()
    expect(wsConnected.value).toBe(false)
  })
})
