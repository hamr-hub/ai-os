import { ref, onMounted, onUnmounted, computed } from 'vue'
import {
  getModelsStatus,
  startModel,
  stopModel,
  switchModel,
  getDefaultModel,
  setDefaultModel,
  clearDefaultModel,
} from '@/api/client'
import type { ModelStatus } from '@/types'
import { isAbortError } from '@/utils/request'
import { useAppStore } from '@/stores/app'

export function useModels() {
  const modelStatus = ref<ModelStatus | null>(null)
  const defaultModel = ref<string | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const actionLoading = ref<string | null>(null)
  const switchingModel = ref<string | null>(null)
  const isRefreshing = ref(false)
  let refreshInterval: number | null = null
  let switchPollingInterval: number | null = null
  let fetchController: AbortController | null = null
  let switchPollingController: AbortController | null = null

  const fetchModelStatus = async (manualRefresh = false) => {
    if (fetchController) {
      if (!manualRefresh) return
      fetchController.abort()
    }

    const controller = new AbortController()
    fetchController = controller

    if (manualRefresh) {
      isRefreshing.value = true
    } else {
      loading.value = true
    }
    error.value = null
    try {
      const [status, defaultModelResult] = await Promise.all([
        getModelsStatus({ signal: controller.signal }),
        getDefaultModel({ signal: controller.signal }),
      ])
      modelStatus.value = status
      defaultModel.value = defaultModelResult.default_model
    } catch (err) {
      if (isAbortError(err)) return
      error.value = err instanceof Error ? err.message : 'Failed to fetch model status'
      if (manualRefresh) {
        console.error('Failed to fetch model status:', err)
      }
    } finally {
      if (fetchController === controller) {
        fetchController = null
        loading.value = false
        isRefreshing.value = false
      }
    }
  }

  const refresh = () => {
    fetchModelStatus(true)
  }

  const handleSetDefaultModel = async (modelName: string) => {
    actionLoading.value = modelName
    error.value = null
    try {
      await setDefaultModel(modelName)
      defaultModel.value = modelName
    } catch (err) {
      error.value = err instanceof Error ? err.message : `Failed to set default model ${modelName}`
      console.error('Failed to set default model:', err)
    } finally {
      actionLoading.value = null
    }
  }

  const handleClearDefaultModel = async () => {
    error.value = null
    try {
      await clearDefaultModel()
      defaultModel.value = null
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to clear default model'
      console.error('Failed to clear default model:', err)
    }
  }

  const handleStartModel = async (modelName: string) => {
    const appStore = useAppStore()
    actionLoading.value = modelName
    error.value = null
    try {
      await startModel(modelName)
      switchingModel.value = modelName
      startSwitchPolling(modelName)
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : `Failed to start model ${modelName}`
      const axiosErr = err as { response?: { data?: { error?: string; message?: string } } }
      const apiError = axiosErr.response?.data?.error || axiosErr.response?.data?.message
      const fullError = apiError || errMsg
      error.value = fullError
      console.error('Failed to start model:', err)

      if (fullError.includes('insufficient memory') || fullError.includes('memory')) {
        appStore.warning(`模型 ${modelName} 所需显存超过当前可用显存，启动失败，请尝试停止其他模型后重试`)
      } else {
        appStore.warning(`模型 ${modelName} 启动失败：${fullError}`)
      }
      actionLoading.value = null
    }
  }

  const handleStopModel = async (modelName: string) => {
    actionLoading.value = modelName
    error.value = null
    try {
      await stopModel(modelName)
      await fetchModelStatus()
    } catch (err) {
      error.value = err instanceof Error ? err.message : `Failed to stop model ${modelName}`
      console.error('Failed to stop model:', err)
    } finally {
      actionLoading.value = null
    }
  }

  const handleSwitchModel = async (modelName: string, setAsDefault = false) => {
    const appStore = useAppStore()
    actionLoading.value = modelName
    switchingModel.value = modelName
    error.value = null
    try {
      await switchModel(modelName, false)
      if (setAsDefault) {
        await setDefaultModel(modelName)
        defaultModel.value = modelName
      }
      startSwitchPolling(modelName)
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : `Failed to switch to model ${modelName}`
      const axiosErr = err as { response?: { data?: { error?: string; message?: string } } }
      const apiError = axiosErr.response?.data?.error || axiosErr.response?.data?.message
      const fullError = apiError || errMsg
      error.value = fullError
      console.error('Failed to switch model:', err)

      if (fullError.includes('insufficient memory') || fullError.includes('memory')) {
        appStore.warning(`模型 ${modelName} 所需显存超过当前可用显存，切换失败，请尝试停止其他模型后重试`)
      } else if (fullError.includes('503')) {
        appStore.warning(`模型 ${modelName} 切换失败：服务不可用，请检查模型服务状态`)
      } else {
        appStore.warning(`模型 ${modelName} 切换失败：${fullError}`)
      }

      actionLoading.value = null
      switchingModel.value = null
    }
  }

  const startSwitchPolling = (modelName: string) => {
    if (switchPollingInterval) clearInterval(switchPollingInterval)
    if (switchPollingController) {
      switchPollingController.abort()
      switchPollingController = null
    }
    switchPollingInterval = window.setInterval(async () => {
      if (switchPollingController) return

      const controller = new AbortController()
      switchPollingController = controller
      try {
        const status = await getModelsStatus({ signal: controller.signal })
        modelStatus.value = status
        const modelEntry = status[modelName]
        if (modelEntry?.running) {
          actionLoading.value = null
          switchingModel.value = null
          if (switchPollingInterval) {
            clearInterval(switchPollingInterval)
            switchPollingInterval = null
          }
          const defaultModelResult = await getDefaultModel({ signal: controller.signal })
          defaultModel.value = defaultModelResult.default_model
        }
      } catch (err) {
        if (!isAbortError(err)) {
          console.error('[useModels] Switch polling error:', err)
        }
      } finally {
        if (switchPollingController === controller) {
          switchPollingController = null
        }
      }
    }, 5000)
  }

  const handleSwitchAndSetDefault = async (modelName: string) => {
    await handleSwitchModel(modelName, true)
  }

  const startAutoRefresh = () => {
    if (refreshInterval) return
    refreshInterval = window.setInterval(fetchModelStatus, 30000)
  }

  const stopAutoRefresh = () => {
    if (refreshInterval) {
      clearInterval(refreshInterval)
      refreshInterval = null
    }
    if (fetchController) {
      fetchController.abort()
      fetchController = null
    }
  }

  const toggleAutoRefresh = () => {
    if (refreshInterval) {
      stopAutoRefresh()
    } else {
      startAutoRefresh()
    }
  }

  const isAutoRefreshEnabled = computed(() => refreshInterval !== null)

  const modelList = computed(() => {
    if (!modelStatus.value) return []
    return Object.entries(modelStatus.value).map(([name, status]) => ({
      id: name,
      object: 'model',
      created: 0,
      owned_by: 'local',
      name,
      ...status,
    }))
  })

  const runningModelsCount = computed(() => {
    if (!modelStatus.value) return 0
    return Object.values(modelStatus.value).filter((m) => m.running).length
  })

  onMounted(() => {
    fetchModelStatus()
    startAutoRefresh()
  })

  onUnmounted(() => {
    stopAutoRefresh()
    if (switchPollingInterval) {
      clearInterval(switchPollingInterval)
      switchPollingInterval = null
    }
    if (switchPollingController) {
      switchPollingController.abort()
      switchPollingController = null
    }
  })

  return {
    modelStatus,
    modelList,
    defaultModel,
    loading,
    error,
    actionLoading,
    switchingModel,
    isRefreshing,
    isAutoRefreshEnabled,
    fetchModelStatus,
    refresh,
    startAutoRefresh,
    stopAutoRefresh,
    toggleAutoRefresh,
    handleStartModel,
    handleStopModel,
    handleSwitchModel,
    handleSwitchAndSetDefault,
    handleSetDefaultModel,
    handleClearDefaultModel,
    runningModelsCount,
  }
}
