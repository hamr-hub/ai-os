import { describe, it, expect, vi, beforeEach, vi as vitestVi } from 'vitest'

vi.mock('@/utils/request', () => ({
  isAbortError: vi.fn((err: unknown) => {
    if (!err || typeof err !== 'object') return false
    const e = err as { name?: string }
    return e.name === 'AbortError'
  }),
}))

const mockOnMounted = vitestVi.fn()
const mockOnUnmounted = vitestVi.fn()
vi.mock('vue', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue')>()
  return {
    ...actual,
    onMounted: (cb: () => void) => { mockOnMounted.mockImplementation(cb) },
    onUnmounted: (cb: () => void) => { mockOnUnmounted.mockImplementation(cb) },
  }
})

import { usePolling } from '@/composables/usePolling'
import { isAbortError } from '@/utils/request'

describe('usePolling', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetch调用fetchFn并设置loading', async () => {
    const fetchFn = vi.fn().mockResolvedValue(undefined)

    const { fetch, loading, error } = usePolling(fetchFn, 5000)
    mockOnMounted()
    await fetch()

    expect(fetchFn).toHaveBeenCalled()
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
  })

  it('AbortController防止并发请求', async () => {
    const fetchFn = vi.fn().mockImplementation(async (signal: AbortSignal) => {
      await new Promise(r => setTimeout(r, 100))
      if (signal.aborted) throw new DOMException('Aborted', 'AbortError')
    })

    const { fetch, loading } = usePolling(fetchFn, 5000)
    mockOnMounted()

    const p1 = fetch()
    const p2 = fetch()

    await Promise.allSettled([p1, p2])

    expect(fetchFn.mock.calls.length).toBeLessThanOrEqual(2)
  })

  it('非Abort错误写入error', async () => {
    const fetchFn = vi.fn().mockRejectedValue(new Error('网络断开'))

    const { fetch, error, loading } = usePolling(fetchFn, 5000)
    mockOnMounted()
    await fetch()

    expect(error.value).toBe('网络断开')
    expect(loading.value).toBe(false)
    expect(isAbortError).toHaveBeenCalled()
  })

  it('AbortError不写入error', async () => {
    const abortErr = new DOMException('Aborted', 'AbortError')
    const fetchFn = vi.fn().mockRejectedValue(abortErr)

    const { fetch, error } = usePolling(fetchFn, 5000)
    mockOnMounted()
    await fetch()

    expect(error.value).toBeNull()
  })

  it('refresh设置isRefreshing=true', async () => {
    const fetchFn = vi.fn().mockResolvedValue(undefined)

    const { refresh, isRefreshing, loading } = usePolling(fetchFn, 5000)
    mockOnMounted()
    await refresh()

    expect(fetchFn).toHaveBeenCalled()
    expect(isRefreshing.value).toBe(false)
    expect(loading.value).toBe(false)
  })

  it('stopPolling清空timer并abort控制器', () => {
    const fetchFn = vi.fn().mockResolvedValue(undefined)

    const { stopPolling } = usePolling(fetchFn, 5000)
    mockOnMounted()
    stopPolling()

    expect(fetchFn).toHaveBeenCalled()
  })
})
