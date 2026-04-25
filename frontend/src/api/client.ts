import axios from 'axios'
import type {
  GPUSummary,
  GPUHistoryEntry,
  GPUProcess,
  VLLMMetricsData,
  ModelStatus,
  ModelsResponse,
  ActionResponse,
  TestResponse,
  TestHistoryEntry,
  TokenStats,
  SystemStatus,
  QueueStatus,
  HealthAlert,
} from '@/types'
import { useServerStore } from '@/stores/server'
import { useAppStore } from '@/stores/app'

const client = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

const v1Client = axios.create({
  baseURL: '/v1',
  timeout: 60000,
})

type RetryableConfig = {
  __retryCount?: number
  method?: string
  url?: string
}

const RETRYABLE_METHODS = new Set(['get', 'head', 'options'])

const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms))

const createTimedAbortSignal = (signal?: AbortSignal, timeoutMs = 30000) => {
  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(new Error('请求超时')), timeoutMs)

  const abortFromParent = () => controller.abort(signal?.reason)
  if (signal) {
    if (signal.aborted) {
      abortFromParent()
    } else {
      signal.addEventListener('abort', abortFromParent, { once: true })
    }
  }

  return {
    signal: controller.signal,
    cleanup: () => {
      window.clearTimeout(timeoutId)
      signal?.removeEventListener('abort', abortFromParent)
    },
  }
}

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

// Request Interceptors
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

// Response Interceptors
const handleResponseError = (error: unknown) => {
  const appStore = useAppStore()

  // Don't toast for cancelled requests
  if (axios.isCancel(error)) {
    return Promise.reject(error)
  }

  appStore.error(normalizeErrorMessage(error))
  return Promise.reject(error)
}

attachRetryInterceptor(client)
attachRetryInterceptor(v1Client)

client.interceptors.response.use((response) => response, handleResponseError)

v1Client.interceptors.response.use((response) => response, handleResponseError)

export async function getGPUSummary(): Promise<GPUSummary> {
  const { data } = await client.get<GPUSummary>('/gpu/summary')
  return data
}

export async function getGPUEnhancedInfo(): Promise<Record<string, any>> {
  const { data } = await client.get('/gpu/enhanced')
  return data
}

export async function getGPUProcesses(): Promise<{ processes: GPUProcess[]; count: number }> {
  const { data } = await client.get<{ processes: GPUProcess[]; count: number }>('/gpu/processes')
  return data
}

export async function getVLLMMetrics(): Promise<VLLMMetricsData> {
  const { data } = await client.get<VLLMMetricsData>('/vllm/metrics')
  return data
}

export async function getModelsStatus(): Promise<ModelStatus> {
  const { data } = await client.get<ModelStatus>('/models')
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
  const { data } = await v1Client.post<TestResponse>(`/test/model/${name}`)
  return data
}

