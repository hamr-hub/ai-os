import { ref, onMounted, onUnmounted, computed } from 'vue'
import {
  getModelStatus,
  startModel,
  stopModel,
  switchModel,
  getDefaultModel,
  setDefaultModel,
  clearDefaultModel,
} from '@/api/client'
import type { ModelStatus } from '@/types'

export function useModels() {
  const modelStatus = ref<ModelStatus | null>(null)
  const defaultModel = ref<string | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const actionLoading = ref<string | null>(null)
  const isRefreshing = ref(false)
  let refreshInterval: number | null = null

  const fetchModelStatus = async (manualRefresh = false) => {
    if (manualRefresh) {
      isRefreshing.value = true
    } else {
      loading.value = true
    }
    error.value = null
    try {
      modelStatus.value = await getModelStatus()
      const defaultModelResult = await getDefaultModel()
      defaultModel.value = defaultModelResult.default_model
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch model status'
      console.error('Failed to fetch model status:', err)
    } finally {
      loading.value = false
      isRefreshing.value = false
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
    actionLoading.value = modelName
    error.value = null
    try {
      await startModel(modelName)
      await fetchModelStatus()
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
      await fetchModelStatus()
    } catch (err) {
      error.value = err instanceof Error ? err.message : `Failed to stop model ${modelName}`
      console.error('Failed to stop model:', err)
    } finally {
      actionLoading.value = null
    }
  }

  const handleSwitchModel = async (modelName: string, setAsDefault = false) => {
    actionLoading.value = modelName
    error.value = null
    try {
      await switchModel(modelName)
      if (setAsDefault) {
        await setDefaultModel(modelName)
        defaultModel.value = modelName
      }
      await fetchModelStatus()
    } catch (err) {
      error.value = err instanceof Error ? err.message : `Failed to switch to model ${modelName}`
      console.error('Failed to switch model:', err)
    } finally {
      actionLoading.value = null
    }
  }

  const handleSwitchAndSetDefault = async (modelName: string) => {
    await handleSwitchModel(modelName, true)
  }

  const startAutoRefresh = () => {
    if (refreshInterval) return
    refreshInterval =