<script setup lang="ts">
import ModelManager from '@/components/ModelManager.vue'
import { Server } from 'lucide-vue-next'
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center gap-4">
      <div class="w-12 h-12 bg-purple-600 rounded-xl flex items-center justify-center">
        <Server class="w-7 h-7 text-white" />
      </div>
      <div>
        <h1 class="text-2xl font-bold text-white">模型管理</h1>
        <p class="text-slate-400">管理和控制 AI 模型服务</p>
      </div>
    </div>

    <ModelManager />
  </div>
</template>
