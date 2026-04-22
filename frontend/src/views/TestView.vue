<script setup lang="ts">
import ModelTester from '@/components/ModelTester.vue'
import { TestTube } from 'lucide-vue-next'
</script>

<template>
  <div class="space-y-6 p-6">
    <div class="flex items-center gap-4">
      <div class="w-12 h-12 rounded-xl flex items-center justify-center gradient-orange">
        <TestTube class="w-7 h-7 text-white" />
      </div>
      <div>
        <h1 class="text-2xl font-bold text-primary">模型检测</h1>
        <p class="text-secondary">检测模型支持的功能特性</p>
      </div>
    </div>

    <ModelTester />
  </div>
</template>
