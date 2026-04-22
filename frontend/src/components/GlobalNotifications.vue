<script setup lang="ts">
import { useGlobalState } from '@/composables/useGlobalState'
import { XCircle, AlertTriangle, Info, X } from 'lucide-vue-next'

const { errors, removeError } = useGlobalState()

const getIcon = (type: string) => {
  switch (type) {
    case 'error':
      return XCircle
    case 'warning':
      return AlertTriangle
    case 'info':
      return Info
    default:
      return Info
  }
}

const getColors = (type: string) => {
  switch (type) {
    case 'error':
      return {
        bg: 'bg-red-500/15',
        border: 'border-red-500/40',
        text: 'text-red-400',
        iconBg: 'bg-red-500/20',
        closeHover: 'hover:bg-red-500/20'
      }
    case 'warning':
      return {
        bg: 'bg-yellow-500/15',
        border: 'border-yellow-500/40',
        text: 'text-yellow-400',
        iconBg: 'bg-yellow-500/20',
        closeHover: 'hover:bg-yellow-500/20'
      }
    case 'info':
      return {
        bg: 'bg-blue-500/15',
        border: 'border-blue-500/40',
        text: 'text-blue-400',
        iconBg: 'bg-blue-500/20',
        closeHover: 'hover:bg-blue-500/20'
      }
    default:
      return {
        bg: 'bg-gray-500/15',
        border: 'border-gray-500/40',
        text: 'text-gray-400',
        iconBg: 'bg-gray-500/20',
        closeHover: 'hover:bg-gray-500/20'
      }
  }
}
</script>

<template>
  <div class="fixed top-4 right-4 z-[100] max-w-md">
    <TransitionGroup name="notification" tag="div" class="space-y-3">
      <div
        v-for="error in errors"
        :key="error.id"
        class="flex items-center gap-3 p-4 rounded-xl border shadow-xl backdrop-blur-md"
        :class="[getColors(error.type).bg, getColors(error.type).border]"
      >
        <div class="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0" :class="getColors(error.type).iconBg">
          <component :is="getIcon(error.type)" class="w-5 h-5" :class="getColors(error.type).text" />
        </div>
        <div class="flex-1 min-w-0">
          <p class="text-sm font-medium text-primary">{{ error.message }}</p>
          <p class="text-xs text-muted mt-0.5">{{ error.timestamp.toLocaleTimeString('zh-CN') }}</p>
        </div>
        <button
          @click="removeError(error.id)"
          class="p-1.5 rounded-lg transition-colors"
          :class="getColors(error.type).closeHover"
        >
          <X class="w-4 h-4 text-muted" />
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.notification-enter-active {
  animation: notification-in 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.notification-leave-active {
  animation: notification-out 0.2s ease-out forwards;
}

.notification-move {
  transition: transform 0.3s ease;
}

@keyframes notification-in {
  from {
    opacity: 0;
    transform: translateX(50px) scale(0.9);
  }
  to {
    opacity: 1;
    transform: translateX(0) scale(1);
  }
}

@keyframes notification-out {
  from {
    opacity: 1;
    transform: translateX(0) scale(1);
  }
  to {
    opacity: 0;
    transform: translateX(50px) scale(0.9);
  }
}
</style>
