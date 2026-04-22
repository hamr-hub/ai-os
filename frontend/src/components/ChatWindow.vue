<script setup lang="ts">
import { ref, nextTick, computed, watch } from 'vue'
import { Send, Loader2, Bot, User, Sparkles, StopCircle } from 'lucide-vue-next'
import { chatCompletionStream, type ChatMessage } from '@/api/client'
import { useModels } from '@/composables/useModels'
import { useAppStore } from '@/stores/app'
import { useChatStore } from '@/stores/chat'

const { defaultModel } = useModels()
const appStore = useAppStore()
const chatStore = useChatStore()

const inputMessage = ref('')
const isLoading = ref(false)
const chatContainer = ref<HTMLElement | null>(null)
const streamingMessageId = ref<string | null>(null)
const abortController = ref<AbortController | null>(null)

const currentConv = computed(() => chatStore.currentConversation)
const messages = computed(() => currentConv.value?.messages || [])

watch(currentConv, () => {
  nextTick(() => scrollToBottom())
}, { immediate: true })

const scrollToBottom = () => {
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}

const addMessage = (role: 'user' | 'assistant' | 'system', content: string) => {
  if (!currentConv.value) return null
  const message = chatStore.addMessage(currentConv.value.id, role, content)
  nextTick(() => scrollToBottom())
  return message
}

const handleSend = async () => {
  if (!inputMessage.value.trim() || isLoading.value || !currentConv.value) return

  const userMessage = inputMessage.value.trim()
  inputMessage.value = ''
  addMessage('user', userMessage)
  isLoading.value = true

  try {
    const assistantMessage = addMessage('assistant', '')
    if (!assistantMessage) return
    
    streamingMessageId.value = assistantMessage.id
    abortController.value = new AbortController()

    const apiMessages: ChatMessage[] = messages.value
      .filter(m => m.role !== 'system')
      .slice(0, -1)
      .map(m => ({ role: m.role, content: m.content }))

    await chatCompletionStream(
      {
        model: defaultModel.value || undefined,
        messages: apiMessages,
        max_tokens: 2048,
        temperature: 0.7,
      },
      (chunk) => {
        if (streamingMessageId.value && currentConv.value) {
          const msg = currentConv.value.messages.find(m => m.id === streamingMessageId.value)
          if (msg) {
            msg.content += chunk
            nextTick(() => scrollToBottom())
          }
        }
      },
      (error) => {
        appStore.error(`请求失败: ${error.message}`)
        streamingMessageId.value = null
      },
      abortController.value.signal
    )

    streamingMessageId.value = null
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      return
    }
    const errorMessage = error instanceof Error ? error.message : 'Failed to get response'
    appStore.error(errorMessage)
    addMessage('system', `Error: ${errorMessage}`)
  } finally {
    isLoading.value = false
    abortController.value = null
  }
}

const handleStop = () => {
  if (abortController.value) {
    abortController.value.abort()
    isLoading.value = false
    streamingMessageId.value = null
  }
}

const handleKeyPress = (event: KeyboardEvent) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    handleSend()
  }
}

