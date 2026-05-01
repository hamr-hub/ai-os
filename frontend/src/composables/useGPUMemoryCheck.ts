import { ref, type Ref } from 'vue'
import { getGPUMemoryCheck, recommendModel, checkModelMemory } from '@/api/client'
import type { GPUMemoryInfo, RecommendResult, MemoryCheckResult } from '@/types'

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

export function useGPUMemoryCheck() {
  const memoryInfo: Ref<GPUMemoryInfo | null> = ref(null)
  const recommendation: Ref<RecommendResult | null> = ref(null)
  const checkResult: Ref<MemoryCheckResult | null> = ref(null)
  const loading = ref(false)
  const error: Ref<string | null> = ref(null)

  const fetchMemoryInfo = async () => {
    loading.value = true
    error.value = null
    try {
      const raw = await getGPUMemoryCheck()
      memoryInfo.value = normalizeGPUMemoryInfo(raw)
    } catch (e: unknown) {
      error.value = (e as Error).message
      memoryInfo.value = null
    } finally {
      loading.value = false
    }
  }

  const getRecommendation = async (keyword: string = '', source: string = 'all') => {
    loading.value = true
    error.value = null
    try {
      recommendation.value = await recommendModel(keyword, source)
    } catch (e: unknown) {
      error.value = (e as Error).message
      recommendation.value = null
    } finally {
      loading.value = false
    }
  }

  const checkModel = async (modelName: string) => {
    loading.value = true
    error.value = null
    try {
      checkResult.value = await checkModelMemory(modelName)
      return checkResult.value
    } catch (e: unknown) {
      error.value = (e as Error).message
      return null
    } finally {
      loading.value = false
    }
  }

  return { memoryInfo, recommendation, checkResult, loading, error, fetchMemoryInfo, getRecommendation, checkModel }
}
