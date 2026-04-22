<script setup lang="ts">
import ModelTester from '@/components/ModelTester.vue'
import { TestTube } from 'lucide-vue-next'
</script>

<template>
  <div class="view-page">
    <div class="view-header">
      <div class="header-icon orange">
        <TestTube class="w-6 h-6 text-white" />
      </div>
      <div>
        <h1 class="view-title">Model Test</h1>
        <p class="view-subtitle">Test model capabilities and features</p>
      </div>
    </div>
    <ModelTester />
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
  box-shadow: 0 4px 16px rgba(245, 158, 11, 0.3);
}

.header-icon.orange {
  background: linear-gradient(135deg, #f59e0b, #ea580c);
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
