import { ref, onMounted, onUnmounted, computed } from 'vue'
import {
  getModelsStatus,
  getDefaultModel,
  setDefaultModel,
  clearDefaultModel,
  getAggregatedModels,
  updateModelVLLMConfig,
  atomicSwitchModel,
  getSwitchStatus,
  enablePreload,
  disablePreload,
  startModel,
  stopModel,
} from '@/api/client'
import type { ModelStatus, AggregatedModelsResponse, VLLMConfigUpdateRequest, SwitchSession } from '@/types'
import { isAbortError } from '@/utils/request'

type SwitchNotice = {
  type: 'info' | 'success' | 'error'
  message: string
  detail?: string
}

export function useModels() {
  const modelStatus = ref<ModelStatus | null>(null)
  const aggregatedModels = ref<AggregatedModelsResponse | null>(null)
  const defaultModel = ref<string | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const actionLoading = ref<string | null>(null)
  const switchingModel = ref<string | null>(null)
  const switchSession = ref<SwitchSession | null>(null)
  const switchNotice = ref<SwitchNotice | null>(null)
  const isRefreshing = ref(false)
  let refreshInterval: number | null = null
  let statusFetchController: AbortController | null = null
  let aggregatedFetchController: AbortController | null = null
  let switchPollToken = 0

  const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms))

  const isTerminalSwitchSession = (session: SwitchSession) =>
    session.completed_successfully ||
    session.overall_phase === 'completed' ||
    session.overall_phase === 'failed' ||
    session.overall_phase === 'rolled_back'

  const buildRollbackMessage = (session: SwitchSession) => {
    const rollbackTarget = session.previous_model || '原模型'
    const reason = session.rollback_reason || session.error || '切换失败'
    return `切换到 ${session.target_model} 失败，已自动回滚到 ${rollbackTarget}: ${reason}`
  }

  const waitForSwitchTerminal = async (sessionId: string | undefined, targetModel: string, token: number) => {
    const deadline = Date.now() + 15 * 60 * 1000
    let seenSession = false

    while (Date.now() < deadline && switchPollToken === token) {
      const status = await getSwitchStatus()
      const session = status.session
      if (session && (!sessionId || session.session_id === sessionId || session.target_model === targetModel)) {
        seenSession = true
        switchSession.value = session

        if (isTerminalSwitchSession(session)) {
          if (session.completed_successfully || session.overall_phase === 'completed') {
            return session
          }
          throw new Error(buildRollbackMessage(session))
        }
      }

      if (!status.is_switching && seenSession && session) {
        throw new Error(buildRollbackMessage(session))
      }

      await sleep(2000)
    }

    throw new Error(`切换到 ${targetModel} 超时，请稍后刷新状态确认`)
  }

  const fetchModelStatus = async (manualRefresh = false) => {
    if (statusFetchController) {
      if (!manualRefresh) return
      statusFetchController.abort()
    }

    const controller = new AbortController()
    statusFetchController = controller

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
      if (statusFetchController === controller) {
        statusFetchController = null
        loading.value = false
        isRefreshing.value = false
      }
    }
  }

  const fetchAggregatedModels = async (manualRefresh = false) => {
    if (aggregatedFetchController) {
      if (!manualRefresh) return
      aggregatedFetchController.abort()
    }

    const controller = new AbortController()
    aggregatedFetchController = controller

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
      if (aggregatedFetchController === controller) {
        aggregatedFetchController = null
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
    switchSession.value = null
    switchNotice.value = {
      type: 'info',
      message: `正在切换到 ${modelName}`,
      detail: '等待后端原子切换完成，页面会在成功后立即刷新',
    }
    error.value = null
    const token = ++switchPollToken
    try {
      const result = await atomicSwitchModel(modelName, setAsDefault, 'switch')
      const session = await waitForSwitchTerminal(result.session_id, modelName, token)
      if (setAsDefault) {
        defaultModel.value = modelName
      }
      switchNotice.value = {
        type: 'success',
        message: `已切换到 ${session.target_model}`,
        detail: '当前运行模型已刷新',
      }
      await Promise.all([
        fetchModelStatus(true),
        fetchAggregatedModels(true),
      ])
    } catch (err) {
      const message = err instanceof Error ? err.message : `切换失败`
      error.value = message
      switchNotice.value = {
        type: 'error',
        message,
        detail: '后端已按原子切换策略恢复原模型',
      }
      console.error('Failed to switch model:', err)
      await Promise.allSettled([
        fetchModelStatus(true),
        fetchAggregatedModels(true),
      ])
      throw err
    } finally {
      if (switchPollToken === token) {
        actionLoading.value = null
        switchingModel.value = null
      }
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
    if (statusFetchController) {
      statusFetchController.abort()
      statusFetchController = null
    }
    if (aggregatedFetchController) {
      aggregatedFetchController.abort()
      aggregatedFetchController = null
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
    switchPollToken++
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
    switchSession,
    switchNotice,
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
