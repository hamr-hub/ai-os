import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export interface ToastMessage {
  id: number
  type: 'success' | 'error' | 'warning' | 'info'
  message: string
  duration?: number
}

export const useAppStore = defineStore('app', () => {
  const toasts = ref<ToastMessage[]>([])
  const sidebarCollapsed = ref(false)
  const theme = ref<'light' | 'dark' | 'system'>('system')
  const actualTheme = ref<'light' | 'dark'>('dark')
  let toastId = 0

  const updateActualTheme = () => {
    if (theme.value === 'system') {
      actualTheme.value = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
    } else {
      actualTheme.value = theme.value
    }
    document.documentElement.setAttribute('data-theme', actualTheme.value)
  }

  watch(theme, updateActualTheme, { immediate: true })

  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (theme.value === 'system') {
      updateActualTheme()
    }
  })

  const setTheme = (newTheme: 'light' | 'dark' | 'system') => {
    theme.value = newTheme
    localStorage.setItem('theme', newTheme)
  }

  const initTheme = () => {
    const saved = localStorage.getItem('theme') as 'light' | 'dark' | 'system' | null
    if (saved) {
      theme.value = saved
    }
    updateActualTheme()
  }

  const addToast = (type: ToastMessage['type'], message: string, duration = 3000) => {
    const id = ++toastId
    toasts.value.push({ id, type, message, duration })
    
    if (duration > 0) {
      setTimeout(() => {
        removeToast(id)
      }, duration)
    }
    
    return id
  }

  const removeToast = (id: number) => {
    const index = toasts.value.findIndex((t) => t.id === id)
    if (index !== -1) {
      toasts.value.splice(index, 1)
    }
  }

  const toggleSidebar = () => {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  const success = (message: string, duration?: number) => addToast('success', message, duration)
  const error = (message: string, duration?: number) => addToast('error', message, duration)
  const warning = (message: string, duration?: number) => addToast('warning', message, duration)
  const info = (message: string, duration?: number) => addToast('info', message, duration)

  return {
    toasts,
    sidebarCollapsed,
    theme,
    actualTheme,
    addToast,
    removeToast,
    toggleSidebar,
    setTheme,
    initTheme,
    success,
    error,
    warning,
    info,
  }
})
