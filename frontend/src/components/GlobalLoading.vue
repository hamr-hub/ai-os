<script setup lang="ts">
import { useGlobalState } from '@/composables/useGlobalState'

const { isLoading, loadingMessage } = useGlobalState()
</script>

<template>
  <Transition name="loading">
    <div
      v-if="isLoading"
      class="fixed inset-0 bg-black/50 backdrop-blur-md flex items-center justify-center z-[100]"
    >
      <div class="bg-card backdrop-blur-xl rounded-2xl p-8 shadow-2xl border border-primary scale-in">
        <div class="flex flex-col items-center gap-4">
          <div class="relative">
            <div class="w-14 h-14 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
            <div class="absolute inset-0 w-14 h-14 border-4 border-purple-500 border-b-transparent rounded-full animate-spin" style="animation-direction: reverse; animation-duration: 1.5s;"></div>
          </div>
          <div class="text-center">
            <p class="text-primary font-semibold text-lg">{{ loadingMessage }}</p>
            <p class="text-secondary text-sm mt-1">请稍候...</p>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.loading-enter-active,
.loading-leave-active {
  transition: opacity 0.3s ease;
}

.loading-enter-from,
.loading-leave-to {
  opacity: 0;
}
</style>