export async function getTestResults(name: string): Promise<TestResponse> {
  const { data } = await v1Client.get<TestResponse>(`/test/report/${name}`)
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

export async function getTokenStats(): Promise<TokenStats> {
  const { data } = await client.get<TokenStats>('/token/stats')
  return data
}

export async function getTokenHistory(count: number = 60): Promise<{
  history: Array<{
    timestamp: string
    total_tokens: number
    prompt_tokens: number
    completion_tokens: number
    models: Record<string, any>
  }>
  count: number
}> {
  const { data } = await client.get('/token/history', { params: { count } })
  return data
}

export async function getGPUHistory(
  count: number = 60
): Promise<{ history: GPUHistoryEntry[]; count: number; enabled: boolean; max_days: number }> {
  const { data } = await client.get('/gpu/history', { params: { count } })
  return data
}

export async function healthCheck(): Promise<{ status: string }> {
  const serverStore = useServerStore()
  const { data } = await axios.get<{ status: string }>(serverStore.healthUrl)
  return data
}

export async function getDefaultModel(): Promise<{ default_model: string | null }> {
  const { data } = await client.get<{ default_model: string | null }>('/default-model')
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
  historyCount = 60
): Promise<SystemStatus & { history?: any[] }> {
  const { data } = await client.get<SystemStatus & { history?: any[] }>('/system/status', {
    params: { include_history: includeHistory, history_count: historyCount },
  })
  return data
}

export async function getSystemHistory(
  count: number = 60
): Promise<{ history: any[]; count: number }> {
  const { data } = await client.get('/system/history', { params: { count } })
  return data
}

export async function getQueueStatus(): Promise<QueueStatus> {
  const { data } = await client.get<QueueStatus>('/queue')
  return data
}

export async function getHealthAlert(): Promise<HealthAlert> {
  const { data } = await client.get<HealthAlert>('/health/alert')
  return data
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string | Array<{ type: string; text?: string; image_url?: { url: string } }>
}

export interface ChatCompletionRequest {
  model?: string
  messages: ChatMessage[]
  stream?: boolean
  max_tokens?: number
  temperature?: number
  // Disable thinking mode for models that support it (DeepSeek R1, Qwen, etc.)
  enable_thinking?: boolean
}

export interface ChatCompletionResponse {
  id: string
  object: string
  created: number
  model: string
  choices: {
    index: number
    message: { role: string; content: string }
    finish_reason: string
  }[]
  usage?: { prompt_tokens: number; completion_tokens: number; total_tokens: number }
}

export async function chatCompletion(
  request: ChatCompletionRequest
): Promise<ChatCompletionResponse> {
  const { data } = await v1Client.post<ChatCompletionResponse>('/chat/completions', request)
  return data
}

const DONE_SENTINEL = '[DONE]'

export async function chatCompletionStream(
  request: Omit<ChatCompletionRequest, 'stream'>,
  onChunk: (content: string) => void,
  onError?: (error: Error) => void,
  signal?: AbortSignal
): Promise<void> {
  const timedSignal = createTimedAbortSignal(signal, 30000)
  try {
    const serverStore = useServerStore()
    const response = await fetch(`${serverStore.v1Base}/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...request,
        stream: true,
        // Explicitly disable thinking mode to avoid reasoning_content errors
        enable_thinking: false,
      }),
      signal: timedSignal.signal,
    })

    if (!response.ok) {
      const errorText = await response.text()
      // Check for thinking mode error and provide guidance
      if (errorText.includes('reasoning_content') || errorText.includes('thinking is enabled')) {
        throw new Error('模型thinking模式错误，请联系后端管理员关闭thinking模式或更新API配置')
      }
      throw new Error(`HTTP ${response.status}: ${errorText}`)
    }

    const reader = response.body?.getReader()
    if (!reader) throw new Error('No response body')

    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed || !trimmed.startsWith('data: ')) continue
        const data = trimmed.slice(6)
        if (data === DONE_SENTINEL) return

        try {
          const json = JSON.parse(data)
          // Handle reasoning_content if present (for thinking-enabled models)
          const reasoningContent = json.choices?.[0]?.delta?.reasoning_content
          if (reasoningContent) {
            // Skip reasoning content or handle separately if needed
            // For now, we just ignore it to avoid mixing with regular content
          }
          const content = json.choices?.[0]?.delta?.content
          if (content) onChunk(content)
        } catch (err) {
          if (data.length < 200) console.warn('[SSE] Parse skip:', data, err)
        }
      }
    }
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') throw error
    if (onError) onError(error instanceof Error ? error : new Error('Stream error'))
    else throw error
  } finally {
    timedSignal.cleanup()
  }
}

// Agent API
export interface AgentToolCall {
  name: string
  arguments: Record<string, unknown>
}

export interface AgentMessage {
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  tool_calls?: Array<{
    id: string
    type: 'function'
    function: { name: string; arguments: string }
  }>
  tool_call_id?: string
}

export interface AgentRequest {
  model?: string
  messages: AgentMessage[]
  tools?: string[]
  max_iterations?: number
  stream?: boolean
  auto_confirm?: boolean
}

export interface ToolResult {
  tool_name: string
  success: boolean
  result: unknown
  error?: string
  execution_time: number
}

export async function listAgentTools(categories?: string): Promise<{
  tools: Array<{ type: string; function: unknown }>
  categories: string[]
  count: number
}> {
  const params = categories ? { categories } : {}
  const { data } = await client.get('/agent/tools', { params })
  return data
}

export async function getAgentToolInfo(toolName: string): Promise<{
  name: string
  description: string
  parameters: unknown[]
  category: string
  dangerous: boolean
  requires_confirmation: boolean
}> {
  const { data } = await client.get(`/agent/tools/${toolName}`)
  return data
}

export async function executeToolCall(
  name: string,
  args: Record<string, unknown>,
  autoConfirm = false
): Promise<ToolResult> {
  const { data } = await client.post(`/agent/execute/${name}`, {
    name,
    arguments: args,
    auto_confirm: autoConfirm,
  })
  return data
}

export async function executeToolBatch(
  calls: AgentToolCall[],
  autoConfirm = false
): Promise<{ results: ToolResult[]; success: boolean }> {
  const { data } = await client.post('/agent/execute', {
    calls,
    auto_confirm: autoConfirm,
  })
  return data
}

export async function getToolExecutionHistory(limit = 100): Promise<{
  history: ToolResult[]
  statistics: unknown
}> {
  const { data } = await client.get('/agent/history', {
    params: { limit },
  })
  return data
}

export async function clearToolExecutionHistory(): Promise<{ status: string }> {
  const { data } = await client.delete('/agent/history')
  return data
}

export async function agentChatCompletion(request: AgentRequest): Promise<{
  id: string
  model: string
  message: { role: string; content: string }
  iterations: number
  finished: boolean
}> {
  const { data } = await client.post('/agent/chat', {
    ...request,
    stream: false,
  })
  return data
}

export async function agentChatStream(
  request: Omit<AgentRequest, 'stream'>,
  onChunk: (data: unknown) => void,
  onError?: (error: Error) => void,
  signal?: AbortSignal
): Promise<void> {
  const timedSignal = createTimedAbortSignal(signal, 30000)
  try {
    const serverStore = useServerStore()
    const response = await fetch(`${serverStore.manageBase}/agent/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...request, stream: true }),
      signal: timedSignal.signal,
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`HTTP ${response.status}: ${errorText}`)
    }

    const reader = response.body?.getReader()
    if (!reader) throw new Error('No response body')

    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed || !trimmed.startsWith('data: ')) continue
        const data = trimmed.slice(6)
        if (data === '[DONE]') return

        try {
          onChunk(JSON.parse(data))
        } catch (err) {
          if (data.length < 200) console.warn('[Agent SSE] Parse skip:', data, err)
          onChunk(data)
        }
      }
    }
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') throw error
    if (onError) onError(error instanceof Error ? error : new Error('Stream error'))
    else throw error
  } finally {
    timedSignal.cleanup()
  }
}
