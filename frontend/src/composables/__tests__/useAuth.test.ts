import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/client', () => ({
  healthCheck: vi.fn().mockResolvedValue({ status: 'healthy' }),
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
    setActivePinia(createPinia())
  })

  it('初始状态isAuthenticated为false', () => {
    const { loading, error, isAuthenticated } = useAuth()
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
    expect(isAuthenticated).toBe(false)
  })

  it('login成功后isAuthenticated为true', async () => {
    const { login, isAuthenticated, loading, error } = useAuth()
    const result = await login('my-api-key')
    expect(result).toBe(true)
    expect(isAuthenticated).toBe(true)
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
  })

  it('logout后isAuthenticated为false', async () => {
    const { login, logout, isAuthenticated } = useAuth()
    await login('existing-key')
    expect(isAuthenticated).toBe(true)
    logout()
    expect(isAuthenticated).toBe(false)
  })

  it('healthCheck失败时login返回false并设置error', async () => {
    const { healthCheck } = await import('@/api/client')
    vi.mocked(healthCheck).mockRejectedValueOnce(new Error('Unauthorized'))
    const { login, error, loading } = useAuth()
    const result = await login('bad-key')
    expect(result).toBe(false)
    expect(error.value).toBe('认证失败：API Key 无效或服务不可用')
    expect(loading.value).toBe(false)
  })
})
