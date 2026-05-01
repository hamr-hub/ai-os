import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { EngineStatus } from '@/types'

vi.mock('@/api/client', () => ({
  getEngineStatus: vi.fn(),
  switchEngine: vi.fn(),
  getEngineConfig: vi.fn(),
  updateEngineConfig: vi.fn(),
}))

import * as apiClient from '@/api/client'
import { useEngineManagement } from '@/composables/useEngineManagement'

const getEngineStatus = vi.mocked(apiClient.getEngineStatus)
const switchEngine = vi.mocked(apiClient.switchEngine)
const getEngineConfig = vi.mocked(apiClient.getEngineConfig)
const updateEngineConfig = vi.mocked(apiClient.updateEngineConfig)

const createEngineStatus = (overrides: Partial<EngineStatus> = {}): EngineStatus => ({
  current_engine: 'vllm',
  vllm: { running: false, pid: null, port: null, model: null, uptime: null },
  sglang: { running: false, pid: null, port: null, model: null, uptime: null },
  llama_cpp: { running: false, pid: null, port: null, model: null, uptime: null },
  ...overrides,
})

describe('useEngineManagement', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('normalizeEngineStatus兼容后端engine_type字段', async () => {
    const backendRaw = {
      engine_manager_mode: 'subprocess',
      services: [
        { status: 'running', engine_type: 'vllm', pid: 123, port: 8000, model: 'Qwen3-235B', uptime_seconds: 120, health: 'healthy', service_name: 'vllm-aiclient' },
      ],
      active_count: 1,
    }
    getEngineStatus.mockResolvedValue(backendRaw as any)

    const { fetchStatus, engineStatus } = useEngineManagement()
    await fetchStatus()

    expect(engineStatus.value?.vllm.running).toBe(true)
    expect(engineStatus.value?.vllm.pid).toBe(123)
    expect(engineStatus.value?.vllm.port).toBe(8000)
    expect(engineStatus.value?.vllm.model).toBe('Qwen3-235B')
    expect(engineStatus.value?.vllm.uptime).toBe(120)
    expect(engineStatus.value?.current_engine).toBe('vllm')
  })

  it('fetchStatus填充engineStatus', async () => {
    const status = createEngineStatus({
      vllm: { running: true, pid: 123, port: 8000, model: 'llama', uptime: 60 },
    })
    getEngineStatus.mockResolvedValue(status)

    const { fetchStatus, engineStatus, loading, error } = useEngineManagement()
    await fetchStatus()

    expect(engineStatus.value?.current_engine).toBe('vllm')
    expect(engineStatus.value?.vllm.running).toBe(true)
    expect(engineStatus.value?.vllm.pid).toBe(123)
    expect(engineStatus.value?.vllm.port).toBe(8000)
    expect(engineStatus.value?.vllm.model).toBe('llama')
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
  })

  it('fetchStatus失败清空engineStatus并设置error', async () => {
    getEngineStatus.mockRejectedValue(new Error('超时'))

    const { fetchStatus, engineStatus, error } = useEngineManagement()
    await fetchStatus()

    expect(engineStatus.value).toBeNull()
    expect(error.value).toBe('超时')
  })

  it('fetchConfig填充engineConfig', async () => {
    const config = {
      vllm: { command: 'python -m vllm', default_params: {} },
      sglang: { command: 'python -m sglang', default_params: {} },
      llama_cpp: { command: 'llama-server', default_params: {} },
    }
    getEngineConfig.mockResolvedValue(config)

    const { fetchConfig, engineConfig } = useEngineManagement()
    await fetchConfig()

    expect(engineConfig.value).toEqual(config)
  })

  it('doSwitchEngine成功返回session_id时构造SwitchSession', async () => {
    const result = { status: 'ok', session_id: 'sess-123' }
    switchEngine.mockResolvedValue(result)

    const { doSwitchEngine, switchSession, switching, error } = useEngineManagement()
    const resp = await doSwitchEngine('llama', 'vllm', 8000)

    expect(resp).toEqual(result)
    expect(switchSession.value).toBeTruthy()
    expect(switchSession.value!.session_id).toBe('sess-123')
    expect(switchSession.value!.target_model).toBe('llama')
    expect(switchSession.value!.action).toBe('switch')
    expect(switching.value).toBe(false)
    expect(error.value).toBeNull()
  })

  it('doSwitchEngine失败返回null并设置error', async () => {
    switchEngine.mockRejectedValue(new Error('引擎繁忙'))

    const { doSwitchEngine, switchSession, error, switching } = useEngineManagement()
    const resp = await doSwitchEngine('fail-model')

    expect(resp).toBeNull()
    expect(switchSession.value).toBeNull()
    expect(error.value).toBe('引擎繁忙')
    expect(switching.value).toBe(false)
  })

  it('doUpdateConfig成功返回true并更新engineConfig', async () => {
    const newConf = {
      vllm: { command: 'python -m vllm', default_params: { port: 9000 } },
      sglang: { command: 'python -m sglang', default_params: {} },
      llama_cpp: { command: 'llama-server', default_params: {} },
    }
    updateEngineConfig.mockResolvedValue(newConf)

    const { doUpdateConfig, engineConfig, loading } = useEngineManagement()
    const result = await doUpdateConfig(newConf)

    expect(result).toBe(true)
    expect(engineConfig.value).toEqual(newConf)
    expect(loading.value).toBe(false)
  })

  it('doUpdateConfig失败返回false并设置error', async () => {
    updateEngineConfig.mockRejectedValue(new Error('不支持'))

    const { doUpdateConfig, error } = useEngineManagement()
    const result = await doUpdateConfig({
      vllm: { command: 'python -m vllm', default_params: { port: 0 } },
      sglang: { command: 'python -m sglang', default_params: {} },
      llama_cpp: { command: 'llama-server', default_params: {} },
    })

    expect(result).toBe(false)
    expect(error.value).toBe('不支持')
  })
})
