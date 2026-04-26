import axios, { type AxiosRequestConfig } from 'axios'
import type {
  GPUSummary,
  GPUHistoryEntry,
  GPUProcess,
  GPUEnhancedInfo,
  VLLMMetricsData,
  ModelStatus,
  ModelsResponse,
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
} from '@/types'
import { useServerStore } from '@/stores/server'
import { useAppStore } from '@/stores/app'
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
  config.baseURL = serverStore.manageBase
  return config
})

v1Client.interceptors.request.use((config) => {
  const serverStore = useServerStore()
  config.baseURL = serverStore.v1Base
  return config
})

const handleResponseError = (error: unknown) => {
  const config = (error as { config?: RetryableConfig }).config
  const appStore = useAppStore()

  if (axios.isCancel(error)) {
    return Promise.reject(error)
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

export async function getModels(): Promise<ModelsResponse> {
  const { data } = await v1Client.get<ModelsResponse>('/models')
  return data
}

export async function startModel(name: string): Promise<ActionResponse> {
  const { data } = await client.post<ActionResponse>(`/models/${name}/start`)
  return data
}

export async function stopModel(name: string): Promise<ActionResponse> {
  const { data } = await client.post<ActionResponse>(`/models/${name}/stop`)
  return data
}

export async function switchModel(name: string, testEnabled = true): Promise<ActionResponse> {
  const { data } = await client.post<ActionResponse>(`/models/${name}/switch`, null, {
    params: { test_enabled: testEnabled },
  })
  return data
}

export async function runModelTest(name: string): Promise<TestResponse> {
  const { data } = await v1Client.post<TestResponse>(
    `/test/model/${name}`,
    null,
    silentRequestConfig({ timeout: 180000 })
  )
  return data
}

export async function getTestResults(name: string): Promise<TestResponse> {
  const { data } = await v1Client.get<TestResponse>(
    `/test/report/${name}`,
    silentRequestConfig()
  )
  return data
}

export async function getTestHistory(): Promise<TestHistoryEntry[]> {
  const { data } = await v1Client.get<
    | {
        status?: string
        reports?: Record<string, Record<string, unknown>>
        history?: Array<Record<string, unknown>>
      }
    | Array<Record<string, unknown>>
  >('/test/reports')

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
  const serverStore = useServerStore()
  const { data } = await axios.get<{ status: string }>(serverStore.inferenceHealthUrl)
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

  await readSSEStream({
    url: `${serverStore.v1Base}/chat/completions`,
    body: {
      ...request,
      stream: true,
      enable_thinking: false,
    },
    signal,
    timeoutMs: 30000,
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

  await readSSEStream({
    url: `${serverStore.manageBase}/agent/chat`,
    body: { ...request, stream: true },
    signal,
    timeoutMs: 30000,
    doneSentinel: DONE_SENTINEL,
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
