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

import {
  getVLLMDefaultConfig,
  getEngineConfig,
  updateEngineConfig,
  getDefaultModel,
  setDefaultModel,
  clearDefaultModel,
  getSystemConfig,
  updateSystemConfig,
} from '@/api/client'
import { useConfigManagement } from '@/composables/useConfigManagement'

describe('useConfigManagement', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('fetchAll并行获取4种配置并赋值', async () => {
    const vllmConf = { max_model_len: 4096 }
    const engConf = { engine_type: 'vllm', port: 8000 }
    const sysConf = { debug: false }
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
