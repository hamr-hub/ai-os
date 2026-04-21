import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface ToastMessage {
  id: number
  type: 'success' | 'error' | 'warning' | 'info'
  message: string
  duration?: number
}

export const useAppStore = defineStore('app', () => {
  const toasts = ref<ToastMessage[]>([])
  const sidebarCollapsed = ref(false)
  let toastId = 0

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
    addToast,
    removeToast,
    toggleSidebar,
    success,
    error,
    warning,
    info,
  }
})
