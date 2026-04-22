<script setup lang="ts">
import GPUMonitor from '@/components/GPUMonitor.vue'
import { Cpu } from 'lucide-vue-next'
</script>

<template>
  <div class="view-page">
    <div class="view-header">
      <div class="header-icon blue">
        <Cpu class="w-6 h-6 text-white" />
      </div>
      <div>
        <h1 class="view-title">GPU Monitor</h1>
        <p class="view-subtitle">Real-time GPU status and performance metrics</p>
      </div>
    </div>
    <GPUMonitor />
  </div>
</template>

<style scoped>
.view-page {
  padding: 24px 28px;
  height: 100%;
  overflow-y: auto;
  background: var(--bg-primary);
}

.view-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
}

.header-icon {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 16px rgba(99, 102, 241, 0.3);
}

.header-icon.blue {
  background: linear-gradient(135deg, #6366f1, #4f46e5);
}

.view-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.5px;
}

.view-subtitle {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 2px;
}
</style>
