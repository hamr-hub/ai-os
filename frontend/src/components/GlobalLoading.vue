<script setup lang="ts">
import { useGlobalState } from '@/composables/useGlobalState'
import { Loader2 } from 'lucide-vue-next'

const { isLoading, loadingMessage } = useGlobalState()
</script>

<template>
  <Transition name="fade">
    <div
      v-if="isLoading"
      class="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50"
    >
      <div class="bg-slate-800 rounded-xl p-6 shadow-2xl">
        <div class="flex flex-col items-center gap-4">
          <div class="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
          <div>
            <p class="text-white font-medium">{{ loadingMessage }}</p>
            <p class="text-slate-400 text-sm text-center">请稍候...</p>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
