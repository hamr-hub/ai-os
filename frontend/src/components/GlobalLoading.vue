<script setup lang="ts">
import { useGlobalState } from '@/composables/useGlobalState'

const { isLoading, loadingMessage } = useGlobalState()
</script>

<template>
  <Transition name="fade">
    <div
      v-if="isLoading"
      class="fixed inset-0 bg-black/60 backdrop-blur-md flex items-center justify-center z-50"
    >
      <div class="bg-slate-800/90 rounded-2xl p-8 shadow-2xl border border-slate-700/50 scale-in">
        <div class="flex flex-col items-center gap-4">
          <div class="relative">
            <div class="w-14 h-14 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
            <div class="absolute inset-0 w-14 h-14 border-4 border-purple-500 border-b-transparent rounded-full animate-spin" style="animation-direction: reverse; animation-duration: 1.5s;"></div>
          </div>
          <div class="text-center">
            <p class="text-white font-semibold text-lg">{{ loadingMessage }}</p>
            <p class="text-slate-400 text-sm mt-1">请稍候...</p>
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
