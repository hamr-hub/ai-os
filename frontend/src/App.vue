<script setup lang="ts">
import { RouterView } from 'vue-router'
import Sidebar from '@/components/Sidebar.vue'
import ToastContainer from '@/components/ToastContainer.vue'
import { useAppStore } from '@/stores/app'
import { onMounted, computed } from 'vue'

const store = useAppStore()

onMounted(() => {
  store.initTheme()
})

const sidebarWidth = computed(() => store.sidebarCollapsed ? '4rem' : '16rem')
</script>

<template>
  <div class="app-shell">
    <ToastContainer />
    <Sidebar />

    <main
      class="app-main"
      :style="{ marginLeft: sidebarWidth }"
    >
      <RouterView v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" class="app-page" />
        </transition>
      </RouterView>
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  background-color: var(--bg-primary);
  color: var(--text-primary);
}

.app-main {
  height: 100vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: margin-left 0.3s ease;
}

.app-page {
  flex: 1;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.page-enter-active,
.page-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.page-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

.page-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
