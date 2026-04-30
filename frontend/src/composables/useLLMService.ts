import { ref, type Ref } from 'vue'
import { startModel, stopModel, getLLMServiceStatus, getLLMServiceLogs, loadFromPool } from '@/api/client'

export interface LLMServiceEntry {
  running: boolean
  engine: string
  port: number | null
  pid: number | null
  started_at: string | null
}

export function useLLMService() {
  const services: Ref<Record<string, LLMServiceEntry>> = ref({})
  const logs: Ref<string[]> = ref([])
  const loading = ref(false)
  const error: Ref<string | null> = ref(null)

  const getStatus = async () => {
    loading.value = true
    error.value = null
    try {
      services.value = await getLLMServiceStatus()
    } catch (e: any) {
      error.value = e.message || '获取服务状态失败'
      services.value = {}
    } finally {
      loading.value = false
    }
  }

  const getLogs = async (lines: number = 100) => {
    loading.value = true
    error.value = null
    try {
      const result = await getLLMServiceLogs(lines)
      logs.value = result.logs
    } catch (e: any) {
      error.value = e.message || '获取日志失败'
      logs.value = []
    } finally {
      loading.value = false
    }
  }

  const start = async (modelName: string) => {
    loading.value = true
    error.value = null
    try {
      return await startModel(modelName)
    } catch (e: any) {
      error.value = e.message || '启动服务失败'
      return null
    } finally {
      loading.value = false
    }
  }

  const stop = async (modelName: string) => {
    loading.value = true
    error.value = null
    try {
      return await stopModel(modelName)
    } catch (e: any) {
      error.value = e.message || '停止服务失败'
      return null
    } finally {
      loading.value = false
    }
  }

  const loadFromPoolService = async (modelKey: string, engine: string = 'vllm') => {
    loading.value = true
    error.value = null
    try {
      return await loadFromPool(modelKey, engine)
    } catch (e: any) {
      error.value = e.message || '从池加载模型失败'
      return null
    } finally {
      loading.value = false
    }
  }

  return { services, logs, loading, error, getStatus, getLogs, start, stop, loadFromPoolService }
}
