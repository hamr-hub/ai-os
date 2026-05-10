import axios, { type AxiosRequestConfig } from 'axios'
import type {
  GPUSummary,
  GPUHistoryEntry,
  GPUProcess,
  GPUEnhancedInfo,
  VLLMMetricsData,
  ModelStatus,
  ModelInfo,
  ActionResponse,
  TestResponse,
  TestHistoryEntry,
  TokenStats,
  TokenHistoryResponse,
  SystemHistoryResponse,
  SystemStatus,
  QueueStatus,
  HealthAlert,
  ChatMessage,
  ChatCompletionRequest,
  ChatCompletionResponse,
  AgentToolCall,
  AgentMessage,
  AgentRequest,
  ToolResult,
  AggregatedModelsResponse,
  VLLMDefaultConfig,
  VLLMConfig,
  VLLMConfigUpdateRequest,
  SwitchStatusResponse,
  SearchResult,
  RecommendResult,
  DownloadTask,
  PoolListResponse,
  PoolEntry,
  MemoryCheckResult,
  EngineType,
  EngineStatus,
  EngineConfig,
  EngineParamSchema,
  ModelEngineParams,
  GPUMemoryInfo,
  GPURecommendInfo,
  RateLimitConfig,
  RateLimitStats,
  SystemConfig,
  GoHealthDetail,
  HealthHistoryEntry,
} from '@/types'
import { useServerStore } from '@/stores/server'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import { readSSEStream, DONE_SENTINEL } from '@/utils/sse'
import { buildStreamErrorMessage } from '@/utils/connection'

const client = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

const v1Client = axios.create({
  baseURL: '/v1',
  timeout: 60000,
})

type RetryableConfig = AxiosRequestConfig & {
  __retryCount?: number
  suppressGlobalErrorToast?: boolean
}

const RETRYABLE_METHODS = new Set(['get', 'head', 'options'])

const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms))
const silentRequestConfig = (config: AxiosRequestConfig = {}): RetryableConfig => ({
  ...config,
  suppressGlobalErrorToast: true,
})

const shouldRetryRequest = (error: unknown): boolean => {
  if (axios.isCancel(error)) {
    return false
  }

  const err = error as {
    code?: string
    response?: { status?: number }
    config?: RetryableConfig
  }
  const method = err.config?.method?.toLowerCase() ?? 'get'

  if (!RETRYABLE_METHODS.has(method)) {
    return false
  }

  if (!err.response) {
    return true
  }

  const status = err.response.status ?? 0
  return status === 408 || status === 425 || status === 429 || status >= 500
}

const normalizeErrorMessage = (error: unknown) => {
  const err = error as {
    code?: string
    response?: { status?: number; data?: unknown }
    message?: string
  }
  const data = err.response?.data as Record<string, unknown> | undefined
  const explicitMessage =
    (data?.message as string) || (data?.error as string) || err.message || 'API Request Failed'

  if (err.code === 'ECONNABORTED') {
    return '请求超时，请稍后重试'
  }

  if (!err.response) {
    return '网络连接异常，请检查服务状态'
  }

  if (err.response.status === 503) {
    return explicitMessage || '服务暂时不可用，请稍后重试'
  }

  return explicitMessage
}

export const getApiErrorMessage = (error: unknown) => normalizeErrorMessage(error)

const attachRetryInterceptor = (instance: typeof client) => {
  instance.interceptors.response.use(undefined, async (error) => {
    const config = (error as { config?: RetryableConfig }).config
    const retryCount = config?.__retryCount ?? 0

    if (config && retryCount < 2 && shouldRetryRequest(error)) {
      config.__retryCount = retryCount + 1
      await sleep(250 * config.__retryCount)
      return instance(config)
    }

    return Promise.reject(error)
  })
}

client.interceptors.request.use((config) => {
  const serverStore = useServerStore()
  const authStore = useAuthStore()
  config.baseURL = serverStore.manageBase
  if (authStore.token) {
    config.headers = config.headers || {}
    config.headers['Authorization'] = `Bearer ${authStore.token}`
  }
  return config
})

