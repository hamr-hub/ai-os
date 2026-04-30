import { ref, type Ref } from 'vue'
import { recommendModel, checkModelMemory, getGPUSummary, getGPUMemoryCheck, getEngineStatus, switchEngine } from '@/api/client'
import type { RecommendResult, MemoryCheckResult, GPUSummary, GPUMemoryInfo, EngineStatus, EngineType } from '@/types'

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
      engineStatus.value = await getEngineStatus()
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
      const result = await switchEngine(targetEngine)
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
