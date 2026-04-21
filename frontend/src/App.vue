<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import GPUMonitor from '@/components/GPUMonitor.vue'
import ModelManager from '@/components/ModelManager.vue'
import ChatWindow from '@/components/ChatWindow.vue'
import ModelTester from '@/components/ModelTester.vue'
import GlobalNotifications from '@/components/GlobalNotifications.vue'
import GlobalLoading from '@/components/GlobalLoading.vue'
import { Server, Activity, Bell, Settings, HelpCircle, ChevronDown } from 'lucide-vue-next'

const currentTime = ref(new Date())

let timeInterval: number | null = null

onMounted(() => {
  timeInterval = window.setInterval(() => {
    currentTime.value = new Date()
  }, 1000)
})

onUnmounted(() => {
  if (timeInterval) {
    clearInterval(timeInterval)
  }
})

const formatTime = (date: Date) => {
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}
</script>

<template>
  <div class="min-h-screen bg-slate-900 flex flex-col">
    <GlobalNotifications />
    <GlobalLoading />

    <header class="bg-slate-800 border-b border-slate-700 px-4 sm:px-6 lg:px-8 py-3 sticky top-0 z-40">
      <div class="max-w-7xl mx-auto flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
            <Server class="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 class="text-lg font-bold text-white">AI Controller</h1>
            <p class="text-slate-400 text-xs">GPU 监控与模型管理平台</p>
          </div>
        </div>

        <div class="flex items-center gap-4">
          <div class="hidden sm:flex items-center gap-2 text-slate-400">
            <Activity class="w-4 h-4 text-green-400" />
            <span class="text-sm">系统运行中</span>
          </div>

          <div class="text-right hidden sm:block">
            <p class="text-xs text-slate-500">当前时间</p>
            <p class="text-sm text-slate-300 font-mono">{{ formatTime(currentTime) }}</p>
          </div>

          <div class="flex items-center gap-2">
            <button class="p-2 hover:bg-slate-700 rounded-lg text-slate-400 hover:text-white transition-colors relative">
              <Bell class="w-5 h-5" />
              <span class="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full"></span>
            </button>
            <button class="p-2 hover:bg-slate-700 rounded-lg text-slate-400 hover:text-white transition-colors">
              <HelpCircle class="w-5 h-5" />
            </button>
            <button class="p-2 hover:bg-slate-700 rounded-lg text-slate-400 hover:text-white transition-colors">
              <Settings class="w-5 h-5" />
            </button>
            <div class="w-px h-6 bg-slate-600"></div>
            <button class="flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors">
              <div class="w-7 h-7 bg-blue-600 rounded-full flex items-center justify-center">
                <span class="text-white text-xs font-medium">A</span>
              </div>
              <span class="text-sm text-white hidden sm:block">Admin</span>
              <ChevronDown class="w-4 h-4 text-slate-400" />
            </button>
          </div>
        </div>
      </div>
    </header>

    <main class="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-6">
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div class="space-y-6">
          <GPUMonitor />
          <ChatWindow />
        </div>
        <div class="space-y-6">
          <ModelManager />
          <ModelTester />
        </div>
      </div>
    </main>

    <footer class="bg-slate-800 border-t border-slate-700 px-4 sm:px-6 lg:px-8 py-4">
      <div class="max-w-7xl mx-auto">
        <div class="flex flex-col sm:flex-row items-center justify-between gap-2">
          <div class="text-center sm:text-left">
            <p class="text-slate-500 text-sm">AI Controller Management Console</p>
            <p class="text-slate-600 text-xs">Version 1.0.0 | Built with Vue 3 + TypeScript</p>
          </div>
          <div class="flex items-center gap-4 text-xs text-slate-500">
            <span>服务状态: <span class="text-green-400">正常</span></span>
            <span>|</span>
            <span>API 版本: v1</span>
            <span>|</span>
            <span>文档</span>
            <span>|</span>
            <span>支持</span>
          </div>
        </div>
      </div>
    </footer>
  </div>
</template>
