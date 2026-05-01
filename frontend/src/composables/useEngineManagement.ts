import { ref, type Ref } from 'vue'
import { getEngineStatus, switchEngine, getEngineConfig, updateEngineConfig } from '@/api/client'
import type { EngineType, EngineStatus, EngineConfig, SwitchSession } from '@/types'

interface RawServiceStatus {
  engine?: string | null
  status?: string | null
  port?: number | null
  pid?: number | null
  started_at?: string | null
  model_name?: string | null
  model?: string | null
}

interface RawEngineStatusResponse {
  current_engine?: EngineType
  services?: RawServiceStatus[]
}

interface RawEngineConfigEntry {
  command?: string
  default_params?: Record<string, unknown>
}

interface RawEngineConfigResponse {
  vllm?: RawEngineConfigEntry
  sglang?: RawEngineConfigEntry
  llama_cpp?: RawEngineConfigEntry
}

const ENGINE_TYPES: EngineType[] = ['vllm', 'sglang', 'llama_cpp']

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
    llama_cpp: createEmptyEngineState(),
    current_engine: raw.current_engine ?? 'vllm',
  }

  if (Array.isArray(raw.services)) {
    for (const service of raw.services) {
      const engine = service.engine
      if (!engine || !ENGINE_TYPES.includes(engine as EngineType)) continue
      const startedAt = service.started_at ? Date.parse(service.started_at) : NaN
      normalized[engine as EngineType] = {
        running: service.status === 'running',
        pid: service.pid ?? null,
        port: service.port ?? null,
        model: service.model_name ?? service.model ?? null,
        uptime: Number.isFinite(startedAt) ? Math.max(0, Math.floor((Date.now() - startedAt) / 1000)) : null,
      }
      if (service.status === 'running') {
        normalized.current_engine = engine as EngineType
      }
    }
  }

  return normalized
}

const normalizeEngineConfig = (payload: unknown): EngineConfig => {
  const raw = (payload ?? {}) as RawEngineConfigResponse
  return {
    vllm: {
      command: raw.vllm?.command ?? '',
      default_params: raw.vllm?.default_params ?? {},
    },
    sglang: {
      command: raw.sglang?.command ?? '',
      default_params: raw.sglang?.default_params ?? {},
    },
    llama_cpp: {
      command: raw.llama_cpp?.command ?? '',
      default_params: raw.llama_cpp?.default_params ?? {},
    },
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
