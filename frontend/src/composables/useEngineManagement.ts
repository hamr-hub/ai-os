import { ref, type Ref } from 'vue'
import { getEngineStatus, switchEngine, getEngineConfig, updateEngineConfig } from '@/api/client'
import type { EngineType, EngineStatus, EngineConfig, SwitchSession } from '@/types'

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
      engineStatus.value = await getEngineStatus()
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
      engineConfig.value = await getEngineConfig()
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
      engineConfig.value = await updateEngineConfig(newConfig)
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
