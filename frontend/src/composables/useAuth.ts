import { computed, ref, type Ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useServerStore } from '@/stores/server'
import { verifyAuth } from '@/api/client'

export function useAuth() {
  const authStore = useAuthStore()
  const serverStore = useServerStore()
  const loading = ref(false)
  const error: Ref<string | null> = ref(null)

  const verifyAuthWithFetch = async (apiKey: string) => {
    const response = await fetch(`${serverStore.manageBase}/auth/verify`, {
      cache: 'no-store',
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${apiKey}`,
      },
    })
    if (!response.ok) return false
    const result = await response.json().catch(() => ({}))
    return result.authenticated === true || result.auth_enabled === false
  }

  const login = async (apiKey: string) => {
    loading.value = true
    error.value = null
    try {
      authStore.setToken(apiKey)
      let verified = false
      try {
        const result = await verifyAuth()
        verified = result.authenticated === true || result.auth_enabled === false
      } catch {
        verified = await verifyAuthWithFetch(apiKey).catch(() => false)
      }
      if (!verified) {
        authStore.clearToken()
        error.value = '认证失败：API Key 无效或服务不可用'
        return false
      }
      return true
    } catch (e: unknown) {
      authStore.clearToken()
      error.value = (e as Error).message || '登录失败'
      return false
    } finally {
      loading.value = false
    }
  }

  const logout = () => {
    authStore.clearToken()
  }

  return {
    token: authStore.token,
    user: authStore.user,
    loading,
    error,
    isAuthenticated: computed(() => authStore.isAuthenticated),
    login,
    logout,
  }
}
