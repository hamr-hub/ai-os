<script setup lang="ts">
import { RouterView } from 'vue-router'
import Sidebar from '@/components/Sidebar.vue'
import ToastContainer from '@/components/ToastContainer.vue'
import { useAppStore } from '@/stores/app'

const store = useAppStore()
</script>

<template>
  <div class="min-h-screen bg-slate-900">
    <ToastContainer />
    <Sidebar />
    
    <main class="transition-all duration-300" :class="store.sidebarCollapsed ? 'ml-16' : 'ml-56'">
      <div class="p-6">
        <RouterView />
      </div>
    </main>
  </div>
</template>
