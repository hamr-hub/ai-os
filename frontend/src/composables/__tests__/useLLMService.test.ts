import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/api/client', () => ({
  startModel: vi.fn(),
  stopModel: vi.fn(),
  getLLMServiceStatus: vi.fn(),
  getLLMServiceLogs: vi.fn(),
  loadFromPool: vi.fn(),
}))

import * as apiClient from '@/api/client'
import { useLLMService } from '@/composables/useLLMService'

const startModel = vi.mocked(apiClient.startModel)
const stopModel = vi.mocked(apiClient.stopModel)
const getLLMServiceStatus = vi.mocked(apiClient.getLLMServiceStatus)
const getLLMServiceLogs = vi.mocked(apiClient.getLLMServiceLogs)
const loadFromPool = vi.mocked(apiClient.loadFromPool)

describe('useLLMService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('getStatus填充services字典', async () => {
    const services = { vllm: { running: true, engine: 'vllm', port: 8000, pid: 123, started_at: '2026-01-01' } }
    getLLMServiceStatus.mockResolvedValue(services)

    const { getStatus, services: servicesRef, loading, error } = useLLMService()
    await getStatus()

    expect(servicesRef.value).toEqual(services)
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
  })

  it('getStatus失败设置error', async () => {
    getLLMServiceStatus.mockRejectedValue(new Error('不可用'))

    const { getStatus, services: servicesRef, error } = useLLMService()
    await getStatus()

    expect(servicesRef.value).toEqual({})
    expect(error.value).toBe('不可用')
  })

  it('getLogs只取result.logs', async () => {
    const result = { logs: ['log1', 'log2'] }
    getLLMServiceLogs.mockResolvedValue(result)

    const { getLogs, logs, loading } = useLLMService()
    await getLogs(50)

    expect(logs.value).toEqual(['log1', 'log2'])
    expect(getLLMServiceLogs).toHaveBeenCalledWith(50)
    expect(loading.value).toBe(false)
  })

  it('getLogs失败清空logs', async () => {
    getLLMServiceLogs.mockRejectedValue(new Error('日志丢失'))

    const { getLogs, logs, error } = useLLMService()
    await getLogs()

    expect(logs.value).toEqual([])
    expect(error.value).toBe('日志丢失')
  })

  it('start返回结果', async () => {
    const result = { started: true }
    startModel.mockResolvedValue(result)

    const { start } = useLLMService()
    const resp = await start('llama')

    expect(startModel).toHaveBeenCalledWith('llama')
    expect(resp).toEqual(result)
  })

  it('stop返回结果', async () => {
    const result = { stopped: true }
    stopModel.mockResolvedValue(result)

    const { stop } = useLLMService()
    const resp = await stop('llama')

    expect(stopModel).toHaveBeenCalledWith('llama')
    expect(resp).toEqual(result)
  })

  it('loadFromPoolService返回结果', async () => {
    const result = { loaded: true }
    loadFromPool.mockResolvedValue(result)

    const { loadFromPoolService } = useLLMService()
    const resp = await loadFromPoolService('qwen2', 'vllm')

    expect(loadFromPool).toHaveBeenCalledWith('qwen2', 'vllm')
    expect(resp).toEqual(result)
  })
})
