import { ref, type Ref } from 'vue'
import { getHealthAlert, healthCheck, getHealthDetailed, getHealthHistory } from '@/api/client'
import type { HealthAlert, HealthDetail, HealthHistoryEntry } from '@/types'

export function useHealthOps() {
  const healthAlert: Ref<HealthAlert | null> = ref(null)
  const healthDetail: Ref<HealthDetail | null> = ref(null)
  const healthHistory: Ref<HealthHistoryEntry[]> = ref([])
  const loading = ref(false)
  const error: Ref<string | null> = ref(null)

  const fetchAlert = async () => {
    loading.value = true
    error.value = null
    try {
      healthAlert.value = await getHealthAlert()
    } catch (e: unknown) {
      error.value = (e as Error).message || '获取健康告警失败'
      healthAlert.value = null
    } finally {
      loading.value = false
    }
  }

  const fetchDetail = async () => {
    loading.value = true
    error.value = null
    try {
      healthDetail.value = await getHealthDetailed()
    } catch (e: unknown) {
      error.value = (e as Error).message || '获取健康详情失败'
      healthDetail.value = null
    } finally {
      loading.value = false
    }
  }

  const fetchHistory = async () => {
    loading.value = true
    error.value = null
    try {
      healthHistory.value = await getHealthHistory()
    } catch (e: unknown) {
      error.value = (e as Error).message || '获取健康历史失败'
      healthHistory.value = []
    } finally {
      loading.value = false
    }
  }

  const runCheck = async () => {
    loading.value = true
    error.value = null
    try {
      await healthCheck()
      await fetchAlert()
      await fetchDetail()
    } catch (e: unknown) {
      error.value = (e as Error).message || '执行健康检查失败'
    } finally {
      loading.value = false
    }
  }

  return {
    healthAlert,
    healthDetail,
    healthHistory,
    loading,
    error,
    fetchAlert,
    fetchDetail,
    fetchHistory,
    runCheck,
  }
}
