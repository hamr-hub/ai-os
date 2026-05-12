import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/client', () => ({
  verifyAuth: vi.fn().mockResolvedValue({ authenticated: true, auth_enabled: true, mode: 'token' }),
}))

const mockLocalStorage = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
}
vi.stubGlobal('localStorage', mockLocalStorage)

import { useAuth } from '@/composables/useAuth'

describe('useAuth', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockLocalStorage.getItem.mockReturnValue(null)
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('fetch failed')))
    setActivePinia(createPinia())
  })

  it('初始状态isAuthenticated为false', () => {
    const { loading, error, isAuthenticated } = useAuth()
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
    expect(isAuthenticated.value).toBe(false)
  })

  it('login成功后isAuthenticated为true', async () => {
    const { login, isAuthenticated, loading, error } = useAuth()
    const result = await login('my-api-key')
    expect(result).toBe(true)
    expect(isAuthenticated.value).toBe(true)
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
  })

  it('logout后isAuthenticated为false', async () => {
    const { login, logout, isAuthenticated } = useAuth()
    await login('existing-key')
    expect(isAuthenticated.value).toBe(true)
    logout()
    expect(isAuthenticated.value).toBe(false)
  })

  it('healthCheck失败时login返回false并设置error', async () => {
    const { verifyAuth } = await import('@/api/client')
    vi.mocked(verifyAuth).mockRejectedValueOnce(new Error('Unauthorized'))
    const { login, error, loading } = useAuth()
    const result = await login('bad-key')
    expect(result).toBe(false)
    expect(error.value).toBe('认证失败：API Key 无效或服务不可用')
    expect(loading.value).toBe(false)
  })

  it('verifyAuth异常时使用fetch兜底登录', async () => {
    const { verifyAuth } = await import('@/api/client')
    vi.mocked(verifyAuth).mockRejectedValueOnce(new Error('Interceptor failed'))
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ authenticated: true, auth_enabled: false }),
      })
    )

    const { login, isAuthenticated, error } = useAuth()
    const result = await login('fallback-key')

    expect(result).toBe(true)
    expect(isAuthenticated.value).toBe(true)
    expect(error.value).toBeNull()
    expect(fetch).toHaveBeenCalledWith(
      '/api/auth/verify',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer fallback-key' }),
      })
    )
  })
})
