import { ref, onUnmounted, type Ref } from 'vue'
import { startDownload, getDownloadStatus, cancelDownload, listDownloads } from '@/api/client'
import { useServerStore } from '@/stores/server'
import type { DownloadTask, DownloadWSMessage } from '@/types'

export function useModelDownload() {
  const serverStore = useServerStore()

  const tasks: Ref<DownloadTask[]> = ref([])
  const currentTask: Ref<DownloadTask | null> = ref(null)
  const loading = ref(false)
  const error: Ref<string | null> = ref(null)
  const wsConnected = ref(false)

  let ws: WebSocket | null = null
  let pollInterval: ReturnType<typeof setInterval> | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null

  const start = async (modelName: string, source: string = 'hf', saveDir?: string) => {
    loading.value = true
    error.value = null
    try {
      const result = await startDownload(modelName, source, saveDir)
      if ('task_id' in result) {
        currentTask.value = result as DownloadTask
      }
      return result
    } catch (e: any) {
      error.value = e.message || '下载启动失败'
      return null
    } finally {
      loading.value = false
    }
  }

  const getStatus = async (taskId: string) => {
    try {
      currentTask.value = await getDownloadStatus(taskId)
      return currentTask.value
    } catch (e: any) {
      error.value = e.message || '获取状态失败'
      return null
    }
  }

  const cancel = async (taskId: string) => {
    try {
      return await cancelDownload(taskId)
    } catch (e: any) {
      error.value = e.message || '取消下载失败'
      return null
    }
  }

  const list = async () => {
    try {
      tasks.value = await listDownloads()
      return tasks.value
    } catch (e: any) {
      error.value = e.message || '获取下载列表失败'
      return []
    }
  }

  const handleWSMessage = (msg: DownloadWSMessage) => {
    const updateTask = (taskData: Partial<DownloadTask> & { task_id: string }) => {
      if (currentTask.value && currentTask.value.task_id === taskData.task_id) {
        currentTask.value = { ...currentTask.value, ...taskData } as DownloadTask
      }
      const idx = tasks.value.findIndex(t => t.task_id === taskData.task_id)
      if (idx >= 0) {
        tasks.value[idx] = { ...tasks.value[idx], ...taskData } as DownloadTask
      } else {
        tasks.value.push(taskData as DownloadTask)
      }
    }

    switch (msg.event) {
      case 'download_started':
        updateTask({
          task_id: msg.task_id,
          model_name: msg.model_name ?? '',
          status: 'downloading',
          progress_pct: 0,
        })
        break
      case 'download_progress':
        updateTask({
          task_id: msg.task_id,
          status: 'downloading',
          progress_pct: msg.progress_pct ?? 0,
          speed_mbps: msg.speed_mbps ?? 0,
          eta_seconds: msg.eta_seconds ?? 0,
          downloaded_bytes: msg.downloaded_bytes ?? 0,
          total_bytes: msg.total_bytes ?? 0,
        })
        break
      case 'download_completed':
        updateTask({
          task_id: msg.task_id,
          status: 'completed',
          progress_pct: 100,
        })
        break
      case 'download_failed':
        updateTask({
          task_id: msg.task_id,
          status: 'failed',
          error_message: msg.error_message ?? '下载失败',
        })
        break
    }
  }

  const connectDownloadWS = () => {
    if (ws && ws.readyState === WebSocket.OPEN) return

    const base = serverStore.activeUrl || window.location.origin
    const wsUrl = base.replace(/^http/, 'ws') + '/ws/download'

    try {
      ws = new WebSocket(wsUrl)
    } catch (e) {
      console.warn('[useModelDownload] WS connect error:', e)
      startPolling()
      return
    }

    ws.onopen = () => {
      wsConnected.value = true
      stopPolling()
    }

    ws.onmessage = (event) => {
      try {
        const msg: DownloadWSMessage = JSON.parse(event.data)
        handleWSMessage(msg)
      } catch (e) {
        console.warn('[useModelDownload] WS parse error:', e)
      }
    }

    ws.onclose = () => {
      wsConnected.value = false
      if (!ws) return
      reconnectTimer = setTimeout(() => {
        connectDownloadWS()
      }, 3000)
      startPolling()
    }

    ws.onerror = () => {
      wsConnected.value = false
      startPolling()
    }
  }

  const disconnectWS = () => {
    if (ws) {
      ws.close()
      ws = null
    }
    wsConnected.value = false
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  const startPolling = () => {
    if (pollInterval) return
    pollInterval = setInterval(async () => {
      if (currentTask.value && currentTask.value.status === 'downloading') {
        await getStatus(currentTask.value.task_id)
      }
      await list()
    }, 3000)
  }

  const stopPolling = () => {
    if (pollInterval) {
      clearInterval(pollInterval)
      pollInterval = null
    }
  }

  onUnmounted(() => {
    disconnectWS()
    stopPolling()
  })

  return {
    tasks,
    currentTask,
    loading,
    error,
    wsConnected,
    start,
    getStatus,
    cancel,
    list,
    connectDownloadWS,
    disconnectWS,
  }
}
