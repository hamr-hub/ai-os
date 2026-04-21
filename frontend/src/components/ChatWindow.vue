<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { MessageSquare, Send, Loader2, Bot, User, RefreshCw, ChevronDown } from 'lucide-vue-next'
import { chatCompletionStream, type ChatMessage } from '@/api/client'
import { useModels } from '@/composables/useModels'
import { useAppStore } from '@/stores/app'

const { modelStatus, defaultModel } = useModels()
const store = useAppStore()

const messages = ref<(ChatMessage & { timestamp: Date })[]>([])
const inputMessage = ref('')
const isLoading = ref(false)
const chatContainer = ref<HTMLElement | null>(null)
const streamingMessageId = ref<number | null>(null)
const selectedModel = ref<string | null>(null)
const showModelDropdown = ref(false)

const addMessage = (role: 'user' | 'assistant' | 'system', content: string) => {
  messages.value.push({ role, content, timestamp: new Date() })
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
    messages.value.push({ role: 'assistant', content: '', timestamp: new Date() })
    streamingMessageId.value = assistantMessageIndex

    const modelToUse = selectedModel.value || defaultModel.value

    await chatCompletionStream(
      {
        model: modelToUse || undefined,
        messages: messages.value.slice(0, -1),
        max_tokens: 1024,
        temperature: 0.7,
      },
      (chunk) => {
        updateStreamingMessage(chunk)
      },
      (error) => {
        store.error(`请求失败: ${error.message}`)
        messages.value.push({ role: 'system', content: `Error: ${error.message}`, timestamp: new Date() })
        streamingMessageId.value = null
      }
    )

    streamingMessageId.value = null
    store.success('消息发送成功')
  } catch (error) {
    if (streamingMessageId.value !== null) {
      messages.value.splice(streamingMessageId.value, 1)
      streamingMessageId.value = null
    }
    const errorMessage = error instanceof Error ? error.message : 'Failed to get response'
    store.error(errorMessage)
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
  addMessage('system', '欢迎使用 AI 聊天！选择模型后开始对话。')
}

const selectModel = (modelName: string) => {
  selectedModel.value = selectedModel.value === modelName ? null : modelName
  showModelDropdown.value = false
  if (selectedModel.value) {
    store.info(`已选择模型: ${modelName}`)
  } else {
    store.info('使用默认模型')
  }
}

const formatTime = (date: Date) => {
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

const availableModels = () => {
  if (!modelStatus.value) return []
  return Object.keys(modelStatus.value).filter((name) => modelStatus.value![name].running)
}

addMessage('system', '欢迎使用 AI 聊天！选择模型后开始对话。')
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
          <p class="text-slate-400 text-sm">与 AI 模型进行对话测试</p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <div class="relative">
          <button
            @click="showModelDropdown = !showModelDropdown"
            class="flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg text-sm transition-colors"
          >
            <span v-if="selectedModel">{{ selectedModel }}</span>
            <span v-else-if="defaultModel">{{ defaultModel }} (默认)</span>
            <span v-else>选择模型</span>
            <ChevronDown class="w-4 h-4 transition-transform" :class="{ 'rotate-180': showModelDropdown }" />
          </button>
          <div
            v-if="showModelDropdown"
            class="absolute top-full right-0 mt-1 w-48 bg-slate-700 rounded-lg shadow-lg overflow-hidden z-10"
          >
            <button
              @click="selectModel('')"
              class="w-full px-4 py-2 text-left hover:bg-slate-600 text-slate-300 text-sm transition-colors"
              :class="{ 'bg-slate-600': !selectedModel }"
            >
              {{ defaultModel ? `${defaultModel} (默认)` : '无默认模型' }}
            </button>
            <div class="border-t border-slate-600 my-1"></div>
            <button
              v-for="model in availableModels()"
              :key="model"
              @click="selectModel(model)"
              class="w-full px-4 py-2 text-left hover:bg-slate-600 text-slate-300 text-sm transition-colors flex items-center gap-2"
              :class="{ 'bg-slate-600': selectedModel === model }"
            >
              <span class="w-2 h-2 rounded-full bg-green-500"></span>
              {{ model }}
            </button>
            <div v-if="availableModels().length === 0" class="px-4 py-2 text-slate-500 text-sm">
              暂无运行中的模型
            </div>
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
          class="max-w-[80%]"
        >
          <div
            class="px-4 py-2 rounded-lg"
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
          <p class="text-xs text-slate-500 mt-1 ml-1" :class="{ 'text-right': message.role === 'user' }">
            {{ formatTime(message.timestamp) }}
          </p>
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
      <span v-if="selectedModel">当前模型: {{ selectedModel }} (手动选择)</span>
      <span v-else-if="defaultModel">当前模型: {{ defaultModel }} (默认)</span>
      <span v-else>未设置模型，请先选择或切换模型</span>
    </div>
  </div>
</template>
