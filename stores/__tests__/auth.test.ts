import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const mockLocalStorage = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
}
vi.stubGlobal('localStorage', mockLocalStorage)

import { useAuthStore } from '@/stores/auth'

describe('useAuthStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockLocalStorage.getItem.mockReturnValue(null)
  })

  it('初始状态token为空字符串，isAuthenticated为false', () => {
    const store = useAuthStore()
    expect(store.token).toBe('')
    expect(store.user).toBe('')
    expect(store.isAuthenticated).toBe(false)
  })

  it('localStorage有token时isAuthenticated为true', () => {
    mockLocalStorage.getItem
      .mockReturnValueOnce('my-key')
      .mockReturnValueOnce('admin')
    const store = useAuthStore()
    expect(store.token).toBe('my-key')
    expect(store.isAuthenticated).toBe(true)
  })

  it('setToken存localStorage并更新状态', () => {
    const store = useAuthStore()
    store.setToken('new-key', 'admin')

    expect(store.token).toBe('new-key')
    expect(store.user).toBe('admin')
    expect(store.isAuthenticated).toBe(true)
    expect(mockLocalStorage.setItem).toHaveBeenCalledWith('auth_token', 'new-key')
    expect(mockLocalStorage.setItem).toHaveBeenCalledWith('auth_user', 'admin')
  })

  it('clearToken清localStorage并重置', () => {
    mockLocalStorage.getItem
      .mockReturnValueOnce('old-key')
      .mockReturnValueOnce('admin')
    const store = useAuthStore()
    store.clearToken()

    expect(store.token).toBe('')
    expect(store.user).toBe('')
    expect(store.isAuthenticated).toBe(false)
    expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('auth_token')
    expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('auth_user')
  })
})
