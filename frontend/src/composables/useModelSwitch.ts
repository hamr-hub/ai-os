import { ref, computed, onUnmounted } from 'vue'
import type { SwitchSession, SwitchProgressMessage, SwitchLogLevel } from '@/types'
import { getSwitchStatus, atomicSwitchModel, cancelSwitch } from '@/api/client'
import { useServerStore } from '@/stores/server'
import { useAppStore } from '@/stores/app'

export function useModelSwitch() {
  const serverStore = useServerStore()
  const appStore = useAppStore()

  const isSwitching = ref(false)
  const currentSession = ref<SwitchSession | null>(null)
  const latestLog = ref<string>('')
  const latestLogLevel = ref<SwitchLogLevel>('info')
  const wsConnected = ref(false)
  const error = ref<string | null>(null)

  let ws: WebSocket | null = null
  let pollInterval: number | null = null
  let pollFallbackTimer: number | null = null

  const overallProgress = computed(() => currentSession.value?.overall_progress ?? 0)
  const overallPhase = computed(() => currentSession.value?.overall_phase ?? 'idle')
  const phases = computed(() => currentSession.value?.phases ?? [])
  const isRollingBack = computed(() =>
    overallPhase.value === 'rolling_back' || overallPhase.value === 'rolled_back'
  )
  const isCompleted = computed(() => overallPhase.value === 'completed')
  const isFailed = computed(() =>
    overallPhase.value === 'failed' || overallPhase.value === 'rolled_back'
  )

  const connectWS = () => {
    if (ws && ws.readyState === WebSocket.OPEN) return

    const base = serverStore.activeUrl || window.location.origin
    const wsUrl = base.replace(/^http/, 'ws') + '/ws/model-switch'

    try {
      ws = new WebSocket(wsUrl)
    } catch (e) {
      console.warn('[useModelSwitch] WS connect error:', e)
      return
    }

    ws.onopen = () => {
      wsConnected.value = true
      stopPolling()
    }

    ws.onmessage = (event) => {
      try {
        const msg: SwitchProgressMessage = JSON.parse(event.data)
        handleMessage(msg)
      } catch (e) {
        console.warn('[useModelSwitch] WS parse error:', e)
      }
    }

    ws.onclose = () => {
      wsConnected.value = false
      if (isSwitching.value) {
        startPolling()
      }
    }

    ws.onerror = () => {
      wsConnected.value = false
      if (isSwitching.value) {
        startPolling()
      }
    }

    pollFallbackTimer = window.setTimeout(() => {
      if (!wsConnected.value && isSwitching.value) {
        startPolling()
      }
    }, 5000)
  }

  const disconnectWS = () => {
    if (ws) {
      ws.close()
      ws = null
    }
    wsConnected.value = false
    if (pollFallbackTimer) {
      clearTimeout(pollFallbackTimer)
      pollFallbackTimer = null
    }
  }

  const handleMessage = (msg: SwitchProgressMessage) => {
    if (msg.type === 'switch_state_sync') {
      if (msg.session) {
        currentSession.value = msg.session
        if (isTerminalPhase(msg.session.overall_phase)) {
          isSwitching.value = false
          stopPolling()
        } else {
          isSwitching.value = msg.is_switching ?? true
        }
      }
      return
    }

    latestLog.value = msg.log
    latestLogLevel.value = msg.level

    if (msg.session) {
      currentSession.value = msg.session
    } else if (currentSession.value && msg.session_id === currentSession.value.session_id) {
      currentSession.value = {
        ...currentSession.value,
        overall_phase: msg.overall_phase,
        overall_progress: msg.overall_progress,
      }
    }

    if (msg.final) {
      isSwitching.value = false
      stopPolling()

      if (msg.overall_phase === 'completed') {
        appStore.success(`模型 ${msg.target_model} 切换成功`)
      } else if (msg.overall_phase === 'rolled_back' || msg.type === 'switch_failed') {
        const errMsg = currentSession.value?.rollback_reason || currentSession.value?.error || '切换失败'
        appStore.error(`模型切换失败: ${errMsg}`)
        error.value = errMsg
      }
    }
  }

  const isTerminalPhase = (phase: string) =>
    phase === 'completed' || phase === 'failed' || phase === 'rolled_back' || phase === 'idle'

  const startPolling = () => {
    if (pollInterval || wsConnected.value) return
    pollInterval = window.setInterval(async () => {
      try {
        const status = await getSwitchStatus()

        if (!status.is_switching && isSwitching.value) {
          isSwitching.value = false
          stopPolling()
          disconnectWS()
          return
        }

        isSwitching.value = status.is_switching
        if (status.session) {
          currentSession.value = status.session

          if (isTerminalPhase(status.session.overall_phase)) {
            isSwitching.value = false
            stopPolling()
            disconnectWS()

            if (status.session.completed_successfully) {
              appStore.success(`模型 ${status.session.target_model} 切换成功`)
            } else if (status.session.overall_phase === 'rolled_back' || status.session.overall_phase === 'failed') {
              const errMsg = status.session.rollback_reason || status.session.error || '切换失败'
              appStore.error(`模型切换失败: ${errMsg}`)
              error.value = errMsg
            } else if (status.session.overall_phase === 'completed') {
              appStore.success(`模型 ${status.session.target_model} 切换成功`)
            }
            return
          }
        }
      } catch (e) {
        console.warn('[useModelSwitch] Poll error:', e)
      }
    }, 2000)
  }

  const stopPolling = () => {
    if (pollInterval) {
      clearInterval(pollInterval)
      pollInterval = null
    }
  }

  const triggerSwitch = async (
    modelName: string,
    setAsDefault = false,
    action: 'switch' | 'start' | 'stop' = 'switch'
  ) => {
    error.value = null
    isSwitching.value = true

    try {
      await atomicSwitchModel(modelName, setAsDefault, action)
    } catch (err) {
      isSwitching.value = false
      const errMsg = err instanceof Error ? err.message : '切换请求失败'
      error.value = errMsg
      appStore.error(`模型切换请求失败: ${errMsg}`)
      return
    }

    connectWS()
  }

  const triggerCancel = async () => {
    error.value = null
    try {
      await cancelSwitch()
    } catch (err) {
      console.warn('[useModelSwitch] Cancel request failed:', err)
    }
    isSwitching.value = false
    stopPolling()
    disconnectWS()
  }

  const initSwitchMonitor = () => {
    getSwitchStatus().then((status) => {
      if (status.is_switching && status.session) {
        if (isTerminalPhase(status.session.overall_phase)) {
          isSwitching.value = false
          currentSession.value = status.session
          return
        }
        isSwitching.value = true
        currentSession.value = status.session
        connectWS()
      } else if (status.session && isTerminalPhase(status.session.overall_phase)) {
        currentSession.value = status.session
        isSwitching.value = false
      } else {
        isSwitching.value = false
      }
    }).catch(() => {})
  }

  onUnmounted(() => {
    disconnectWS()
    stopPolling()
  })

  return {
    isSwitching,
    currentSession,
    latestLog,
    latestLogLevel,
    overallProgress,
    overallPhase,
    phases,
    isRollingBack,
    isCompleted,
    isFailed,
    error,
    wsConnected,
    triggerSwitch,
    triggerCancel,
    connectWS,
    disconnectWS,
    startPolling,
    stopPolling,
    initSwitchMonitor,
  }
}
