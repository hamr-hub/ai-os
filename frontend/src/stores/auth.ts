import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('auth_token') || '')
  const user = ref(localStorage.getItem('auth_user') || '')
  const isAuthenticated = computed(() => !!token.value)

  const setToken = (newToken: string, newUser: string = 'admin') => {
    token.value = newToken
    user.value = newUser
    localStorage.setItem('auth_token', newToken)
    localStorage.setItem('auth_user', newUser)
  }

  const clearToken = () => {
    token.value = ''
    user.value = ''
    localStorage.removeItem('auth_token')
    localStorage.removeItem('auth_user')
  }

  return {
    token,
    user,
    isAuthenticated,
    setToken,
    clearToken,
  }
})