v1Client.interceptors.request.use((config) => {
  const serverStore = useServerStore()
  const authStore = useAuthStore()
  config.baseURL = serverStore.v1Base
  if (authStore.token) {
    config.headers = config.headers || {}
    config.headers['Authorization'] = `Bearer ${authStore.token}`
  }
  return config
})

const handleResponseError = (error: unknown) => {
  const config = (error as { config?: RetryableConfig }).config
  const appStore = useAppStore()
  const err = error as { response?: { status?: number; data?: { error?: string; client_ip?: string } } }

  if (axios.isCancel(error)) {
    return Promise.reject(error)
  }

  if (err.response?.status === 403) {
    const errMsg = err.response.data?.error || 'admin write operations require internal network access'
    if (errMsg.includes('admin write') || errMsg.includes('whitelist') || errMsg.includes('internal network')) {
      window.location.hash = '#/blocked'
      return Promise.reject(error)
    }
  }

  if (!config?.suppressGlobalErrorToast) {
    appStore.error(normalizeErrorMessage(error))
  }
  return Promise.reject(error)
}

attachRetryInterceptor(client)
attachRetryInterceptor(v1Client)

client.interceptors.response.use((response) => response, handleResponseError)

v1Client.interceptors.response.use((response) => response, handleResponseError)

export async function getGPUSummary(config: AxiosRequestConfig = {}): Promise<GPUSummary> {
  const { data } = await client.get<GPUSummary>('/gpu/summary', silentRequestConfig(config))
  return data
}

export async function getGPUEnhancedInfo(): Promise<GPUEnhancedInfo> {
  const { data } = await client.get<GPUEnhancedInfo>('/gpu/enhanced', silentRequestConfig())
  return data
}

export async function getGPUProcesses(): Promise<{ processes: GPUProcess[]; count: number }> {
  const { data } = await client.get<{ processes: GPUProcess[]; count: number }>(
    '/gpu/processes',
    silentRequestConfig()
  )
  return data
}

export async function getVLLMMetrics(config: AxiosRequestConfig = {}): Promise<VLLMMetricsData> {
  const { data } = await client.get<VLLMMetricsData>('/vllm/metrics', silentRequestConfig(config))
  return data
}

export async function getModelsStatus(config: AxiosRequestConfig = {}): Promise<ModelStatus> {
  const { data } = await client.get<ModelStatus>('/models', silentRequestConfig(config))
  return data
}

export async function getModels(config: AxiosRequestConfig = {}): Promise<{ data: ModelInfo[]; total: number }> {
  const { data } = await client.get('/models/pool', {
    params: { filter: 'all', page: 1, page_size: 200 },
    timeout: config.timeout || 10000,
    ...config,
  })
  const models = data.models || data.items || []
  const items: ModelInfo[] = models.map((entry: any) => ({
    id: entry.name || entry.id || '',
    owned_by: entry.source || 'system',
    running: entry.running_status === 'running' || entry.is_running === true,
  }))
  return { data: items, total: data.total || items.length }
}

export async function startModel(name: string): Promise<ActionResponse> {
  const data = await atomicSwitchModel(name, false, 'start')
  return data
}

export async function stopModel(name: string): Promise<ActionResponse> {
  const data = await atomicSwitchModel(name, false, 'stop')
  return data
}

export async function switchModel(name: string, testEnabled = true): Promise<ActionResponse> {
  void testEnabled
  const { data } = await client.post<ActionResponse>('/switch/atomic', {
    action: 'switch',
    model_name: name,
    set_as_default: true,
  })
  return data
}

export async function atomicSwitchModel(
  name: string,
  setAsDefault = false,
  action: 'switch' | 'start' | 'stop' = 'switch'
): Promise<ActionResponse & { session_id?: string; target_model?: string; previous_model?: string | null; action?: string }> {
  const { data } = await client.post<
    ActionResponse & { session_id?: string; target_model?: string; previous_model?: string | null; action?: string }
  >('/switch/atomic', {
    action,
    model_name: name,
    set_as_default: setAsDefault,
  })
  return data
}

