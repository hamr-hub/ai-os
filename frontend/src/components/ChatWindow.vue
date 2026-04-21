<script setup lang="ts">
import { ref, nextTick, computed } from 'vue'
import { MessageSquare, Send, Loader2, Bot, User, Paperclip, Smile, Image, Mic, Check, CheckCheck } from 'lucide-vue-next'
import { chatCompletion, type ChatMessage } from '@/api/client'
import { useModels } from '@/composables/useModels'

const { defaultModel } = useModels()

interface ChatMessageWithStatus extends ChatMessage {
  id: number
  status: 'sending' | 'sent' | 'received'
}

const messages = ref<ChatMessageWithStatus[]>([])
const inputMessage = ref('')
const isLoading = ref(false)
const chatContainer = ref<HTMLElement | null>(null)
const messageIdCounter = ref(0)

const isInputDisabled = computed(() => isLoading.value || !inputMessage.value.trim())

const addMessage = (role: 'user' | 'assistant' | 'system', content: string, status: 'sending' | 'sent' | 'received' = 'received') => {
  messages.value.push({
    id: messageIdCounter.value++,
    role,
    content,
    status
  })
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

const handleSend = async () => {
  if (isInputDisabled.value) return
  
  const userMessage = inputMessage.value.trim()
  inputMessage.value = ''
  
  const messageId = messageIdCounter.value
  addMessage('user', userMessage, 'sending')
  
  isLoading.value = true
  
  try {
    const response = await chatCompletion({
      model: defaultModel.value || undefined,
      messages: messages.value.map(m => ({ role: m.role, content: m.content })),
      max_tokens: 1024,
      temperature: 0.7
    })
    
    messages.value.find(m => m.id === messageId)!.status = 'sent'
    
    if (response.choices && response.choices.length > 0) {
      addMessage('assistant', response.choices[0].message.content, 'received')
    }
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Failed to get response'
    addMessage('system', `Error: ${errorMessage}`, 'received')
  } finally {
    isLoading.value = false
  }
}

const handleKeyPress = (event: KeyboardEvent) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    handleSend()
  }
}

addMessage('system', '欢迎使用 AI 聊天！当前使用的是默认模型。', 'received')
</script>

<template>
  <div class="bg-slate-800 rounded-xl p-6 h-full flex flex-col">
    <div class="flex items-center justify-between mb-4">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center">
          <MessageSquare class="w-6 h-6 text-white" />
        </div>
        <div>
          <h2 class="text-xl font-semibold text-white">聊天测试</h2>
          <p class="text-slate-400 text-sm">与默认模型进行对话测试</p>
        </div>
      </div>
      <div v-if="defaultModel" class="px-3 py-1 bg-blue-600/20 text-blue-400 rounded-full text-sm">
        {{ defaultModel }}
      </div>
    </div>

    <div
      ref="chatContainer"
      class="flex-1 overflow-y-auto bg-slate-900 rounded-lg p-4 space-y-4 mb-4 min-h-[200px]"
    >
      <div
        v-for="(message, index) in messages"
        :key="message.id"
        class="flex gap-3"
        :class="{ 'flex-row-reverse': message.role === 'user' }"
      >
        <div
          class="w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0"
          :class="{
            'bg-blue-600': message.role === 'user',
            'bg-purple-600': message.role === 'assistant',
            'bg-slate-600': message.role === 'system'
          }"
        >
          <User v-if="message.role === 'user'" class="w-5 h-5 text-white" />
          <Bot v-else-if="message.role === 'assistant'" class="w-5 h-5 text-white" />
        </div>
        <div class="flex flex-col max-w-[80%]" :class="{ 'items-end': message.role === 'user' }">
          <div
            class="px-4 py-3 rounded-lg"
            :class="{
              'bg-blue-600/20 text-blue-200 rounded-br-md': message.role === 'user',
              'bg-slate-700 text-white rounded-bl-md': message.role === 'assistant',
              'bg-slate-700/50 text-slate-300 rounded-lg': message.role === 'system'
            }"
          >
            <p class="text-sm whitespace-pre-wrap leading-relaxed">{{ message.content }}</p>
          </div>
          <div v-if="message.role === 'user'" class="flex items-center gap-1 mt-1">
            <Loader2 v-if="message.status === 'sending'" class="w-3 h-3 text-slate-500 animate-spin" />
            <Check v-else-if="message.status === 'sent'" class="w-3 h-3 text-slate-500" />
            <CheckCheck v-else class="w-3 h-3 text-green-500" />
            <span class="text-xs text-slate-500 ml-1">
              {{ message.status === 'sending' ? '发送中...' : message.status === 'sent' ? '已发送' : '已送达' }}
            </span>
          </div>
        </div>
      </div>

      <div v-if="isLoading" class="flex items-center gap-2 text-slate-400 animate-pulse">
        <div class="flex gap-1">
          <span class="w-2 h-2 bg-slate-500 rounded-full animate-bounce" style="animation-delay: 0ms"></span>
          <span class="w-2 h-2 bg-slate-500 rounded-full animate-bounce" style="animation-delay: 150ms"></span>
          <span class="w-2 h-2 bg-slate-500 rounded-full animate-bounce" style="animation-delay: 300ms"></span>
        </div>
        <span class="text-sm">正在思考...</span>
      </div>
    </div>

    <div class="bg-slate-700/50 rounded-xl p-3">
      <div class="flex items-center gap-2 mb-2">
        <button class="p-2 hover:bg-slate-600 rounded-lg text-slate-400 hover:text-white transition-colors">
          <Paperclip class="w-5 h-5" />
        </button>
        <button class="p-2 hover:bg-slate-600 rounded-lg text-slate-400 hover:text-white transition-colors">
          <Image class="w-5 h-5" />
        </button>
        <div class="flex-1 relative">
          <textarea
            v-model="inputMessage"
            @keydown="handleKeyPress"
            placeholder="输入消息..."
            rows="2"
            class="w-full bg-transparent text-white placeholder-slate-500 border-none outline-none resize-none text-sm leading-relaxed"
            :disabled="isLoading"
          ></textarea>
        </div>
        <button class="p-2 hover:bg-slate-600 rounded-lg text-slate-400 hover:text-white transition-colors">
          <Smile class="w-5 h-5" />
        </button>
        <button class="p-2 hover:bg-slate-600 rounded-lg text-slate-400 hover:text-white transition-colors">
          <Mic class="w-5 h-5" />
        </button>
      </div>
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span v-if="!defaultModel" class="text-xs text-yellow-500">
            ⚠️ 未设置默认模型
          </span>
        </div>
        <button
          @click="handleSend"
          :disabled="isInputDisabled"
          class="px-5 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-600/50 disabled:cursor-not-allowed text-white rounded-lg transition-colors flex items-center gap-2 text-sm font-medium"
        >
          <Loader2 v-if="isLoading" class="w-4 h-4 animate-spin" />
          <Send v-else class="w-4 h-4" />
          <span>发送</span>
        </button>
      </div>
    </div>
  </div>
</template>
