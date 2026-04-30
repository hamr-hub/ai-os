import { describe, it, expect, vi, beforeEach } from 'vitest'

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
  })

  it('初始状态token/user为null，isAuthenticated为false', () => {
    const { token, user, loading, error, isAuthenticated } = useAuth()
    expect(token.value).toBeNull()
    expect(user.value).toBeNull()
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
    expect(isAuthenticated.value).toBe(false)
  })

  it('localStorage有token时isAuthenticated为true', () => {
    mockLocalStorage.getItem
      .mockReturnValueOnce('test-key')
      .mockReturnValueOnce('admin')
    const { isAuthenticated, token, user } = useAuth()
    expect(token.value).toBe('test-key')
    expect(user.value).toBe('admin')
    expect(isAuthenticated.value).toBe(true)
  })

  it('login成功后设置token/user到localStorage并更新isAuthenticated', async () => {
    const { login, token, user, isAuthenticated, loading, error } = useAuth()
    const result = await login('my-api-key')
    expect(result).toBe(true)
    expect(token.value).toBe('my-api-key')
    expect(user.value).toBe('admin')
    expect(isAuthenticated.value).toBe(true)
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
    expect(mockLocalStorage.setItem).toHaveBeenCalledWith('auth_token', 'my-api-key')
    expect(mockLocalStorage.setItem).toHaveBeenCalledWith('auth_user', 'admin')
  })

  it('logout后清空token/user并更新isAuthenticated', () => {
    mockLocalStorage.getItem
      .mockReturnValueOnce('existing-key')
      .mockReturnValueOnce('admin')
    const { logout, token, user, isAuthenticated } = useAuth()
    logout()
    expect(token.value).toBeNull()
    expect(user.value).toBeNull()
    expect(isAuthenticated.value).toBe(false)
    expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('auth_token')
    expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('auth_user')
  })

  it('localStorage.setItem抛出异常时login返回false并设置error', async () => {
    mockLocalStorage.setItem.mockImplementation(() => {
      throw new Error('storage full')
    })
    const { login, error, loading } = useAuth()
    const result = await login('fail-key')
    expect(result).toBe(false)
    expect(error.value).toBe('storage full')
    expect(loading.value).toBe(false)
  })
})