export async function enablePreload(name: string): Promise<ActionResponse> {
  const { data } = await client.post<ActionResponse>(`/preload/${encodeURIComponent(name)}/enable`)
  return data
}

export async function disablePreload(name: string): Promise<ActionResponse> {
  const { data } = await client.post<ActionResponse>(`/preload/${encodeURIComponent(name)}/disable`)
  return data
}

export async function runModelTest(name: string): Promise<TestResponse> {
  const { data } = await client.post<TestResponse>(
    `/models/${encodeURIComponent(name)}/benchmark`,
    null,
    silentRequestConfig({ timeout: 180000 })
  )
  return data
}

export async function getTestResults(name: string): Promise<TestResponse> {
  const { data } = await client.get<TestResponse>(
    `/models/${encodeURIComponent(name)}/benchmark`,
    silentRequestConfig()
  )
  return data
}

export async function getTestHistory(): Promise<TestHistoryEntry[]> {
  const { data } = await client.get<
    | { status?: string; reports?: Record<string, Record<string, unknown>>; history?: Array<Record<string, unknown>> }
    | Array<Record<string, unknown>>
  >('/models/benchmarks/history')

  const normalizeEntry = (
    modelName: string,
    report: Record<string, unknown> = {}
  ): TestHistoryEntry => ({
    model_name: modelName,
    timestamp: (report.test_timestamp as string) || (report.timestamp as string) || '',
    status:
      (report.overall_status as string) || (report.status as string) || (report.message as string) || 'unknown',
    overall_status: report.overall_status as string | undefined,
    duration: (report.resource_utilization as Record<string, unknown>)?.test_duration_seconds as
      | number
      | undefined,
  })

  if (Array.isArray(data)) {
    return data.map((entry) => normalizeEntry((entry.model_name as string) || '', entry))
  }

  const reports = data.reports || {}
  if (Object.keys(reports).length > 0) {
    return Object.entries(reports).map(([model_name, report]) => normalizeEntry(model_name, report))
  }

  const history = data.history || []
  return history.map((entry) => normalizeEntry((entry.model_name as string) || '', entry))
}

export async function getTokenStats(config: AxiosRequestConfig = {}): Promise<TokenStats> {
  const { data } = await client.get<TokenStats>('/token/stats', silentRequestConfig(config))
  return data
}

export async function getTokenHistory(
  count: number = 60,
  config: AxiosRequestConfig = {}
): Promise<TokenHistoryResponse> {
  const { data } = await client.get<TokenHistoryResponse>(
    '/token/history',
    silentRequestConfig({ params: { count }, ...config })
  )
  return data
}

export async function getGPUHistory(
  count: number = 60,
  config: AxiosRequestConfig = {}
): Promise<{ history: GPUHistoryEntry[]; count: number; enabled: boolean; max_days: number }> {
  const { data } = await client.get('/gpu/history', silentRequestConfig({ params: { count }, ...config }))
  return data
}

export async function healthCheck(): Promise<{ status: string }> {
  const { data } = await v1Client.get<{ status: string }>('/health', silentRequestConfig())
  return data
}

export async function getDefaultModel(
  config: AxiosRequestConfig = {}
): Promise<{ default_model: string | null }> {
  const { data } = await client.get<{ default_model: string | null }>(
    '/default-model',
    silentRequestConfig(config)
  )
  return data
}

export async function setDefaultModel(modelName: string): Promise<ActionResponse> {
  const { data } = await client.post<ActionResponse>(`/default-model/${modelName}`)
  return data
}

export async function clearDefaultModel(): Promise<ActionResponse> {
  const { data } = await client.delete<ActionResponse>('/default-model')
  return data
}

