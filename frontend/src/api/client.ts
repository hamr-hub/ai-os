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
  const err = error as { response?: { data?: unknown }; message?: string }
  const data = err.response?.data as Record<string, unknown> | undefined
  const message =
    (data?.message as string) || (data?.error as string) || err.message || 'API Request Failed'

  // Don't toast for cancelled requests
  if (axios.isCancel(error)) {
    return Promise.reject(error)
  }

  appStore.error(message)
  return Promise.reject(error)
}

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
  const { data } = await v1Client.get<{
    status: string
    reports: Record<string, Record<string, unknown>>
  }>('/test/reports')
  const reports = data.reports || {}
  return Object.entries(reports).map(([model_name, report]) => ({
    model_name,
    timestamp: (report.test_timestamp as string) || '',
    status: (report.overall_status as string) || 'unknown',
    overall_status: report.overall_status as string | undefined,
    duration: (report.resource_utilization as Record<string, unknown>)?.test_duration_seconds as
      | number
      | undefined,
  }))
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
      signal,
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
        } catch {}
      }
    }
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') throw error
    if (onError) onError(error instanceof Error ? error : new Error('Stream error'))
    else throw error
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
  const serverStore = useServerStore()
  const params = categories ? { categories } : {}
  const { data } = await client.get(`${serverStore.manageBase}/agent/tools`, { params })
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
  const serverStore = useServerStore()
  const { data } = await client.get(`${serverStore.manageBase}/agent/tools/${toolName}`)
  return data
}

export async function executeToolCall(
  name: string,
  args: Record<string, unknown>,
  autoConfirm = false
): Promise<ToolResult> {
  const serverStore = useServerStore()
  const { data } = await client.post(`${serverStore.manageBase}/agent/execute/${name}`, {
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
  const serverStore = useServerStore()
  const { data } = await client.post(`${serverStore.manageBase}/agent/execute`, {
    calls,
    auto_confirm: autoConfirm,
  })
  return data
}

export async function getToolExecutionHistory(limit = 100): Promise<{
  history: ToolResult[]
  statistics: unknown
}> {
  const serverStore = useServerStore()
  const { data } = await client.get(`${serverStore.manageBase}/agent/history`, {
    params: { limit },
  })
  return data
}

export async function clearToolExecutionHistory(): Promise<{ status: string }> {
  const serverStore = useServerStore()
  const { data } = await client.delete(`${serverStore.manageBase}/agent/history`)
  return data
}

export async function agentChatCompletion(request: AgentRequest): Promise<{
  id: string
  model: string
  message: { role: string; content: string }
  iterations: number
  finished: boolean
}> {
  const serverStore = useServerStore()
  const { data } = await client.post(`${serverStore.manageBase}/agent/chat`, {
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
  try {
    const serverStore = useServerStore()
    const response = await fetch(`${serverStore.manageBase}/agent/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...request, stream: true }),
      signal,
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
        } catch {
          onChunk(data)
        }
      }
    }
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') throw error
    if (onError) onError(error instanceof Error ? error : new Error('Stream error'))
    else throw error
  }
}
