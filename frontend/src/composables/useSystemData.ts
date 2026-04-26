import { ref, computed, toValue, type MaybeRefOrGetter } from 'vue'
import { getSystemStatus, getHealthAlert, getSystemHistory, getQueueStatus } from '@/api/client'
import { usePolling } from '@/composables/usePolling'
import type { SystemStatus, HealthAlert, QueueStatus, SystemHistoryEntry } from '@/types'

export function useSystemData(intervalMs = 10000, initialCount: MaybeRefOrGetter<number> = 60) {
  const systemStatus = ref<SystemStatus | null>(null)
  const healthAlert = ref<HealthAlert | null>(null)
  const systemHistory = ref<SystemHistoryEntry[]>([])
  const queueStatusRef = ref<QueueStatus | null>(null)

  const { loading, isRefreshing, error, refresh } = usePolling(
    async () => {
      try {
        const status = await getSystemStatus()
        systemStatus.value = status
        if (status.queue) {
          queueStatusRef.value = status.queue
        } else {
          try {
            queueStatusRef.value = await getQueueStatus()
          } catch (err) {
            console.warn('[useSystemData] Queue status fetch failed:', err)
            queueStatusRef.value = null
          }
        }
      } catch {
        if (!systemStatus.value) {
          systemStatus.value = null
        }
      }

      const [healthResult, historyResult] = await Promise.allSettled([
        getHealthAlert(),
        getSystemHistory(toValue(initialCount)),
      ])

      if (healthResult.status === 'fulfilled') {
        healthAlert.value = healthResult.value
      }

      if (historyResult.status === 'fulfilled') {
        systemHistory.value = historyResult.value.history
      }
    },
    intervalMs
  )

  const queueStatus = computed(() => queueStatusRef.value)

  return {
    systemStatus,
    queueStatus,
    healthAlert,
    systemHistory,
    loading,
    isRefreshing,
    error,
    refresh,
  }
}