export async function getAggregatedModels(
  config: AxiosRequestConfig = {}
): Promise<AggregatedModelsResponse> {
  const { data } = await client.get<AggregatedModelsResponse>(
    '/models/aggregated',
    silentRequestConfig(config)
  )
  return data
}

export async function getModelVLLMConfig(
  modelName: string
): Promise<VLLMConfig> {
  const { data } = await client.get<VLLMConfig>(`/models/${modelName}/vllm-config`)
  return data
}

export async function updateModelVLLMConfig(
  modelName: string,
  config: VLLMConfigUpdateRequest
): Promise<VLLMConfig> {
  const { data } = await client.put<VLLMConfig>(`/models/${modelName}/vllm-config`, config)
  return data
}

export async function getVLLMDefaultConfig(
  config: AxiosRequestConfig = {}
): Promise<VLLMDefaultConfig> {
  const { data } = await client.get<VLLMDefaultConfig>(
    '/vllm/default-config',
    silentRequestConfig(config)
  )
  return data
}

export async function getSystemStatus(
  includeHistory = false,
  historyCount = 60,
  config: AxiosRequestConfig = {}
): Promise<SystemStatus & { history?: SystemHistoryResponse['history'] }> {
  const { data } = await client.get<SystemStatus & { history?: SystemHistoryResponse['history'] }>(
    '/system/status',
    silentRequestConfig({
      params: { include_history: includeHistory, history_count: historyCount },
      ...config,
    })
  )
  return data
}

export async function getSystemHistory(
  count: number = 60,
  config: AxiosRequestConfig = {}
): Promise<SystemHistoryResponse> {
  const { data } = await client.get<SystemHistoryResponse>(
    '/system/history',
    silentRequestConfig({ params: { count }, ...config })
  )
  return data
}

export async function getQueueStatus(config: AxiosRequestConfig = {}): Promise<QueueStatus> {
  const { data } = await client.get<QueueStatus>('/queue', silentRequestConfig(config))
  return data
}

export async function getHealthAlert(config: AxiosRequestConfig = {}): Promise<HealthAlert> {
  const { data } = await client.get<HealthAlert>('/health/alert', silentRequestConfig(config))
  return data
}

export async function chatCompletion(
  request: ChatCompletionRequest
): Promise<ChatCompletionResponse> {
  const { data } = await v1Client.post<ChatCompletionResponse>('/chat/completions', request)
  return data
}

export async function chatCompletionStream(
  request: Omit<ChatCompletionRequest, 'stream'>,
  onChunk: (content: string) => void,
  onError?: (error: Error) => void,
  signal?: AbortSignal
): Promise<void> {
  const serverStore = useServerStore()
  const authStore = useAuthStore()

  await readSSEStream({
    url: `${serverStore.v1Base}/chat/completions`,
    body: {
      ...request,
      stream: true,
      enable_thinking: false,
    },
    signal,
    timeoutMs: 30000,
    headers: authStore.token ? { Authorization: `Bearer ${authStore.token}` } : undefined,
    onChunk: (rawData) => {
      try {
        const json = JSON.parse(rawData)
        const reasoningContent = json.choices?.[0]?.delta?.reasoning_content
        if (reasoningContent) {
          // Skip reasoning content to avoid mixing with regular content
        }
        const content = json.choices?.[0]?.delta?.content
        if (content) onChunk(content)
      } catch (err) {
        if (rawData.length < 200) console.warn('[SSE] Parse skip:', rawData, err)
      }
    },
    onError: (error) => {
      const message = buildStreamErrorMessage(
        error.message,
        'inference',
        serverStore.connectionStatus,
        serverStore.connectionDetails,
        serverStore.lastErrorMessage
      )
      if (error.message.includes('reasoning_content') || error.message.includes('thinking is enabled')) {
        onError?.(new Error('模型thinking模式错误，请联系后端管理员关闭thinking模式或更新API配置'))
        return
      }
      onError?.(new Error(message))
    },
  })
}

