import { ref, type Ref } from 'vue'
import { getHealthAlert, healthCheck, getHealthDetailed, getHealthHistory } from '@/api/client'
import type { HealthAlert, HealthDetail, HealthHistoryEntry, GoHealthDetail } from '@/types'

interface RawGoHealthHistory {
  timestamp?: string
  health_score?: number
  status?: string
  source?: string
}

const normalizeHealthDetail = (raw: GoHealthDetail): HealthDetail | null => {
  if (!raw) return null

  const scores = raw.scores || {}
  const gpu = raw.gpu || {}
  const alerts = scores.alerts || []
  const engines = raw.engines || {}
  const vllmEngine = engines['vllm'] || {}
  const models = raw.models || {}
  const vllmActiveRequests = Object.values(models).reduce(
    (sum: number, m: any) => sum + (m.active_requests || 0), 0
  )

  return {
    overall_score: scores.overall ?? 0,
    status: scores.status ?? 'healthy',
    checks: {
      gpu: {
        available: gpu.status === 'available' || gpu.gpu_count > 0,
        utilization: gpu.utilization ?? 0,
        temperature: gpu.temperature ?? 0,
        memory_used_pct: gpu.memory_utilization ?? 0,
      },
      go_backend: {
        reachable: true,
        response_time_ms: scores.response_time ?? 0,
      },
      python_backend: {
        reachable: true,
        response_time_ms: 0,
      },
      vllm_service: {
        running: vllmEngine.running ?? false,
        active_requests: vllmActiveRequests,
      },
      redis: {
        available: raw.redis ?? false,
        connected: raw.redis ?? false,
      },
    },
    alert_reasons: Array.isArray(alerts) ? alerts.map((a: any) => a.message || String(a.type)) : [],
    timestamp: raw.timestamp ?? new Date().toISOString(),
  }
}

const normalizeHealthHistory = (payload: unknown): HealthHistoryEntry[] => {
  if (!payload) return []
  if (Array.isArray(payload)) {
    return payload.map((entry) => {
      const raw = entry as RawGoHealthHistory
      return {
        timestamp: raw.timestamp || '',
        health_score: raw.health_score ?? 0,
        status: raw.status || 'unknown',
        alert_count: 0,
      }
    })
  }
  return []
}

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
      const raw = await getHealthDetailed()
      healthDetail.value = normalizeHealthDetail(raw)
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
      const raw = await getHealthHistory()
      healthHistory.value = normalizeHealthHistory(raw)
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
