import { ref, type Ref } from 'vue'

export function useAuth() {
  const token: Ref<string | null> = ref(localStorage.getItem('auth_token'))
  const user: Ref<string | null> = ref(localStorage.getItem('auth_user'))
  const loading = ref(false)
  const error: Ref<string | null> = ref(null)
  const isAuthenticated = ref(!!token.value)

  const login = async (apiKey: string) => {
    loading.value = true
    error.value = null
    try {
      token.value = apiKey
      user.value = 'admin'
      localStorage.setItem('auth_token', apiKey)
      localStorage.setItem('auth_user', 'admin')
      isAuthenticated.value = true
      return true
    } catch (e: unknown) {
      error.value = (e as Error).message || '登录失败'
      return false
    } finally {
      loading.value = false
    }
  }

  const logout = () => {
    token.value = null
    user.value = null
    localStorage.removeItem('auth_token')
    localStorage.removeItem('auth_user')
    isAuthenticated.value = false
  }

  return {
    token,
    user,
    loading,
    error,
    isAuthenticated,
    login,
    logout,
  }
}
