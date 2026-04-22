<script setup lang="ts">
import ModelManager from '@/components/ModelManager.vue'
import { Server } from 'lucide-vue-next'
</script>

<template>
  <div class="view-page">
    <div class="view-header">
      <div class="header-icon purple">
        <Server class="w-6 h-6 text-white" />
      </div>
      <div>
        <h1 class="view-title">Model Management</h1>
        <p class="view-subtitle">Manage and control AI model services</p>
      </div>
    </div>
    <ModelManager />
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
  box-shadow: 0 4px 16px rgba(139, 92, 246, 0.3);
}

.header-icon.purple {
  background: linear-gradient(135deg, #8b5cf6, #7c3aed);
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
