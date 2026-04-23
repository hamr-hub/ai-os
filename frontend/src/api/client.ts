import axios from 'axios'
import type {
  GPUSummary, GPUHistoryEntry, ModelStatus, ModelsResponse,
  ActionResponse, TestResponse, TestHistoryEntry, TokenStats
} from '@/types'

const client = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

const v1Client = axios.create({
  baseURL: '/v1',
  timeout: 60000,
})

export async function getGPUSummary(): Promise<GPUSummary> {
  const { data } = await client.get<GPUSummary>('/gpu/summary')
  return data
}

export async function getModelsStatus(): Promise<ModelStatus> {
  const { data } = await client.get<ModelStatus>('/models/status')
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
  const { data } = await client.post<ActionResponse>('/models/switch', {
    model_name: name,
    test_enabled: testEnabled,
  })
  return data
}

export async function runModelTest(name: string): Promise<TestResponse> {
  const { data } = await v1Client.post<TestResponse>(`/test/model/${name}`)
  return data
}

export async function getTestResults(name: string): Promise<TestResponse> {
  const { data } = await v1Client.get<TestResponse>(`/test/results/${name}`)
  return data
}

export async function getTestHistory(): Promise<TestHistoryEntry[]> {
  const { data } = await v1Client.get<TestHistoryEntry[]>('/test/history')
  return data
}

export async function getTokenStats(): Promise<TokenStats> {
  const { data } = await client.get<TokenStats>('/manage/token/stats')
  return data
}

export async function getGPUHistory(count: number = 60): Promise<{ history: GPUHistoryEntry[]; count: number; enabled: boolean; max_days: number }> {
  const { data } = await client.get('/manage/gpu/history', { params: { count } })
  return data
}

export async function healthCheck(): Promise<{ status: string }> {
  const { data } = await client.get<{ status: string }>('/health')
  return data
}

export async function getDefaultModel(): Promise<{ default_model: string | null }> {
  const { data } = await client.get<{ default_model: string | null }>('/manage/default-model')
  return data
}

export async function setDefaultModel(modelName: string): Promise<ActionResponse> {
  const { data } = await client.post<ActionResponse>(`/manage/default-model/${modelName}`)
  return data
}

export async function clearDefaultModel(): Promise<ActionResponse> {
  const { data } = await client.delete<ActionResponse>('/manage/default-model')
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

export async function chatCompletion(request: ChatCompletionRequest): Promise<ChatCompletionResponse> {
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
    const response = await fetch('/v1/chat/completions', {
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
        if (data === DONE_SENTINEL) return

        try {
          const json = JSON.parse(data)
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
