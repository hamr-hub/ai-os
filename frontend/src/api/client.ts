import axios, { type AxiosRequestConfig, type AxiosResponse } from 'axios'
import type { GPUStatus, GPUSummary, ModelStatus, ModelsResponse, ActionResponse } from '@/types'

const BASE_URL = '/api'

const client = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
})

client.interceptors.request.use(
  (config: AxiosRequestConfig) => {
    return config
  },
  (error) => {
    console.error('Request error:', error)
    return Promise.reject(error)
  }
)

client.interceptors.response.use(
  (response: AxiosResponse) => {
    return response
  },
  (error) => {
    const errorMessage = error.response?.data?.message || error.message || '请求失败'
    console.error('Response error:', errorMessage)
    return Promise.reject(new Error(errorMessage))
  }
)

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

export async function chatCompletionStream(
  request: Omit<ChatCompletionRequest, 'stream'>,
  onChunk: (content: string) => void,
  onError?: (error: Error) => void
): Promise<void> {
  try {
    const response = await client.post('/v1/chat/completions', { ...request, stream: true }, {
      responseType: 'stream',
    })

    const stream = response.data as ReadableStream

    const reader = stream.getReader()
    const decoder = new TextDecoder('utf-8')

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const chunk = decoder.decode(value, { stream: true })
      const lines = chunk.split('\n').filter((line: string) => line.trim())

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (data === '[DONE]') return

          try {
            const json = JSON.parse(data)
            const content = json.choices?.[0]?.delta?.content
            if (content) {
              onChunk(content)
            }
          } catch {
          }
        }
      }
    }
  } catch (error) {
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