export async function agentChatStream(
  request: Omit<AgentRequest, 'stream'>,
  onChunk: (data: unknown) => void,
  onError?: (error: Error) => void,
  signal?: AbortSignal
): Promise<void> {
  const serverStore = useServerStore()
  const authStore = useAuthStore()

  await readSSEStream({
    url: `${serverStore.manageBase}/agent/chat`,
    body: { ...request, stream: true },
    signal,
    timeoutMs: 30000,
    doneSentinel: DONE_SENTINEL,
    headers: authStore.token ? { Authorization: `Bearer ${authStore.token}` } : undefined,
    onChunk: (rawData) => {
      try {
        onChunk(JSON.parse(rawData))
      } catch (err) {
        if (rawData.length < 200) console.warn('[Agent SSE] Parse skip:', rawData, err)
        onChunk(rawData)
      }
    },
    onError: (error) => {
      const message = buildStreamErrorMessage(
        error.message,
        'manage',
        serverStore.connectionStatus,
        serverStore.connectionDetails,
        serverStore.lastErrorMessage
      )
      onError?.(new Error(message))
    },
  })
}

export { DONE_SENTINEL }
export type { ChatMessage, ChatCompletionRequest, ChatCompletionResponse, AgentToolCall, AgentMessage, AgentRequest, ToolResult }

export async function getSwitchStatus(): Promise<SwitchStatusResponse> {
  const { data } = await client.get<SwitchStatusResponse>(
    '/switch/status',
    silentRequestConfig()
  )
  return data
}

export async function cancelSwitch(): Promise<{ status: string }> {
  const { data } = await client.delete<{ status: string }>('/switch/cancel')
  return data
}

export async function searchModels(keyword: string, source: string = 'all', limit: number = 10, config: AxiosRequestConfig = {}): Promise<{ results: SearchResult[]; total: number }> {
  const { data } = await client.get<{ results: SearchResult[]; total: number }>(
    `/models/search?keyword=${encodeURIComponent(keyword)}&source=${source}&limit=${limit}`,
    silentRequestConfig(config)
  )
  return data
}

interface RawGPURecommendInfo {
  backend?: string
  device_count?: number
  devices?: Array<{
    device_id: number
    total_gb: number
    used_gb: number
    free_gb: number
    effective_free_gb: number
    loaded_models_memory_gb: number
    utilization_pct: number
  }>
  loaded_models?: unknown[]
  total_loaded_memory_gb?: number
  available?: boolean
  name?: string
  total_gb?: number
  used_gb?: number
  free_gb?: number
  safety_available_gb?: number
}

const normalizeGPURecommendInfo = (raw: RawGPURecommendInfo): GPURecommendInfo => {
  if (raw.name && raw.total_gb) {
    return {
      available: raw.available ?? true,
      name: raw.name,
      total_gb: raw.total_gb,
      used_gb: raw.used_gb ?? 0,
      free_gb: raw.free_gb ?? 0,
      safety_available_gb: raw.safety_available_gb ?? raw.free_gb ?? 0,
    }
  }
  const primaryDevice = raw.devices?.[0]
  return {
    available: raw.available ?? true,
    name: primaryDevice?.device_id != null ? `GPU #${primaryDevice.device_id}` : undefined,
    total_gb: primaryDevice?.total_gb ?? raw.total_gb ?? 0,
    used_gb: primaryDevice?.used_gb ?? raw.used_gb ?? 0,
    free_gb: primaryDevice?.free_gb ?? raw.free_gb ?? 0,
    safety_available_gb: primaryDevice?.effective_free_gb ?? raw.safety_available_gb ?? primaryDevice?.free_gb ?? 0,
  }
}

export async function recommendModel(keyword: string, source: string = 'all', config: AxiosRequestConfig = {}): Promise<RecommendResult> {
  const { data } = await client.get<RecommendResult>(
    `/gpu/recommend?keyword=${encodeURIComponent(keyword)}&source=${source}`,
    silentRequestConfig(config)
  )
  const rawGpuInfo = (data.gpu_info ?? {}) as RawGPURecommendInfo
  data.gpu_info = normalizeGPURecommendInfo(rawGpuInfo)
  return data
}

