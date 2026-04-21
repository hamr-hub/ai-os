<script setup lang="ts">
import ChatWindow from '@/components/ChatWindow.vue'
import { MessageSquare } from 'lucide-vue-next'
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center gap-4">
      <div class="w-12 h-12 bg-blue-600 rounded-xl flex items-center justify-center">
        <MessageSquare class="w-7 h-7 text-white" />
      </div>
      <div>
        <h1 class="text-2xl font-bold text-white">聊天测试</h1>
        <p class="text-slate-400">与 AI 模型进行对话测试</p>
      </div>
    </div>

    <ChatWindow />
  </div>
</template>
