import { ref, type Ref } from 'vue'
import { getEngineStatus, switchEngine, getEngineConfig, updateEngineConfig } from '@/api/client'
import type { EngineType, EngineStatus, EngineConfig, SwitchSession } from '@/types'

interface RawServiceStatus {
  engine?: string | null
  engine_type?: string | null
  status?: string | null
  port?: number | null
  pid?: number | null
  started_at?: string | null
  uptime_seconds?: number | null
  model_name?: string | null
  model?: string | null
  health?: string | null
  service_name?: string | null
}

interface RawEngineStatusResponse {
  current_engine?: EngineType
  engine_manager_mode?: string
  services?: RawServiceStatus[]
  active_count?: number
}

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

const ENGINE_TYPES: EngineType[] = ['vllm', 'sglang', 'llamacpp']

const createEmptyEngineState = () => ({
  running: false,
  pid: null,
  port: null,
  model: null,
  uptime: null,
})

const normalizeEngineStatus = (payload: unknown): EngineStatus => {
  const raw = (payload ?? {}) as RawEngineStatusResponse
  const normalized: EngineStatus = {
    vllm: createEmptyEngineState(),
    sglang: createEmptyEngineState(),
    llamacpp: createEmptyEngineState(),
    current_engine: raw.current_engine ?? 'vllm',
  }

  if (Array.isArray(raw.services)) {
    for (const service of raw.services) {
      const engine = (service.engine_type ?? service.engine) as EngineType | null
      if (!engine || !ENGINE_TYPES.includes(engine)) continue
      let uptime: number | null = null
      if (service.uptime_seconds != null) {
        uptime = Math.round(service.uptime_seconds)
      } else if (service.started_at) {
        const startedAt = Date.parse(service.started_at)
        if (Number.isFinite(startedAt)) uptime = Math.max(0, Math.floor((Date.now() - startedAt) / 1000))
      }
      normalized[engine] = {
        running: service.status === 'running',
        pid: service.pid ?? null,
        port: service.port ?? null,
        model: service.model_name ?? service.model ?? null,
        uptime,
      }
      if (service.status === 'running') {
        normalized.current_engine = engine
      }
    }
  }

  return normalized
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

export function useEngineManagement() {
  const engineStatus: Ref<EngineStatus | null> = ref(null)
  const engineConfig: Ref<EngineConfig | null> = ref(null)
  const switchSession: Ref<SwitchSession | null> = ref(null)
  const loading = ref(false)
  const switching = ref(false)
  const error: Ref<string | null> = ref(null)

  const fetchStatus = async () => {
    loading.value = true
    error.value = null
    try {
      const response = await getEngineStatus()
      engineStatus.value = normalizeEngineStatus(response)
    } catch (e: unknown) {
      error.value = (e as Error).message || '获取引擎状态失败'
      engineStatus.value = null
    } finally {
      loading.value = false
    }
  }

  const fetchConfig = async () => {
    loading.value = true
    error.value = null
    try {
      const response = await getEngineConfig()
      engineConfig.value = normalizeEngineConfig(response)
    } catch (e: unknown) {
      error.value = (e as Error).message || '获取引擎配置失败'
      engineConfig.value = null
    } finally {
      loading.value = false
    }
  }

  const doSwitchEngine = async (modelName: string, engineType: EngineType = 'vllm', port: number = 8000) => {
    switching.value = true
    error.value = null
    try {
      const result = await switchEngine(modelName, engineType, port)
      if (result.session_id) {
        switchSession.value = {
          session_id: result.session_id,
          action: 'switch',
          target_model: modelName,
          previous_model: null,
          started_at: new Date().toISOString(),
          finished_at: null,
          overall_phase: 'phase1',
          overall_progress: 0,
          phases: [],
          error: null,
          rollback_reason: null,
          completed_successfully: false,
        }
      }
      return result
    } catch (e: unknown) {
      error.value = (e as Error).message || '引擎切换失败'
      return null
    } finally {
      switching.value = false
    }
  }

  const doUpdateConfig = async (newConfig: Partial<EngineConfig>) => {
    loading.value = true
    error.value = null
    try {
      const response = await updateEngineConfig(newConfig)
      engineConfig.value = normalizeEngineConfig(response)
      return true
    } catch (e: unknown) {
      error.value = (e as Error).message || '更新引擎配置失败'
      return false
    } finally {
      loading.value = false
    }
  }

  return {
    engineStatus,
    engineConfig,
    switchSession,
    loading,
    switching,
    error,
    fetchStatus,
    fetchConfig,
    doSwitchEngine,
    doUpdateConfig,
  }
}
