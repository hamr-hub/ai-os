import { ref, type Ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { healthCheck } from '@/api/client'

export function useAuth() {
  const authStore = useAuthStore()
  const loading = ref(false)
  const error: Ref<string | null> = ref(null)

  const login = async (apiKey: string) => {
    loading.value = true
    error.value = null
    try {
      authStore.setToken(apiKey)
      try {
        await healthCheck()
      } catch {
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
    isAuthenticated: authStore.isAuthenticated,
    login,
    logout,
  }
}
