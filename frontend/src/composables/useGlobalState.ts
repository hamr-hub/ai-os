import { ref, computed } from 'vue'

interface GlobalError {
  id: number
  message: string
  type: 'error' | 'warning' | 'info'
  timestamp: Date
}

const errors = ref<GlobalError[]>([])
const isLoading = ref(false)
const loadingMessage = ref('')
let errorIdCounter = 0

export function useGlobalState() {
  const hasErrors = computed(() => errors.value.length > 0)

  const addError = (message: string, type: 'error' | 'warning' | 'info' = 'error') => {
    const error: GlobalError = {
      id: errorIdCounter++,
      message,
      type,
      timestamp: new Date()
    }
    errors.value.push(error)
    
    if (errors.value.length > 5) {
      errors.value.shift()
    }

    setTimeout(() => {
      removeError(error.id)
    }, 5000)

    return error.id
  }

  const removeError = (id: number) => {
    const index = errors.value.findIndex(e => e.id === id)
    if (index > -1) {
      errors.value.splice(index, 1)
    }
  }

  const clearErrors = () => {
    errors.value = []
  }

  const startLoading = (message = '加载中...') => {
    isLoading.value = true
    loadingMessage.value = message
  }

  const stopLoading = () => {
    isLoading.value = false
    loadingMessage.value = ''
  }

  return {
    errors,
    hasErrors,
    isLoading,
    loadingMessage,
    addError,
    removeError,
    clearErrors,
    startLoading,
    stopLoading
  }
}
