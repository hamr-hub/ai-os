<script setup lang="ts">
import { useAppStore } from '@/stores/app'
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-vue-next'

const store = useAppStore()

const getToastIcon = (type: string) => {
  switch (type) {
    case 'success':
      return CheckCircle
    case 'error':
      return XCircle
    case 'warning':
      return AlertTriangle
    case 'info':
    default:
      return Info
  }
}

const getToastClass = (type: string) => {
  switch (type) {
    case 'success':
      return 'bg-green-500/20 border-green-500/50 text-green-400'
    case 'error':
      return 'bg-red-500/20 border-red-500/50 text-red-400'
    case 'warning':
      return 'bg-yellow-500/20 border-yellow-500/50 text-yellow-400'
    case 'info':
    default:
      return 'bg-blue-500/20 border-blue-500/50 text-blue-400'
  }
}
</script>

<template>
  <div class="fixed top-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
    <TransitionGroup name="toast">
      <div
        v-for="toast in store.toasts"
        :key="toast.id"
        class="flex items-start gap-3 px-4 py-3 rounded-lg border backdrop-blur-sm shadow-lg"
        :class="getToastClass(toast.type)"
      >
        <component :is="getToastIcon(toast.type)" class="w-5 h-5 flex-shrink-0 mt-0.5" />
        <p class="flex-1 text-sm font-medium">{{ toast.message }}</p>
        <button
          @click="store.removeToast(toast.id)"
          class="flex-shrink-0 hover:opacity-70 transition-opacity"
        >
          <X class="w-4 h-4" />
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}

.toast-enter-from {
  opacity: 0;
  transform: translateX(100%);
}

.toast-leave-to {
  opacity: 0;
  transform: translateX(100%);
}

.toast-move {
  transition: transform 0.3s ease;
}
</style>
