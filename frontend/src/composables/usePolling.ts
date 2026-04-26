import { ref, onMounted, onUnmounted } from 'vue'

export function usePolling(fetchFn: () => Promise<void>, intervalMs: number) {
  const loading = ref(false)
  const isRefreshing = ref(false)
  const error = ref<string | null>(null)
  let timer: number | null = null

  const fetch = async (manualRefresh = false) => {
    if (manualRefresh) {
      isRefreshing.value = true
    } else {
      loading.value = true
    }
    error.value = null
    try {
      await fetchFn()
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch data'
    } finally {
      loading.value = false
      isRefreshing.value = false
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
