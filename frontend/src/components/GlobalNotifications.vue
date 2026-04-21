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
        bg: 'bg-red-500/10',
        border: 'border-red-500/30',
        text: 'text-red-400',
        iconBg: 'bg-red-500/20'
      }
    case 'warning':
      return {
        bg: 'bg-yellow-500/10',
        border: 'border-yellow-500/30',
        text: 'text-yellow-400',
        iconBg: 'bg-yellow-500/20'
      }
    case 'info':
      return {
        bg: 'bg-blue-500/10',
        border: 'border-blue-500/30',
        text: 'text-blue-400',
        iconBg: 'bg-blue-500/20'
      }
    default:
      return {
        bg: 'bg-gray-500/10',
        border: 'border-gray-500/30',
        text: 'text-gray-400',
        iconBg: 'bg-gray-500/20'
      }
  }
}
</script>

<template>
  <div class="fixed top-4 right-4 z-50 space-y-2 max-w-md">
    <TransitionGroup name="notification">
      <div
        v-for="error in errors"
        :key="error.id"
        class="flex items-center gap-3 p-4 rounded-lg border shadow-lg backdrop-blur-sm"
        :class="[getColors(error.type).bg, getColors(error.type).border]"
      >
        <div class="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0" :class="getColors(error.type).iconBg">
          <component :is="getIcon(error.type)" class="w-4 h-4" :class="getColors(error.type).text" />
        </div>
        <div class="flex-1">
          <p class="text-sm text-white">{{ error.message }}</p>
          <p class="text-xs text-slate-500">{{ error.timestamp.toLocaleTimeString('zh-CN') }}</p>
        </div>
        <button
          @click="removeError(error.id)"
          class="p-1 hover:bg-white/10 rounded transition-colors"
        >
          <X class="w-4 h-4 text-slate-400" />
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.notification-enter-active,
.notification-leave-active {
  transition: all 0.3s ease;
}

.notification-enter-from {
  opacity: 0;
  transform: translateX(100%);
}

.notification-leave-to {
  opacity: 0;
  transform: translateX(100%);
}

.notification-move {
  transition: transform 0.3s ease;
}
</style>
