export interface SSEStreamOptions {
  url: string
  body: unknown
  signal?: AbortSignal
  timeoutMs?: number
  onChunk: (data: string) => void
  onError?: (error: Error) => void
  doneSentinel?: string
}

export const DONE_SENTINEL = '[DONE]'

export async function readSSEStream(options: SSEStreamOptions): Promise<void> {
  const {
    url,
    body,
    signal,
    timeoutMs = 30000,
    onChunk,
    onError,
    doneSentinel = DONE_SENTINEL,
  } = options

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

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
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
        if (data === doneSentinel) return
        onChunk(data)
      }
    }
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') throw error
    if (onError) onError(error instanceof Error ? error : new Error('Stream error'))
    else throw error
  } finally {
    window.clearTimeout(timeoutId)
    signal?.removeEventListener('abort', abortFromParent)
  }
}
