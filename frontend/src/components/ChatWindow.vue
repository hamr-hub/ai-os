<script setup lang="ts">
import { ref, nextTick, computed, watch } from 'vue'
import { Send, Loader2, Bot, User, Sparkles, StopCircle, Copy, Check } from 'lucide-vue-next'
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
const copiedId = ref<string | null>(null)

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

const copyMessage = async (id: string, content: string) => {
  try {
    await navigator.clipboard.writeText(content)
    copiedId.value = id
    setTimeout(() => {
      copiedId.value = null
    }, 2000)
  } catch {
    // fallback
  }
}

/**
 * Simple inline code highlighting: wrap `code` spans
 */
const renderContent = (content: string): string => {
  return content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
      const langLabel = lang ? `<span class="code-lang">${lang}</span>` : ''
      return `<pre class="code-block">${langLabel}<code>${code.trim()}</code></pre>`
    })
    .replace(/`([^`\n]+)`/g, '<code class="inline-code">$1</code>')
}

const autoResize = (event: Event) => {
  const el = event.target as HTMLTextAreaElement
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 160) + 'px'
}
</script>

<template>
  <div class="flex flex-col h-full bg-primary">
    <!-- Empty state -->
    <div v-if="!currentConv" class="flex-1 flex items-center justify-center noise-overlay">
      <div class="text-center scale-in max-w-sm px-6">
        <div class="w-20 h-20 mx-auto mb-5 rounded-2xl gradient-primary flex items-center justify-center shadow-xl animate-float">
          <Sparkles class="w-10 h-10 text-white" />
        </div>
        <h2 class="text-2xl font-bold text-gradient mb-2">欢迎使用 AI 聊天</h2>
        <p class="text-secondary mb-6 text-sm leading-relaxed">选择左侧的会话或创建新会话，开始与 AI 对话</p>
        <button
          @click="handleNewChat"
          class="px-6 py-3 gradient-primary hover:opacity-90 text-white rounded-xl transition-all btn-glow border-glow text-sm font-medium shadow-lg"
        >
          创建新会话
        </button>
      </div>
    </div>

    <template v-else>
      <!-- Messages -->
      <div
        ref="chatContainer"
        class="flex-1 overflow-y-auto p-4 md:p-6 space-y-5 scrollbar-thin"
      >
        <div v-if="messages.length === 0" class="text-center py-16 text-muted">
          <div class="w-16 h-16 mx-auto mb-4 rounded-2xl bg-tertiary flex items-center justify-center">
            <Bot class="w-8 h-8 opacity-50" />
          </div>
          <p class="text-sm">发送消息开始对话</p>
          <p class="text-xs mt-1 opacity-70">支持多轮对话，AI 会记住上下文</p>
        </div>

        <div
          v-for="message in messages"
          :key="message.id"
          class="flex gap-3 fade-in group"
          :class="{ 'flex-row-reverse': message.role === 'user' }"
        >
          <!-- Avatar -->
          <div
            class="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 shadow-lg mt-0.5"
            :class="{
              'gradient-blue': message.role === 'user',
              'gradient-purple': message.role === 'assistant',
              'bg-tertiary': message.role === 'system',
            }"
          >
            <User v-if="message.role === 'user'" class="w-4 h-4 text-white" />
            <Bot v-else-if="message.role === 'assistant'" class="w-4 h-4 text-white" />
            <Sparkles v-else class="w-4 h-4 text-white" />
          </div>

          <!-- Message bubble -->
          <div class="flex-1 max-w-[75%] min-w-0">
            <div
              class="relative px-4 py-3 rounded-2xl shadow-md"
              :class="{
                'gradient-blue text-white rounded-tr-sm': message.role === 'user',
                'bg-card text-primary rounded-tl-sm border border-primary': message.role === 'assistant',
                'bg-tertiary text-secondary rounded-xl': message.role === 'system',
              }"
            >
              <!-- eslint-disable vue/no-v-html -->
              <p
                class="text-sm whitespace-pre-wrap leading-relaxed break-words"
                v-html="renderContent(message.content)"
              ></p>

              <!-- Streaming cursor -->
              <span
                v-if="streamingMessageId === message.id"
                class="inline-flex gap-0.5 ml-1 align-middle"
              >
                <span class="w-1 h-4 bg-current rounded animate-bounce opacity-70" style="animation-delay: 0ms"></span>
                <span class="w-1 h-4 bg-current rounded animate-bounce opacity-70" style="animation-delay: 150ms"></span>
                <span class="w-1 h-4 bg-current rounded animate-bounce opacity-70" style="animation-delay: 300ms"></span>
              </span>

              <!-- Copy button (assistant only) -->
              <button
                v-if="message.role === 'assistant' && message.content && streamingMessageId !== message.id"
                @click="copyMessage(message.id, message.content)"
                class="absolute top-2 right-2 p-1.5 rounded-lg opacity-0 group-hover:opacity-100 transition-all duration-200 hover:bg-secondary/50"
                :title="copiedId === message.id ? '已复制' : '复制'"
              >
                <Check v-if="copiedId === message.id" class="w-3.5 h-3.5 text-green-400" />
                <Copy v-else class="w-3.5 h-3.5 text-muted" />
              </button>
            </div>

            <p
              class="text-xs text-muted mt-1.5 px-1"
              :class="{ 'text-right': message.role === 'user' }"
            >
              {{ formatTime(message.timestamp) }}
            </p>
          </div>
        </div>

        <div v-if="isLoading && !streamingMessageId" class="flex items-center gap-2 text-muted py-2">
          <Loader2 class="w-4 h-4 animate-spin" />
          <span class="text-sm">正在思考...</span>
        </div>
      </div>

      <!-- Input area -->
      <div class="px-4 pb-4 pt-3 border-t border-primary bg-secondary/60 backdrop-blur-sm">
        <div class="flex gap-3 items-end max-w-4xl mx-auto">
          <textarea
            v-model="inputMessage"
            @keydown="handleKeyPress"
            @input="autoResize"
            placeholder="输入消息... (Enter 发送，Shift+Enter 换行)"
            class="flex-1 bg-input text-primary border border-secondary rounded-2xl px-4 py-3 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all placeholder:text-muted resize-none min-h-[48px] max-h-40 scrollbar-thin text-sm"
            :disabled="isLoading"
            rows="1"
          ></textarea>
          <div class="flex flex-col gap-2 flex-shrink-0">
            <button
              v-if="!isLoading"
              @click="handleSend"
              :disabled="!inputMessage.trim()"
              class="w-11 h-11 gradient-primary hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-xl transition-all flex items-center justify-center btn-glow shadow-lg hover:shadow-xl hover:scale-105 active:scale-95"
              title="发送 (Enter)"
            >
              <Send class="w-4 h-4" />
            </button>
            <button
              v-else
              @click="handleStop"
              class="w-11 h-11 bg-red-500 hover:bg-red-600 text-white rounded-xl transition-all flex items-center justify-center shadow-lg hover:shadow-xl hover:scale-105 active:scale-95"
              title="停止生成"
            >
              <StopCircle class="w-4 h-4" />
            </button>
          </div>
        </div>

        <div class="mt-2 text-center text-xs text-muted">
          <span v-if="defaultModel" class="inline-flex items-center gap-1.5">
            <span class="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse"></span>
            当前模型: <span class="font-medium text-secondary">{{ defaultModel }}</span>
          </span>
          <span v-else class="text-yellow-500">未选择模型，请先在模型管理页面选择默认模型</span>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
:deep(.inline-code) {
  background: var(--bg-tertiary);
  color: #f59e0b;
  padding: 0.15em 0.4em;
  border-radius: 4px;
  font-family: 'Fira Code', 'Cascadia Code', 'SF Mono', monospace;
  font-size: 0.85em;
  border: 1px solid var(--border-secondary);
}

:deep(.code-block) {
  background: var(--bg-tertiary);
  border: 1px solid var(--border-primary);
  border-radius: 8px;
  padding: 12px 14px;
  margin: 8px 0;
  overflow-x: auto;
  position: relative;
}

:deep(.code-block code) {
  font-family: 'Fira Code', 'Cascadia Code', 'SF Mono', monospace;
  font-size: 0.82em;
  line-height: 1.6;
  color: var(--text-primary);
  white-space: pre;
}

:deep(.code-lang) {
  position: absolute;
  top: 6px;
  right: 10px;
  font-size: 0.7em;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
</style>
