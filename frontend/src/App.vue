<script setup lang="ts">
import { computed } from 'vue'
import { RouterView } from 'vue-router'
import Sidebar from '@/components/Sidebar.vue'
import ToastContainer from '@/components/ToastContainer.vue'
import { useAppStore } from '@/stores/app'
import { onMounted } from 'vue'

const store = useAppStore()

onMounted(() => {
  store.initTheme()
})

const mainMargin = computed(() => store.sidebarCollapsed ? '64px' : '220px')
</script>

<template>
  <div class="app-shell">
    <ToastContainer />
    <Sidebar />
    <main class="app-main" :style="{ marginLeft: mainMargin }">
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
  display: flex;
}

.app-main {
  flex: 1;
  min-height: 100vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background-color: var(--bg-primary);
  transition: margin-left 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.app-page {
  flex: 1;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

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
