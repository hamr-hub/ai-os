<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { MessageSquare, Send, Loader2, Bot, User, RefreshCw } from 'lucide-vue-next'
import { chatCompletionStream, type ChatMessage } from '@/api/client'
import { useModels } from '@/composables/useModels'

const { defaultModel } = useModels()

const messages = ref<ChatMessage[]>([])
const inputMessage = ref('')
const isLoading = ref(false)
const chatContainer = ref<HTMLElement | null>(null)
const streamingMessageId = ref<number | null>(null)

const addMessage = (role: 'user' | 'assistant' | 'system', content: string) => {
  messages.value.push({ role, content })
  nextTick(() => {
    scrollToBottom()
  })
}

const updateStreamingMessage = (content: string) => {
  if (streamingMessageId.value !== null) {
    messages.value[streamingMessageId.value].content += content
    nextTick(() => {
      scrollToBottom()
    })
  }
}

const scrollToBottom = () => {
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}

const handleSend = async () => {
  if (!inputMessage.value.trim() || isLoading.value) return

  const userMessage = inputMessage.value.trim()
  inputMessage.value = ''
  addMessage('user', userMessage)
  isLoading.value = true

  try {
    const assistantMessageIndex = messages.value.length
    messages.value.push({ role: 'assistant', content: '' })
    streamingMessageId.value = assistantMessageIndex

    await chatCompletionStream(
      {
        model: defaultModel.value || undefined,
        messages: messages.value.slice(0, -1),
        max_tokens: 1024,
        temperature: 0.7,
      },
      (chunk) => {
        updateStreamingMessage(chunk)
      },
      (error) => {
        messages.value.push({ role: 'system', content: `Error: ${error.message}` })
        streamingMessageId.value = null
      }
    )

    streamingMessageId.value = null
  } catch (error) {
    if (streamingMessageId.value !== null) {
      messages.value.splice(streamingMessageId.value, 1)
      streamingMessageId.value = null
    }
    const errorMessage = error instanceof Error ? error.message : 'Failed to get response'
    addMessage('system', `Error: ${errorMessage}`)
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

const clearChat = () => {
  messages.value = []
  addMessage('system', '欢迎使用 AI 聊天！当前使用的是默认模型。')
}

addMessage('system', '欢迎使用 AI 聊天！当前使用的是默认模型。')
</script>

<template>
  <div class="bg-slate-800 rounded-xl p-6">
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center">
          <MessageSquare class="w-6 h-6 text-white" />
        </div>
        <div>
          <h2 class="text-xl font-semibold text-white">聊天测试</h2>
          <p class="text-slate-400 text-sm">与默认模型进行对话测试</p>
        </div>
      </div>
      <button
        @click="clearChat"
        class="flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg text-sm transition-colors"
      >
        <RefreshCw class="w-4 h-4" />
        清空
      </button>
    </div>

    <div
      ref="chatContainer"
      class="h-64 overflow-y-auto bg-slate-900 rounded-lg p-4 mb-4 space-y-4"
    >
      <div
        v-for="(message, index) in messages"
        :key="index"
        class="flex gap-3"
        :class="{ 'flex-row-reverse': message.role === 'user' }"
      >
        <div
          class="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
          :class="{
            'bg-blue-600': message.role === 'user',
            'bg-purple-600': message.role === 'assistant',
            'bg-slate-600': message.role === 'system',
          }"
        >
          <User v-if="message.role === 'user'" class="w-5 h-5 text-white" />
          <Bot v-else-if="message.role === 'assistant'" class="w-5 h-5 text-white" />
        </div>
        <div
          class="max-w-[80%] px-4 py-2 rounded-lg"
          :class="{
            'bg-blue-600/20 text-blue-200 rounded-br-none': message.role === 'user',
            'bg-slate-700 text-white rounded-bl-none': message.role === 'assistant',
            'bg-slate-700/50 text-slate-300 rounded-lg': message.role === 'system',
          }"
        >
          <p class="text-sm whitespace-pre-wrap">{{ message.content }}</p>
          <span
            v-if="streamingMessageId === index"
            class="inline-block w-2 h-4 bg-white/60 ml-1 animate-pulse"
          ></span>
        </div>
      </div>

      <div v-if="isLoading && streamingMessageId === null" class="flex items-center gap-2 text-slate-400">
        <Loader2 class="w-4 h-4 animate-spin" />
        <span class="text-sm">正在思考...</span>
      </div>
    </div>

    <div class="flex gap-3">
      <input
        v-model="inputMessage"
        @keydown="handleKeyPress"
        type="text"
        placeholder="输入消息..."
        class="flex-1 bg-slate-700 text-white border border-slate-600 rounded-lg px-4 py-3 focus:outline-none focus:border-blue-500"
        :disabled="isLoading"
      />
      <button
        @click="handleSend"
        :disabled="isLoading || !inputMessage.trim()"
        class="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-600/50 disabled:cursor-not-allowed text-white rounded-lg transition-colors flex items-center gap-2"
      >
        <Loader2 v-if="isLoading" class="w-4 h-4 animate-spin" />
        <Send v-else class="w-4 h-4" />
        <span>发送</span>
      </button>
    </div>

    <div class="mt-4 text-center text-slate-500 text-xs">
      <span v-if="defaultModel">当前模型: {{ defaultModel }}</span>
      <span v-else>未设置默认模型，请先切换模型</span>
    </div>
  </div>
</template>
