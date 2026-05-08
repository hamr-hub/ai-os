import { ref, type Ref } from 'vue'
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
import type { VLLMDefaultConfig, EngineConfig, SystemConfig, EngineType } from '@/types'

interface RawEngineConfigEntry {
  command?: string
  default_params?: Record<string, unknown>
  default_gpu_memory_utilization?: number
  default_max_model_len?: number
  default_port?: number
  engine_manager_mode?: string
  env_vars?: Record<string, string>
  hf_endpoint?: string
  model_base_path?: string
  service_name?: string
  start_script?: string
  venv_path?: string
}

interface RawEngineConfigResponse {
  vllm?: RawEngineConfigEntry
  sglang?: RawEngineConfigEntry
  llamacpp?: RawEngineConfigEntry
  default_engine?: string
  engine_manager_mode?: string
}

const normalizeEngineConfig = (payload: unknown): EngineConfig => {
  const raw = (payload ?? {}) as RawEngineConfigResponse
  const normalizeEntry = (entry?: RawEngineConfigEntry): { command: string; default_params: Record<string, unknown> } => {
    if (!entry) return { command: '', default_params: {} }
    if (entry.command && entry.default_params) {
      return { command: entry.command, default_params: entry.default_params }
    }
    const params: Record<string, unknown> = {}
    if (entry.default_gpu_memory_utilization != null) params.gpu_memory_utilization = entry.default_gpu_memory_utilization
    if (entry.default_max_model_len != null) params.max_model_len = entry.default_max_model_len
    if (entry.default_port != null) params.port = entry.default_port
    if (entry.engine_manager_mode) params.engine_manager_mode = entry.engine_manager_mode
    if (entry.env_vars) params.env_vars = entry.env_vars
    if (entry.hf_endpoint) params.hf_endpoint = entry.hf_endpoint
    if (entry.model_base_path) params.model_base_path = entry.model_base_path
    if (entry.service_name) params.service_name = entry.service_name
    if (entry.start_script) params.start_script = entry.start_script
    if (entry.venv_path) params.venv_path = entry.venv_path
    return { command: entry.start_script ?? '', default_params: params }
  }
  return {
    vllm: normalizeEntry(raw.vllm),
    sglang: normalizeEntry(raw.sglang),
    llamacpp: normalizeEntry(raw.llamacpp),
  }
}

const toEngineConfigPayload = (payload: Partial<EngineConfig>) => {
  const result: Partial<Record<EngineType, RawEngineConfigEntry>> = {}
  const engineTypes: EngineType[] = ['vllm', 'sglang', 'llamacpp']
  for (const engineType of engineTypes) {
    const config = payload[engineType]
    if (!config) continue
    result[engineType] = {
      command: config.command,
      default_params: config.default_params,
    }
  }
  return result
}

export function useConfigManagement() {
  const vllmDefaultConfig: Ref<VLLMDefaultConfig | null> = ref(null)
  const engineConfig: Ref<EngineConfig | null> = ref(null)
  const systemConfig: Ref<SystemConfig | null> = ref(null)
  const defaultModel: Ref<string | null> = ref(null)
  const loading = ref(false)
  const error: Ref<string | null> = ref(null)

  const fetchAll = async () => {
    loading.value = true
    error.value = null
    try {
      vllmDefaultConfig.value = await getVLLMDefaultConfig()
      engineConfig.value = normalizeEngineConfig(await getEngineConfig())
      systemConfig.value = await getSystemConfig()
      const dm = await getDefaultModel()
      defaultModel.value = dm?.default_model ?? null
    } catch (e: unknown) {
      error.value = (e as Error).message || '获取配置失败'
    } finally {
      loading.value = false
    }
  }

  const updateEngineConf = async (newConfig: Partial<EngineConfig>) => {
    loading.value = true
    error.value = null
    try {
      const response = await updateEngineConfig(toEngineConfigPayload(newConfig) as Partial<EngineConfig>)
      engineConfig.value = normalizeEngineConfig(response)
      return true
    } catch (e: unknown) {
      error.value = (e as Error).message || '更新引擎配置失败'
      return false
    } finally {
      loading.value = false
    }
  }

  const updateSystemConf = async (newConfig: Partial<SystemConfig>) => {
    loading.value = true
    error.value = null
    try {
      systemConfig.value = await updateSystemConfig(newConfig)
      return true
    } catch (e: unknown) {
      error.value = (e as Error).message || '更新系统配置失败'
      return false
    } finally {
      loading.value = false
    }
  }

  const setDefault = async (model: string) => {
    loading.value = true
    error.value = null
    try {
      await setDefaultModel(model)
      defaultModel.value = model
      return true
    } catch (e: unknown) {
      error.value = (e as Error).message || '设置默认模型失败'
      return false
    } finally {
      loading.value = false
    }
  }

  const clearDefault = async () => {
    loading.value = true
    error.value = null
    try {
      await clearDefaultModel()
      defaultModel.value = null
      return true
    } catch (e: unknown) {
      error.value = (e as Error).message || '清除默认模型失败'
      return false
    } finally {
      loading.value = false
    }
  }

  return {
    vllmDefaultConfig,
    engineConfig,
    systemConfig,
    defaultModel,
    loading,
    error,
    fetchAll,
    updateEngineConf,
    updateSystemConf,
    setDefault,
    clearDefault,
  }
}
