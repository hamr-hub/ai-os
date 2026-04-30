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
import type { VLLMDefaultConfig, EngineConfig, SystemConfig } from '@/types'

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
      engineConfig.value = await getEngineConfig()
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
      engineConfig.value = await updateEngineConfig(newConfig)
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
