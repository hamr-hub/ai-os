<script setup lang="ts">
import { RouterView } from 'vue-router'
import Sidebar from '@/components/Sidebar.vue'
import ToastContainer from '@/components/ToastContainer.vue'
import { useAppStore } from '@/stores/app'
import { onMounted } from 'vue'

const store = useAppStore()

onMounted(() => {
  store.initTheme()
})
</script>

<template>
  <div class="min-h-screen bg-primary noise-overlay">
    <ToastContainer />
    <Sidebar />

    <main
      class="transition-all duration-300 ease-out"
      :class="store.sidebarCollapsed ? 'ml-16' : 'ml-64'"
    >
      <div class="h-screen overflow-hidden">
        <RouterView v-slot="{ Component }">
          <transition name="page" mode="out-in">
            <component :is="Component" />
          </transition>
        </RouterView>
      </div>
    </main>
  </div>
</template>

<style scoped>
.page-enter-active,
.page-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.page-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

.page-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
