import { ref, onMounted, onUnmounted, computed } from 'vue'
import {
  getModelsStatus,
  getDefaultModel,
  setDefaultModel,
  clearDefaultModel,
  getAggregatedModels,
  updateModelVLLMConfig,
  atomicSwitchModel,
  enablePreload,
  disablePreload,
  startModel,
  stopModel,
} from '@/api/client'
import type { ModelStatus, AggregatedModelsResponse, VLLMConfigUpdateRequest } from '@/types'
import { isAbortError } from '@/utils/request'

export function useModels() {
  const modelStatus = ref<ModelStatus | null>(null)
  const aggregatedModels = ref<AggregatedModelsResponse | null>(null)
  const defaultModel = ref<string | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const actionLoading = ref<string | null>(null)
  const switchingModel = ref<string | null>(null)
  const isRefreshing = ref(false)
  let refreshInterval: number | null = null
  let fetchController: AbortController | null = null

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

  const fetchAggregatedModels = async (manualRefresh = false) => {
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
      const [aggregated, defaultModelResult] = await Promise.all([
        getAggregatedModels({ signal: controller.signal }),
        getDefaultModel({ signal: controller.signal }),
      ])
      aggregatedModels.value = aggregated
      defaultModel.value = defaultModelResult.default_model
    } catch (err) {
      if (isAbortError(err)) return
      error.value = err instanceof Error ? err.message : 'Failed to fetch aggregated models'
      if (manualRefresh) {
        console.error('Failed to fetch aggregated models:', err)
      }
    } finally {
      if (fetchController === controller) {
        fetchController = null
        loading.value = false
        isRefreshing.value = false
      }
    }
  }

  const saveVLLMParams = async (modelName: string, config: VLLMConfigUpdateRequest) => {
    actionLoading.value = modelName
    error.value = null
    try {
      await updateModelVLLMConfig(modelName, config)
      await fetchAggregatedModels(true)
    } catch (err) {
      error.value = err instanceof Error ? err.message : `Failed to save vLLM params for ${modelName}`
      console.error('Failed to save vLLM params:', err)
    } finally {
      actionLoading.value = null
    }
  }

  const refresh = () => {
    Promise.all([
      fetchModelStatus(true),
      fetchAggregatedModels(true),
    ])
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
    actionLoading.value = modelName
    error.value = null
    try {
      await startModel(modelName)
      await Promise.all([
        fetchModelStatus(true),
        fetchAggregatedModels(true),
      ])
    } catch (err) {
      error.value = err instanceof Error ? err.message : `Failed to start model ${modelName}`
      console.error('Failed to start model:', err)
    } finally {
      actionLoading.value = null
    }
  }

  const handleStopModel = async (modelName: string) => {
    actionLoading.value = modelName
    error.value = null
    try {
      await stopModel(modelName)
      await Promise.all([
        fetchModelStatus(true),
        fetchAggregatedModels(true),
      ])
    } catch (err) {
      error.value = err instanceof Error ? err.message : `Failed to stop model ${modelName}`
      console.error('Failed to stop model:', err)
    } finally {
      actionLoading.value = null
    }
  }

  const handleSwitchModel = async (modelName: string, setAsDefault = false) => {
    actionLoading.value = modelName
    switchingModel.value = modelName
    error.value = null
    try {
      await atomicSwitchModel(modelName, setAsDefault, 'switch')
      if (setAsDefault) {
        defaultModel.value = modelName
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : `切换失败`
      console.error('Failed to switch model:', err)
    } finally {
      actionLoading.value = null
      switchingModel.value = null
    }
  }

  const handleSwitchAndSetDefault = async (modelName: string) => {
    await handleSwitchModel(modelName, true)
  }

  const handleTogglePreload = async (modelName: string, enabled: boolean) => {
    actionLoading.value = modelName
    error.value = null
    try {
      if (enabled) {
        await enablePreload(modelName)
      } else {
        await disablePreload(modelName)
      }
      await fetchModelStatus(true)
    } catch (err) {
      error.value = err instanceof Error ? err.message : `预加载设置失败`
      console.error('Failed to toggle preload:', err)
    } finally {
      actionLoading.value = null
    }
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
    fetchAggregatedModels()
    startAutoRefresh()
  })

  onUnmounted(() => {
    stopAutoRefresh()
  })

  return {
    modelStatus,
    aggregatedModels,
    modelList,
    defaultModel,
    loading,
    error,
    actionLoading,
    switchingModel,
    isRefreshing,
    isAutoRefreshEnabled,
    fetchModelStatus,
    fetchAggregatedModels,
    saveVLLMParams,
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
    handleTogglePreload,
    runningModelsCount,
  }
}
