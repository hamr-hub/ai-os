import axios from 'axios'
import type { GPUStatus, GPUSummary, ModelStatus, ModelsResponse, ActionResponse } from '@/types'

const BASE_URL = '/api'

const client = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
})

export async function getGPUStatus(refresh = false): Promise<GPUStatus> {
  const response = await client.get<GPUStatus>('/manage/gpu', {
    params: { refresh },
  })
  return response.data
}

export async function getGPUSummary(): Promise<GPUSummary> {
  const response = await client.get<GPUSummary>('/manage/gpu/summary')
  return response.data
}

export async function getModelStatus(refresh = false): Promise<ModelStatus> {
  const response = await client.get<ModelStatus>('/manage/models', {
    params: { refresh },
  })
  return response.data
}

export async function getModels(): Promise<ModelsResponse> {
  const response = await client.get<ModelsResponse>('/v1/models')
  return response.data
}

export async function startModel(modelName: string): Promise<ActionResponse> {
  const response = await client.post<ActionResponse>(`/manage/models/${modelName}/start`)
  return response.data
}

export async function stopModel(modelName: string): Promise<ActionResponse> {
  const response = await client.post<ActionResponse>(`/manage/models/${modelName}/stop`)
  return response.data
}

export async function switchModel(modelName: string, testEnabled = true): Promise<ActionResponse> {
  const response = await client.post<ActionResponse>(`/manage/models/${modelName}/switch`, {
    test_enabled: testEnabled,
  })
  return response.data
}

export async function getDefaultModel(): Promise<{ default_model: string | null }> {
  const response = await client.get<{ default_model: string | null }>('/manage/default-model')
  return response.data
}

export async function setDefaultModel(modelName: string): Promise<ActionResponse> {
  const response = await client.post<ActionResponse>(`/manage/default-model/${modelName}`)
  return response.data
}

export async function clearDefaultModel(): Promise<ActionResponse> {
  const response = await client.delete<ActionResponse>('/manage/default-model')
  return response.data
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
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
    message: ChatMessage
    finish_reason: string
  }[]
  usage?: {
    prompt_tokens: number
    completion_tokens: number
    total_tokens: number
  }
}

export async function chatCompletion(request: ChatCompletionRequest): Promise<ChatCompletionResponse> {
  const response = await client.post<ChatCompletionResponse>('/v1/chat/completions', request)
  return response.data
}

const DONE_SENTINEL = '[DONE]'

/**
 * Streaming chat completion using native fetch + SSE
 * (axios responseType:'stream' does not work in browser environments)
 */
export async function chatCompletionStream(
  request: Omit<ChatCompletionRequest, 'stream'>,
  onChunk: (content: string) => void,
  onError?: (error: Error) => void,
  signal?: AbortSignal
): Promise<void> {
  try {
    const response = await fetch('/api/v1/chat/completions', {
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
          if (content) {
            onChunk(content)
          }
        } catch {
          // ignore JSON parse errors for incomplete chunks
        }
      }
    }
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') throw error
    if (onError) {
      onError(error instanceof Error ? error : new Error('Stream error'))
    } else {
      throw error
    }
  }
}

export interface ModelTestResult {
  status: string
  message: string
  report?: {
    model_name: string
    test_timestamp: string
    overall_status: string
    feature_support: {
      chat: boolean
      tool_calling: boolean
      multimodal: boolean
    }
    performance_metrics?: {
      latency_ms: number
      throughput: number
      tokens_per_second?: number
    }
    resource_utilization?: {
      gpu_utilization?: number
      memory_usage?: number
    }
    test_results?: {
      test_name: string
      feature_type: string
      status: string
      duration?: number
      metrics?: Record<string, number>
      error?: string
      details?: string
    }[]
    errors?: string[]
    warnings?: string[]
  }
}

export async function testModel(modelName: string): Promise<ModelTestResult> {
  const response = await client.post<ModelTestResult>(`/v1/test/model/${modelName}`)
  return response.data
}

/**
 * Health check endpoint
 */
export async function healthCheck(): Promise<{ status: string; version?: string }> {
  const response = await client.get<{ status: string; version?: string }>('/health')
  return response.data
}
