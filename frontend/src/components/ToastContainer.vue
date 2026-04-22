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
      return 'bg-green-500/20 border-green-500/40 text-green-400'
    case 'error':
      return 'bg-red-500/20 border-red-500/40 text-red-400'
    case 'warning':
      return 'bg-yellow-500/20 border-yellow-500/40 text-yellow-400'
    case 'info':
    default:
      return 'bg-blue-500/20 border-blue-500/40 text-blue-400'
  }
}
</script>

<template>
  <div class="fixed top-6 right-6 z-[100] flex flex-col gap-3 max-w-sm">
    <TransitionGroup name="toast" tag="div" class="flex flex-col gap-3">
      <div
        v-for="toast in store.toasts"
        :key="toast.id"
        class="flex items-start gap-3 px-4 py-3.5 rounded-xl border backdrop-blur-md shadow-xl hover:shadow-2xl transition-shadow duration-200"
        :class="getToastClass(toast.type)"
      >
        <component :is="getToastIcon(toast.type)" class="w-5 h-5 flex-shrink-0 mt-0.5" />
        <p class="flex-1 text-sm font-medium leading-relaxed">{{ toast.message }}</p>
        <button
          @click="store.removeToast(toast.id)"
          class="flex-shrink-0 p-1 rounded-lg hover:bg-white/10 transition-colors"
        >
          <X class="w-4 h-4" />
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-enter-active {
  animation: toast-in 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.toast-leave-active {
  animation: toast-out 0.2s ease-out forwards;
}

.toast-move {
  transition: transform 0.3s ease;
}

@keyframes toast-in {
  from {
    opacity: 0;
    transform: translateX(100%) scale(0.8);
  }
  to {
    opacity: 1;
    transform: translateX(0) scale(1);
  }
}

@keyframes toast-out {
  from {
    opacity: 1;
    transform: translateX(0) scale(1);
  }
  to {
    opacity: 0;
    transform: translateX(100%) scale(0.8);
  }
}
</style>