const formatTime = (date: Date) => {
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

const handleNewChat = () => {
  chatStore.createConversation()
}
</script>

<template>
  <div class="flex flex-col h-full bg-primary">
    <div v-if="!currentConv" class="flex-1 flex items-center justify-center noise-overlay">
      <div class="text-center scale-in">
        <div class="w-20 h-20 mx-auto mb-5 rounded-2xl gradient-primary flex items-center justify-center shadow-lg animate-float">
          <Sparkles class="w-10 h-10 text-white" />
        </div>
        <h2 class="text-2xl font-semibold text-primary mb-2">欢迎使用 AI 聊天</h2>
        <p class="text-secondary mb-6">选择或创建一个会话开始对话</p>
        <button
          @click="handleNewChat"
          class="px-6 py-3 gradient-primary hover:opacity-90 text-white rounded-xl transition-all btn-glow border-glow"
        >
          创建新会话
        </button>
      </div>
    </div>

    <template v-else>
      <div
        ref="chatContainer"
        class="flex-1 overflow-y-auto p-6 space-y-5 scrollbar-thin"
      >
        <div v-if="messages.length === 0" class="text-center py-16 text-muted">
          <div class="w-16 h-16 mx-auto mb-4 rounded-2xl bg-tertiary flex items-center justify-center">
            <Bot class="w-8 h-8 opacity-50" />
          </div>
          <p class="text-sm">发送消息开始对话</p>
        </div>

        <div
          v-for="message in messages"
          :key="message.id"
          class="flex gap-4 fade-in"
          :class="{ 'flex-row-reverse': message.role === 'user' }"
        >
          <div
            class="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 shadow-md"
            :class="{
              'gradient-blue': message.role === 'user',
              'gradient-purple': message.role === 'assistant',
              'bg-tertiary': message.role === 'system',
            }"
          >
            <User v-if="message.role === 'user'" class="w-5 h-5 text-white" />
            <Bot v-else-if="message.role === 'assistant'" class="w-5 h-5 text-white" />
            <Sparkles v-else class="w-5 h-5 text-white" />
          </div>

          <div class="flex-1 max-w-[80%]">
            <div
              class="px-5 py-3 rounded-2xl shadow-sm"
              :class="{
                'gradient-blue text-white rounded-tr-md': message.role === 'user',
                'bg-secondary text-primary rounded-tl-md border border-primary': message.role === 'assistant',
                'bg-tertiary text-secondary rounded-xl': message.role === 'system',
              }"
            >
              <p class="text-sm whitespace-pre-wrap leading-relaxed text-balance">{{ message.content }}</p>

              <span
                v-if="streamingMessageId === message.id"
                class="inline-flex gap-1 ml-1 mt-1"
              >
                <span class="w-1.5 h-3 bg-white/60 rounded animate-bounce" style="animation-delay: 0ms"></span>
                <span class="w-1.5 h-3 bg-white/60 rounded animate-bounce" style="animation-delay: 150ms"></span>
                <span class="w-1.5 h-3 bg-white/60 rounded animate-bounce" style="animation-delay: 300ms"></span>
              </span>
            </div>
            <p
              class="text-xs text-muted mt-2 ml-1"
              :class="{ 'text-right': message.role === 'user' }"
            >
              {{ formatTime(message.timestamp) }}
            </p>
          </div>
        </div>

        <div v-if="isLoading && !streamingMessageId" class="flex items-center gap-2 text-muted py-4">
          <Loader2 class="w-4 h-4 animate-spin" />
          <span class="text-sm">正在思考...</span>
        </div>
      </div>

      <div class="p-5 border-t border-primary bg-secondary/50 backdrop-blur-sm">
        <div class="flex gap-3 items-end max-w-4xl mx-auto">
          <textarea
            v-model="inputMessage"
            @keydown="handleKeyPress"
            placeholder="输入消息... (Enter 发送, Shift+Enter 换行)"
            class="flex-1 bg-input text-primary border border-secondary rounded-2xl px-5 py-4 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all placeholder:text-muted resize-none min-h-[52px] max-h-40 scrollbar-thin"
            :disabled="isLoading"
            rows="1"
          ></textarea>
          <button
            v-if="!isLoading"
            @click="handleSend"
            :disabled="!inputMessage.trim()"
            class="w-12 h-12 gradient-primary hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl transition-all flex items-center justify-center btn-glow shadow-lg flex-shrink-0"
          >
            <Send class="w-5 h-5" />
          </button>
          <button
            v-else
            @click="handleStop"
            class="w-12 h-12 bg-red-500 hover:bg-red-600 text-white rounded-xl transition-all flex items-center justify-center shadow-lg flex-shrink-0"
          >
            <StopCircle class="w-5 h-5" />
          </button>
        </div>

        <div class="mt-3 text-center text-xs text-muted">
          <span v-if="defaultModel">当前模型: {{ defaultModel }}</span>
          <span v-else>未选择模型</span>
        </div>
      </div>
    </template>
  </div>
</template>