export async function checkModelMemory(modelName: string, config: AxiosRequestConfig = {}): Promise<MemoryCheckResult> {
  const { data } = await client.post<MemoryCheckResult>(
    `/gpu/memory-check/${encodeURIComponent(modelName)}`,
    null,
    silentRequestConfig(config)
  )
  return data
}

export async function startDownload(modelName: string, source: string = 'hf', saveDir?: string, options?: { hfToken?: string; allowPatterns?: string[]; ignorePatterns?: string[]; maxWorkers?: number; forceDownload?: boolean }, config: AxiosRequestConfig = {}): Promise<DownloadTask | { status: string; local_path: string; model_name: string }> {
  const body: Record<string, unknown> = { model_name: modelName, source, save_dir: saveDir }
  if (options?.hfToken) body.hf_token = options.hfToken
  if (options?.allowPatterns) body.allow_patterns = options.allowPatterns
  if (options?.ignorePatterns) body.ignore_patterns = options.ignorePatterns
  if (options?.maxWorkers) body.max_workers = options.maxWorkers
  if (options?.forceDownload) body.force_download = options.forceDownload
  const { data } = await client.post(
    '/models/download',
    body,
    silentRequestConfig(config)
  )
  return data
}

export async function getDownloadStatus(taskId: string, config: AxiosRequestConfig = {}): Promise<DownloadTask> {
  const { data } = await client.get<DownloadTask>(
    `/models/download/${taskId}/status`,
    silentRequestConfig(config)
  )
  return data
}

export async function cancelDownload(taskId: string, config: AxiosRequestConfig = {}): Promise<{ cancelled: boolean; task_id: string }> {
  const { data } = await client.delete<{ cancelled: boolean; task_id: string }>(
    `/models/download/${taskId}`,
    silentRequestConfig(config)
  )
  return data
}

export async function listDownloads(config: AxiosRequestConfig = {}): Promise<DownloadTask[]> {
  const { data } = await client.get<DownloadTask[]>(
    '/models/downloads',
    silentRequestConfig(config)
  )
  return data
}

export async function getPoolList(filter: string = 'all', page: number = 1, pageSize: number = 50, config: AxiosRequestConfig = {}): Promise<PoolListResponse> {
  const { data } = await client.get<PoolListResponse>(
    `/models/pool?filter=${filter}&page=${page}&page_size=${pageSize}`,
    silentRequestConfig(config)
  )
  return data
}

export async function getPoolDetail(modelKey: string, config: AxiosRequestConfig = {}): Promise<PoolEntry> {
  const { data } = await client.get<PoolEntry>(
    `/models/pool/${encodeURIComponent(modelKey)}`,
    silentRequestConfig(config)
  )
  return data
}

export async function loadFromPool(modelKey: string, engine: string = 'vllm', config: AxiosRequestConfig = {}): Promise<{ success: boolean; model: string; engine: string; port: number }> {
  const { data } = await client.post(
    `/models/pool/${encodeURIComponent(modelKey)}/load`,
    { engine },
    silentRequestConfig(config)
  )
  return data
}

export async function deleteFromPool(modelKey: string, removeFiles: boolean = false, config: AxiosRequestConfig = {}): Promise<{ deleted: boolean; model_key: string }> {
  const { data } = await client.delete(
    `/models/pool/${encodeURIComponent(modelKey)}?remove_files=${removeFiles}`,
    silentRequestConfig(config)
  )
  return data
}

export async function getLLMServiceStatus(config: AxiosRequestConfig = {}): Promise<Record<string, { running: boolean; engine: string; port: number | null; pid: number | null; started_at: string | null }>> {
  const { data } = await client.get('/service/status', silentRequestConfig(config))
  return data
}

export async function getLLMServiceLogs(lines: number = 100, config: AxiosRequestConfig = {}): Promise<{ logs: string[]; count: number }> {
  const { data } = await client.get('/service/logs', silentRequestConfig({ params: { lines }, ...config }))
  return data
}

