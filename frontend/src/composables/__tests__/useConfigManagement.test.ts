import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/client', () => ({
  getVLLMDefaultConfig: vi.fn(),
  getEngineConfig: vi.fn(),
  updateEngineConfig: vi.fn(),
  getDefaultModel: vi.fn(),
  setDefaultModel: vi.fn(),
  clearDefaultModel: vi.fn(),
  getSystemConfig: vi.fn(),
  updateSystemConfig: vi.fn(),
}))

import * as apiClient from '@/api/client'
import { useConfigManagement } from '@/composables/useConfigManagement'

const getVLLMDefaultConfig = vi.mocked(apiClient.getVLLMDefaultConfig)
const getEngineConfig = vi.mocked(apiClient.getEngineConfig)
const updateEngineConfig = vi.mocked(apiClient.updateEngineConfig)
const getDefaultModel = vi.mocked(apiClient.getDefaultModel)
const setDefaultModel = vi.mocked(apiClient.setDefaultModel)
const clearDefaultModel = vi.mocked(apiClient.clearDefaultModel)
const getSystemConfig = vi.mocked(apiClient.getSystemConfig)
const updateSystemConfig = vi.mocked(apiClient.updateSystemConfig)

describe('useConfigManagement', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('fetchAll并行获取4种配置并赋值', async () => {
    const vllmConf = { gpu_memory_utilization: 0.9, max_model_len: 4096, max_num_seqs: 16, max_num_batched_tokens: 8192, tensor_parallel_size: 1 }
    const engConf = {
      vllm: { command: 'python -m vllm.entrypoints.openai.api_server', default_params: {} },
      sglang: { command: 'python -m sglang.launch_server', default_params: {} },
      llama_cpp: { command: 'llama-server', default_params: {} },
    }
    const sysConf = {
      health_check_interval_seconds: 30,
      cache_ttl_seconds: 60,
      log_level: 'info',
      gpu_poll_interval_seconds: 5,
      ws_push_interval_seconds: 2,
    }
    getVLLMDefaultConfig.mockResolvedValue(vllmConf)
    getEngineConfig.mockResolvedValue(engConf)
    getSystemConfig.mockResolvedValue(sysConf)
    getDefaultModel.mockResolvedValue({ default_model: 'llama' })

    const { fetchAll, vllmDefaultConfig, engineConfig, systemConfig, defaultModel, loading, error } = useConfigManagement()
    await fetchAll()

    expect(vllmDefaultConfig.value).toEqual(vllmConf)
    expect(engineConfig.value).toEqual(engConf)
    expect(systemConfig.value).toEqual(sysConf)
    expect(defaultModel.value).toBe('llama')
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
  })

  it('fetchAll失败时设置error', async () => {
    getVLLMDefaultConfig.mockRejectedValue(new Error('网络错误'))

    const { fetchAll, error, loading } = useConfigManagement()
    await fetchAll()

    expect(error.value).toBe('网络错误')
    expect(loading.value).toBe(false)
  })

  it('updateEngineConf成功返回true并更新engineConfig', async () => {
    const newConf = { engine_type: 'trt', port: 9000 }
    updateEngineConfig.mockResolvedValue(newConf)

    const { updateEngineConf, engineConfig, loading, error } = useConfigManagement()
    const result = await updateEngineConf(newConf)

    expect(result).toBe(true)
    expect(engineConfig.value).toEqual(newConf)
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
  })

  it('updateEngineConf失败返回false并设置error', async () => {
    updateEngineConfig.mockRejectedValue(new Error('配置冲突'))

    const { updateEngineConf, error } = useConfigManagement()
    const result = await updateEngineConf({ port: 9999 })

    expect(result).toBe(false)
    expect(error.value).toBe('配置冲突')
  })

  it('updateSystemConf成功返回true并更新systemConfig', async () => {
    const newConf = { debug: true }
    updateSystemConfig.mockResolvedValue(newConf)

    const { updateSystemConf, systemConfig } = useConfigManagement()
    const result = await updateSystemConf(newConf)

    expect(result).toBe(true)
    expect(systemConfig.value).toEqual(newConf)
  })

  it('setDefault成功设置defaultModel', async () => {
    setDefaultModel.mockResolvedValue({})

    const { setDefault, defaultModel } = useConfigManagement()
    const result = await setDefault('qwen2')

    expect(result).toBe(true)
    expect(defaultModel.value).toBe('qwen2')
  })

  it('clearDefault成功清空defaultModel', async () => {
    clearDefaultModel.mockResolvedValue({})

    const { clearDefault, defaultModel } = useConfigManagement()
    const result = await clearDefault()

    expect(result).toBe(true)
    expect(defaultModel.value).toBeNull()
  })

  it('getDefaultModel返回null时defaultModel为null', async () => {
    getDefaultModel.mockResolvedValue({ default_model: null })

    const { fetchAll, defaultModel } = useConfigManagement()
    getVLLMDefaultConfig.mockResolvedValue({})
    getEngineConfig.mockResolvedValue({})
    getSystemConfig.mockResolvedValue({})
    await fetchAll()

    expect(defaultModel.value).toBeNull()
  })
})
