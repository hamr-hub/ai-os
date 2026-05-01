import { ref, type Ref } from 'vue'
import { recommendModel, checkModelMemory, getGPUSummary, getGPUMemoryCheck, getEngineStatus, switchEngine } from '@/api/client'
import type { RecommendResult, MemoryCheckResult, GPUSummary, GPUMemoryInfo, EngineStatus, EngineType } from '@/types'

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

export function useGPUMemory() {
  const gpuInfo: Ref<GPUSummary | null> = ref(null)
  const recommendResult: Ref<RecommendResult | null> = ref(null)
  const memoryCheckResult: Ref<MemoryCheckResult | null> = ref(null)
  const memoryInfo: Ref<GPUMemoryInfo | null> = ref(null)
  const engineStatus: Ref<EngineStatus | null> = ref(null)
  const switchingEngine = ref(false)
  const loading = ref(false)
  const error: Ref<string | null> = ref(null)

  const getGPU = async () => {
    loading.value = true
    error.value = null
    try {
      gpuInfo.value = await getGPUSummary()
    } catch (e: any) {
      error.value = e.message || '获取GPU信息失败'
      gpuInfo.value = null
    } finally {
      loading.value = false
    }
  }

  const recommend = async (keyword: string, source: string = 'all') => {
    loading.value = true
    error.value = null
    try {
      recommendResult.value = await recommendModel(keyword, source)
    } catch (e: any) {
      error.value = e.message || '推荐失败'
      recommendResult.value = null
    } finally {
      loading.value = false
    }
  }

  const checkMemory = async (modelName: string) => {
    loading.value = true
    error.value = null
    try {
      memoryCheckResult.value = await checkModelMemory(modelName)
    } catch (e: any) {
      error.value = e.message || '显存校验失败'
      memoryCheckResult.value = null
    } finally {
      loading.value = false
    }
  }

  const getMemoryInfo = async () => {
    loading.value = true
    error.value = null
    try {
      memoryInfo.value = await getGPUMemoryCheck()
    } catch (e: any) {
      error.value = e.message || '获取显存信息失败'
      memoryInfo.value = null
    } finally {
      loading.value = false
    }
  }

  const getEngines = async () => {
    loading.value = true
    error.value = null
    try {
      const response = await getEngineStatus()
      engineStatus.value = normalizeEngineStatus(response)
    } catch (e: any) {
      error.value = e.message || '获取引擎状态失败'
      engineStatus.value = null
    } finally {
      loading.value = false
    }
  }

  const doSwitchEngine = async (targetEngine: EngineType) => {
    switchingEngine.value = true
    error.value = null
    try {
      const currentEngine = engineStatus.value?.current_engine ?? 'vllm'
      const currentModel =
        engineStatus.value?.[currentEngine]?.model ??
        engineStatus.value?.vllm.model ??
        engineStatus.value?.sglang.model ??
        engineStatus.value?.llama_cpp.model
      const currentPort =
        engineStatus.value?.[targetEngine]?.port ??
        engineStatus.value?.[currentEngine]?.port ??
        8000
      const result = await switchEngine(currentModel ?? '', targetEngine, currentPort)
      if (engineStatus.value) {
        engineStatus.value.current_engine = targetEngine
      }
      return result
    } catch (e: any) {
      error.value = e.message || '引擎切换失败'
      return null
    } finally {
      switchingEngine.value = false
    }
  }

  return {
    gpuInfo, recommendResult, memoryCheckResult, memoryInfo, engineStatus,
    switchingEngine, loading, error,
    getGPU, recommend, checkMemory, getMemoryInfo, getEngines, doSwitchEngine,
  }
}
