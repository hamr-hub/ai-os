import { ref, onMounted, onUnmounted } from 'vue'
import { isAbortError } from '@/utils/request'

export function usePolling(fetchFn: (signal: AbortSignal) => Promise<void>, intervalMs: number) {
  const loading = ref(false)
  const isRefreshing = ref(false)
  const error = ref<string | null>(null)
  let timer: number | null = null
  let activeController: AbortController | null = null

  const fetch = async (manualRefresh = false) => {
    if (activeController) {
      if (!manualRefresh) return
      activeController.abort()
    }

    const controller = new AbortController()
    activeController = controller

    if (manualRefresh) {
      isRefreshing.value = true
    } else {
      loading.value = true
    }
    error.value = null
    try {
      await fetchFn(controller.signal)
    } catch (err) {
      if (!isAbortError(err)) {
        error.value = err instanceof Error ? err.message : 'Failed to fetch data'
      }
    } finally {
      if (activeController === controller) {
        activeController = null
        loading.value = false
        isRefreshing.value = false
      }
    }
  }

  const refresh = () => fetch(true)

  const startPolling = () => {
    if (timer) return
    timer = window.setInterval(() => fetch(), intervalMs)
  }

  const stopPolling = () => {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
    if (activeController) {
      activeController.abort()
      activeController = null
    }
  }

  onMounted(() => {
    fetch()
    startPolling()
  })

  onUnmounted(() => {
    stopPolling()
  })

  return {
    loading,
    isRefreshing,
    error,
    fetch,
    refresh,
    startPolling,
    stopPolling,
  }
}