export async function getEngineStatus(config: AxiosRequestConfig = {}): Promise<EngineStatus> {
  const { data } = await client.get<EngineStatus>('/engines/status', silentRequestConfig(config))
  return data
}

export async function switchEngine(modelName: string, engineType: EngineType = 'vllm', port: number = 8000, config: AxiosRequestConfig = {}): Promise<ActionResponse & { session_id?: string }> {
  const { data } = await client.post<ActionResponse & { session_id?: string }>(
    '/engines/switch',
    { model_name: modelName, engine_type: engineType, port },
    config
  )
  return data
}

export async function getEngineConfig(config: AxiosRequestConfig = {}): Promise<EngineConfig> {
  const { data } = await client.get<EngineConfig>('/engines/config', silentRequestConfig(config))
  return data
}

export async function updateEngineConfig(
  newConfig: Partial<EngineConfig>,
  config: AxiosRequestConfig = {}
): Promise<EngineConfig> {
  const { data } = await client.put<EngineConfig>('/engines/config', newConfig, config)
  return data
}

export async function getEngineParamSchema(config: AxiosRequestConfig = {}): Promise<EngineParamSchema> {
  const { data } = await client.get<EngineParamSchema>('/engines/param-schema', silentRequestConfig(config))
  return data
}

export async function getModelEngineParams(modelName: string, config: AxiosRequestConfig = {}): Promise<ModelEngineParams> {
  const { data } = await client.get<ModelEngineParams>(`/models/${encodeURIComponent(modelName)}/engine-params`, silentRequestConfig(config))
  return data
}

export async function updateModelEngineParams(
  modelName: string,
  engineType: EngineType,
  params: Record<string, unknown>,
  config: AxiosRequestConfig = {}
): Promise<{ status: string; model_name: string; engine_type: EngineType; params: Record<string, unknown> }> {
  const { data } = await client.put(
    `/models/${encodeURIComponent(modelName)}/engine-params`,
    { engine_type: engineType, params },
    config
  )
  return data
}

export async function getGPUMemoryCheck(config: AxiosRequestConfig = {}): Promise<GPUMemoryInfo> {
  const { data } = await client.get<GPUMemoryInfo>('/gpu/memory-check', silentRequestConfig(config))
  return data
}

export async function getRateLimitConfig(config: AxiosRequestConfig = {}): Promise<RateLimitConfig> {
  const { data } = await client.get<RateLimitConfig>('/ratelimit/config', silentRequestConfig(config))
  return data
}

export async function updateRateLimitConfig(newConfig: Partial<RateLimitConfig>, config: AxiosRequestConfig = {}): Promise<RateLimitConfig> {
  const { data } = await client.put<RateLimitConfig>('/ratelimit/config', newConfig, config)
  return data
}

export async function getRateLimitStats(config: AxiosRequestConfig = {}): Promise<RateLimitStats> {
  const { data } = await client.get<RateLimitStats>('/ratelimit/stats', silentRequestConfig(config))
  return data
}

export async function getSystemConfig(config: AxiosRequestConfig = {}): Promise<SystemConfig> {
  const { data } = await client.get<SystemConfig>('/config', silentRequestConfig(config))
  return data
}

export async function updateSystemConfig(newConfig: Partial<SystemConfig>, config: AxiosRequestConfig = {}): Promise<SystemConfig> {
  const { data } = await client.put<SystemConfig>('/config', newConfig, config)
  return data
}

export async function getHealthDetailed(config: AxiosRequestConfig = {}): Promise<GoHealthDetail> {
  const { data } = await client.get<GoHealthDetail>('/health/detailed', silentRequestConfig(config))
  return data
}

export async function getHealthHistory(config: AxiosRequestConfig = {}): Promise<HealthHistoryEntry[]> {
  const { data } = await client.get<HealthHistoryEntry[]>('/health/history', silentRequestConfig(config))
  return data
}
