<script setup lang="ts">
import GPUMonitor from '@/components/GPUMonitor.vue'
import ModelManager from '@/components/ModelManager.vue'
import ChatWindow from '@/components/ChatWindow.vue'
import ModelTester from '@/components/ModelTester.vue'
import { Server, Activity } from 'lucide-vue-next'
</script>

<template>
  <div class="min-h-screen bg-slate-900">
    <header class="bg-slate-800 border-b border-slate-700 px-6 py-4">
      <div class="max-w-7xl mx-auto flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
            <Server class="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 class="text-xl font-bold text-white">AI Controller</h1>
            <p class="text-slate-400 text-sm">GPU 监控与模型管理平台</p>
          </div>
        </div>
        <div class="flex items-center gap-2 text-sm text-slate-400">
          <Activity class="w-4 h-4" />
          <span>系统运行中</span>
        </div>
      </div>
    </header>

    <main class="max-w-7xl mx-auto px-6 py-8">
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <GPUMonitor />
        <ModelManager />
      </div>
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChatWindow />
        <ModelTester />
      </div>
    </main>

    <footer class="bg-slate-800 border-t border-slate-700 px-6 py-4 mt-auto">
      <div class="max-w-7xl mx-auto text-center text-slate-500 text-sm">
        AI Controller Management Console
      </div>
    </footer>
  </div>
</template>
