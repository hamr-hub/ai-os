<script setup lang="ts">
import GPUMonitor from '@/components/GPUMonitor.vue'
import { Cpu } from 'lucide-vue-next'
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center gap-4">
      <div class="w-12 h-12 bg-blue-600 rounded-xl flex items-center justify-center">
        <Cpu class="w-7 h-7 text-white" />
      </div>
      <div>
        <h1 class="text-2xl font-bold text-white">GPU 监控</h1>
        <p class="text-slate-400">实时监控 GPU 状态和性能指标</p>
      </div>
    </div>

    <GPUMonitor />
  </div>
</template>
