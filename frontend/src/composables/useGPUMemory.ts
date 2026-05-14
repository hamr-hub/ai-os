import { ref, type Ref } from 'vue'
import { recommendModel, checkModelMemory, getGPUSummary, getGPUMemoryCheck, getEngineStatus, switchEngine, getAggregatedModels } from '@/api/client'
import type { RecommendResult, MemoryCheckResult, GPUSummary, GPUMemoryInfo, EngineStatus, EngineType } from '@/types'

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
}

interface RawEngineStatusResponse {
  current_engine?: EngineType
  engine_manager_mode?: string
  services?: RawServiceStatus[]
  active_count?: number
}

const ENGINE_TYPES: EngineType[] = ['vllm', 'sglang', 'llamacpp']

const normalizeModelName = (name: string | null | undefined) => (name ?? '').trim().toLowerCase()

const selectModelForEngine = async (
  status: EngineStatus | null,
  targetEngine: EngineType,
): Promise<{ modelName: string; port: number | null }> => {
  const currentEngine = status?.current_engine ?? 'vllm'
  const currentModel =
    status?.[currentEngine]?.model ??
    status?.vllm.model ??
    status?.sglang.model ??
    status?.llamacpp.model ??
    ''
  const currentModelKey = normalizeModelName(currentModel)

  try {
    const aggregated = await getAggregatedModels()
    const variants = aggregated.groups.flatMap(group =>
      group.variants.map(variant => ({
        name: variant.name || group.base_name,
        variant,
      })),
    )
    const variantEngine = (variant: any) => (variant.backend_type || variant.engine_type || variant.service || 'vllm') as EngineType
    const pick = (predicate: (item: typeof variants[number]) => boolean) => variants.find(predicate) ?? null

    const selected =
      pick(item => variantEngine(item.variant) === targetEngine && normalizeModelName(item.name) === currentModelKey) ||
      pick(item => variantEngine(item.variant) === targetEngine && (item.variant.running || item.variant.is_current)) ||
      pick(item => variantEngine(item.variant) === targetEngine && item.variant.path_exists !== false) ||
      pick(item => variantEngine(item.variant) === targetEngine) ||
      pick(item => item.variant.running || item.variant.is_current) ||
      variants[0] ||
      null
    if (selected) return { modelName: selected.name, port: selected.variant.port ?? null }
    return { modelName: targetEngine === currentEngine ? currentModel : '', port: status?.[targetEngine]?.port ?? null }
  } catch {
    return { modelName: targetEngine === currentEngine ? currentModel : '', port: status?.[targetEngine]?.port ?? null }
  }
}

const normalizeGPUMemoryInfo = (raw: any): GPUMemoryInfo => {
  const gpuData = raw?.gpu ?? {}
  return {
    available: raw?.available ?? (gpuData?.free_gb > 0) ?? true,
    total_gb: gpuData?.total_gb ?? raw?.total_gb ?? 0,
    used_gb: gpuData?.used_gb ?? raw?.used_gb ?? 0,
    free_gb: gpuData?.free_gb ?? raw?.free_gb ?? 0,
    safety_available_gb: gpuData?.free_gb ?? raw?.safety_available_gb ?? raw?.free_gb ?? 0,
    gpu_name: gpuData?.name ?? raw?.gpu_name ?? '',
    method: (gpuData?.backend ?? gpuData?.method ?? raw?.method ?? 'pynvml') as GPUMemoryInfo['method'],
  }
}

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
      const raw = await getGPUMemoryCheck()
      memoryInfo.value = normalizeGPUMemoryInfo(raw)
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
      const targetSelection = await selectModelForEngine(engineStatus.value, targetEngine)
      const currentPort =
        targetSelection.port ??
        engineStatus.value?.[targetEngine]?.port ??
        engineStatus.value?.[currentEngine]?.port ??
        8000
      const result = await switchEngine(targetSelection.modelName, targetEngine, currentPort)
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
