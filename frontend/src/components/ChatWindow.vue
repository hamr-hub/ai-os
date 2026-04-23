<script setup lang="ts">
import { ref, nextTick, computed, watch } from 'vue'
import { Send, Loader2, Bot, User, Sparkles, StopCircle, Copy, Check, ChevronDown, Settings, Wrench } from 'lucide-vue-next'
import { chatCompletionStream, type ChatMessage } from '@/api/client'
import { useModels } from '@/composables/useModels'
import { useAppStore } from '@/stores/app'
import { useChatStore } from '@/stores/chat'
import { renderMarkdown } from '@/composables/useMarkdown'

const { modelList, defaultModel } = useModels()
const appStore = useAppStore()
const chatStore = useChatStore()

const inputMessage = ref('')
const isLoading = ref(false)
const chatContainer = ref<HTMLElement | null>(null)
const streamingMessageId = ref<string | null>(null)
const abortController = ref<AbortController | null>(null)
const copiedId = ref<string | null>(null)
const showModelPicker = ref(false)
const showSystemPrompt = ref(false)
const systemPromptInput = ref('')

const currentConv = computed(() => chatStore.currentConversation)
const messages = computed(() => currentConv.value?.messages || [])
const runningModelList = computed(() => modelList.value.filter(m => m.running))
const activeModel = computed(() => currentConv.value?.model || defaultModel.value)

watch(currentConv, (conv) => {
  if (conv) {
    systemPromptInput.value = conv.systemPrompt ?? ''
  }
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

    const apiMessages: ChatMessage[] = []

    if (currentConv.value?.systemPrompt) {
      apiMessages.push({ role: 'system', content: currentConv.value.systemPrompt })
    }

    messages.value
      .filter(m => m.role !== 'system')
      .slice(0, -1)
      .forEach(m => apiMessages.push({ role: m.role, content: m.content }))

    await chatCompletionStream(
      {
        model: activeModel.value || undefined,
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
  chatStore.createConversation('新会话', activeModel.value || null)
  systemPromptInput.value = ''
}

const selectModel = (name: string) => {
  if (currentConv.value) {
    chatStore.setConversationModel(currentConv.value.id, name)
  }
  showModelPicker.value = false
}

const applySystemPrompt = () => {
  if (currentConv.value) {
    chatStore.setConversationSystemPrompt(currentConv.value.id, systemPromptInput.value)
  }
}

const copyMessage = async (id: string, content: string) => {
  try {
    await navigator.clipboard.writeText(content)
    copiedId.value = id
    setTimeout(() => { copiedId.value = null }, 2000)
  } catch {}
}

const renderContent = (content: string): string => {
  return renderMarkdown(content)
}

const autoResize = (event: Event) => {
  const el = event.target as HTMLTextAreaElement
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 160) + 'px'
}
</script>

<template>
  <div class="chat-window">
    <div v-if="!currentConv" class="empty-state">
      <div class="empty-content">
        <div class="empty-icon">
          <Sparkles class="w-10 h-10 text-white" />
        </div>
        <h2 class="empty-title">AI Chat</h2>
        <p class="empty-desc">选择模型，开始与 AI 对话</p>
        <button @click="handleNewChat" class="new-chat-btn">创建新会话</button>
      </div>
    </div>

    <template v-else>
      <div class="chat-topbar">
        <div class="topbar-left">
          <div class="model-selector" @click="showModelPicker = !showModelPicker">
            <span class="model-dot" :class="activeModel ? 'online' : 'offline'"></span>
            <span class="model-name">{{ activeModel || '选择模型' }}</span>
            <ChevronDown class="w-3.5 h-3.5" />
          </div>
          <div v-if="showModelPicker" class="model-picker">
            <div v-for="m in runningModelList" :key="m.name" class="picker-item" :class="{ active: m.name === activeModel }" @click.stop="selectModel(m.name)">
              {{ m.name }}
              <Check v-if="m.name === activeModel" class="w-3.5 h-3.5" />
            </div>
            <div v-if="!runningModelList.length" class="picker-empty">暂无运行中模型</div>
          </div>
        </div>
        <button class="sys-prompt-toggle" :class="{ active: showSystemPrompt }" @click="showSystemPrompt = !showSystemPrompt" title="系统提示词">
          <Settings class="w-4 h-4" />
        </button>
      </div>

      <div v-if="showSystemPrompt" class="sys-prompt-panel">
        <div class="sys-prompt-header">
          <span>系统提示词</span>
          <button class="sys-prompt-apply" @click="applySystemPrompt">应用</button>
        </div>
        <textarea v-model="systemPromptInput" class="sys-prompt-input" placeholder="输入系统提示词，设定 AI 的角色和行为..." rows="3"></textarea>
        <p class="sys-prompt-hint">设定后将在下次发送消息时生效</p>
      </div>

      <div ref="chatContainer" class="messages-area scrollbar-thin">
        <div v-if="messages.length === 0" class="msg-empty">
          <Bot class="w-8 h-8 opacity-40" />
          <p>发送消息开始对话</p>
          <p class="sub">支持多轮对话，AI 会记住上下文</p>
        </div>

        <div v-for="message in messages" :key="message.id" class="msg-row" :class="{ 'msg-user': message.role === 'user' }">
          <div class="msg-avatar" :class="{
            'avatar-user': message.role === 'user',
            'avatar-bot': message.role === 'assistant',
            'avatar-sys': message.role === 'system',
          }">
            <User v-if="message.role === 'user'" class="w-4 h-4 text-white" />
            <Bot v-else-if="message.role === 'assistant'" class="w-4 h-4 text-white" />
            <Sparkles v-else class="w-4 h-4 text-white" />
          </div>

          <div class="msg-body">
            <div class="msg-bubble" :class="{
              'bubble-user': message.role === 'user',
              'bubble-bot': message.role === 'assistant',
              'bubble-sys': message.role === 'system',
            }">
              <div v-if="message.role === 'assistant'" class="msg-text markdown-body" v-html="renderContent(message.content)"></div>
              <p v-else class="msg-text">{{ message.content }}</p>

              <div v-if="message.toolCalls?.length" class="tool-calls-block">
                <div v-for="tc in message.toolCalls" :key="tc.id" class="tool-call-item">
                  <Wrench class="w-3.5 h-3.5" />
                  <span class="tc-name">{{ tc.function.name }}</span>
                  <span class="tc-badge">工具调用</span>
                </div>
              </div>

              <span v-if="streamingMessageId === message.id" class="streaming-cursor">
                <span style="animation-delay:0ms"></span>
                <span style="animation-delay:150ms"></span>
                <span style="animation-delay:300ms"></span>
              </span>

              <button v-if="message.role === 'assistant' && message.content && streamingMessageId !== message.id" @click="copyMessage(message.id, message.content)" class="copy-btn">
                <Check v-if="copiedId === message.id" class="w-3.5 h-3.5 text-green-400" />
                <Copy v-else class="w-3.5 h-3.5" />
              </button>
            </div>
            <p class="msg-time" :class="{ 'text-right': message.role === 'user' }">{{ formatTime(message.timestamp) }}</p>
          </div>
        </div>

        <div v-if="isLoading && !streamingMessageId" class="thinking-row">
          <Loader2 class="w-4 h-4 animate-spin" />
          <span>正在思考...</span>
        </div>
      </div>

      <div class="input-area">
        <div class="input-row">
          <textarea v-model="inputMessage" @keydown="handleKeyPress" @input="autoResize" placeholder="输入消息... (Enter 发送，Shift+Enter 换行)" class="msg-input scrollbar-thin" :disabled="isLoading" rows="1"></textarea>
          <button v-if="!isLoading" @click="handleSend" :disabled="!inputMessage.trim()" class="send-btn" title="发送">
            <Send class="w-4 h-4" />
          </button>
          <button v-else @click="handleStop" class="stop-btn" title="停止">
            <StopCircle class="w-4 h-4" />
          </button>
        </div>
        <div class="input-footer">
          <span v-if="activeModel" class="model-info">
            <span class="model-dot online"></span>
            {{ activeModel }}
          </span>
          <span v-else class="model-warn">请先选择或启动模型</span>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.chat-window {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-primary);
}

.empty-state { flex: 1; display: flex; align-items: center; justify-content: center; }
.empty-content { text-align: center; max-width: 360px; padding: 24px; }
.empty-icon {
  width: 72px; height: 72px; margin: 0 auto 20px;
  border-radius: 20px; background: linear-gradient(135deg, #6366f1, #4f46e5);
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 8px 24px rgba(99,102,241,0.4);
  animation: pulse-glow 3s ease-in-out infinite;
}
.empty-title { font-size: 22px; font-weight: 700; color: var(--text-primary); margin-bottom: 6px; }
.empty-desc { font-size: 13px; color: var(--text-muted); margin-bottom: 20px; line-height: 1.6; }
.new-chat-btn {
  padding: 10px 24px; border-radius: 12px; border: none;
  background: linear-gradient(135deg, #6366f1, #4f46e5);
  color: #fff; font-size: 14px; font-weight: 500; cursor: pointer;
  box-shadow: 0 4px 16px rgba(99,102,241,0.3); transition: all 0.2s;
}
.new-chat-btn:hover { opacity: 0.9; transform: translateY(-1px); }

.chat-topbar {
  position: relative; display: flex; align-items: center; justify-content: space-between;
  padding: 10px 16px; border-bottom: 1px solid var(--border-primary); background: var(--bg-card); z-index: 10;
}

.model-selector {
  display: flex; align-items: center; gap: 8px; padding: 6px 14px; border-radius: 8px;
  border: 1px solid var(--border-primary); background: var(--bg-secondary); cursor: pointer;
  font-size: 13px; color: var(--text-primary); transition: all 0.2s;
}
.model-selector:hover { border-color: var(--color-primary); background: rgba(99, 102, 241, 0.06); }
.model-dot { width: 7px; height: 7px; border-radius: 50%; }
.model-dot.online { background: #22c55e; box-shadow: 0 0 6px rgba(34,197,94,0.4); }
.model-dot.offline { background: #6b7280; }

.model-picker {
  position: absolute; top: 100%; left: 16px; min-width: 240px;
  background: var(--bg-card); border: 1px solid var(--border-primary); border-radius: 10px;
  box-shadow: var(--shadow-md); z-index: 20; overflow: hidden;
}
.picker-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 14px; font-size: 13px; color: var(--text-primary); cursor: pointer; transition: background 0.2s;
}
.picker-item:hover { background: var(--bg-secondary); }
.picker-item.active { color: #6366f1; }
.picker-empty { padding: 14px; text-align: center; font-size: 12px; color: var(--text-muted); }

.topbar-left { position: relative; }

.sys-prompt-toggle {
  width: 32px; height: 32px; border-radius: 8px; border: 1px solid var(--border-primary);
  background: transparent; color: var(--text-muted); cursor: pointer;
  display: flex; align-items: center; justify-content: center; transition: all 0.2s;
}
.sys-prompt-toggle:hover { color: var(--text-primary); background: var(--bg-secondary); }
.sys-prompt-toggle.active { color: #6366f1; border-color: #6366f1; background: rgba(99,102,241,0.1); }

.sys-prompt-panel {
  padding: 12px 16px; border-bottom: 1px solid var(--border-primary); background: var(--bg-card);
}
.sys-prompt-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 8px; font-size: 13px; font-weight: 500; color: var(--text-primary);
}
.sys-prompt-apply {
  padding: 4px 12px; border-radius: 6px; border: none;
  background: #6366f1; color: #fff; font-size: 12px; cursor: pointer; transition: opacity 0.2s;
}
.sys-prompt-apply:hover { opacity: 0.85; }
.sys-prompt-input {
  width: 100%; padding: 8px 12px; border-radius: 8px;
  border: 1px solid var(--border-primary); background: var(--bg-input);
  color: var(--text-primary); font-size: 13px; outline: none; resize: vertical;
  min-height: 60px; transition: border-color 0.2s;
}
.sys-prompt-input:focus { border-color: #6366f1; }
.sys-prompt-input::placeholder { color: var(--text-muted); }
.sys-prompt-hint { margin-top: 4px; font-size: 11px; color: var(--text-muted); }

.messages-area { flex: 1; overflow-y: auto; padding: 16px; }

.msg-empty {
  display: flex; flex-direction: column; align-items: center;
  gap: 6px; padding: 48px 0; color: var(--text-muted); font-size: 13px;
}
.msg-empty .sub { font-size: 12px; opacity: 0.7; }

.msg-row { display: flex; gap: 10px; margin-bottom: 16px; }
.msg-row.msg-user { flex-direction: row-reverse; }

.msg-avatar {
  width: 36px; height: 36px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  transition: transform 0.2s;
}
.msg-row:hover .msg-avatar { transform: scale(1.05); }
.avatar-user { background: linear-gradient(135deg, #3b82f6, #2563eb); box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3); }
.avatar-bot { background: linear-gradient(135deg, #8b5cf6, #7c3aed); box-shadow: 0 2px 8px rgba(139, 92, 246, 0.3); }
.avatar-sys { background: var(--bg-tertiary); box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2); }

.msg-body { flex: 1; max-width: 72%; min-width: 0; }

.msg-bubble {
  position: relative; padding: 12px 16px; border-radius: 16px;
  font-size: 14px; line-height: 1.65; word-break: break-word;
  transition: transform 0.15s;
}
.msg-row:hover .msg-bubble { transform: translateY(-1px); }
.bubble-user { background: linear-gradient(135deg, #3b82f6, #2563eb); color: #fff; border-top-right-radius: 4px; box-shadow: 0 2px 10px rgba(59, 130, 246, 0.25); }
.bubble-bot { background: var(--bg-card); color: var(--text-primary); border: 1px solid var(--border-primary); border-top-left-radius: 4px; box-shadow: var(--shadow-sm); }
.bubble-sys { background: var(--bg-tertiary); color: var(--text-muted); }

.msg-text { white-space: pre-wrap; }

.tool-calls-block { margin-top: 8px; display: flex; flex-direction: column; gap: 4px; }
.tool-call-item {
  display: flex; align-items: center; gap: 6px;
  padding: 5px 8px; border-radius: 6px;
  background: rgba(99, 102, 241, 0.06); border: 1px solid rgba(99, 102, 241, 0.15);
  font-size: 12px; color: var(--text-secondary);
}
.tc-name { font-weight: 500; color: var(--text-primary); font-family: 'SF Mono', 'Fira Code', monospace; font-size: 11px; }
.tc-badge { font-size: 10px; color: #6366f1; background: rgba(99, 102, 241, 0.1); padding: 1px 5px; border-radius: 3px; }

.streaming-cursor { display: inline-flex; gap: 2px; margin-left: 4px; vertical-align: middle; }
.streaming-cursor span {
  width: 4px; height: 16px; border-radius: 2px;
  background: currentColor; opacity: 0.6; animation: bounce 1s infinite;
}

.copy-btn {
  position: absolute; top: 8px; right: 8px; padding: 4px; border-radius: 6px;
  background: transparent; border: none; color: var(--text-muted); cursor: pointer;
  opacity: 0; transition: all 0.2s;
}
.msg-row:hover .copy-btn { opacity: 1; }

.msg-time { font-size: 11px; color: var(--text-muted); margin-top: 4px; padding: 0 4px; }

.thinking-row {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 0; color: var(--text-muted); font-size: 13px;
}

.input-area { padding: 12px 16px 16px; border-top: 1px solid var(--border-primary); background: var(--bg-card); }
.input-row { display: flex; gap: 10px; align-items: flex-end; }

.msg-input {
  flex: 1; padding: 10px 14px; border-radius: 14px;
  border: 1px solid var(--border-primary); background: var(--bg-input);
  color: var(--text-primary); font-size: 14px; outline: none; resize: none;
  min-height: 44px; max-height: 160px; transition: border-color 0.2s;
}
.msg-input:focus { border-color: #6366f1; }
.msg-input:disabled { opacity: 0.5; }
.msg-input::placeholder { color: var(--text-muted); }

.send-btn, .stop-btn {
  width: 44px; height: 44px; border-radius: 12px; border: none;
  display: flex; align-items: center; justify-content: center; cursor: pointer;
  transition: all 0.2s; flex-shrink: 0;
}
.send-btn {
  background: linear-gradient(135deg, #6366f1, #4f46e5); color: #fff;
  box-shadow: 0 4px 12px rgba(99,102,241,0.3);
}
.send-btn:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 6px 18px rgba(99,102,241,0.4); }
.send-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.stop-btn { background: #ef4444; color: #fff; box-shadow: 0 4px 12px rgba(239,68,68,0.3); }

.input-footer { display: flex; justify-content: center; margin-top: 6px; font-size: 12px; }
.model-info { display: inline-flex; align-items: center; gap: 6px; color: var(--text-muted); }
.model-warn { color: #f59e0b; }

:deep(.markdown-body) {
  white-space: normal;
  word-break: break-word;
}
:deep(.markdown-body p) {
  margin: 0 0 8px;
}
:deep(.markdown-body p:last-child) {
  margin-bottom: 0;
}
:deep(.markdown-body ul), :deep(.markdown-body ol) {
  margin: 0 0 8px;
  padding-left: 20px;
}
:deep(.markdown-body blockquote) {
  margin: 0 0 8px;
  padding: 8px 12px;
  border-left: 3px solid #6366f1;
  background: rgba(99,102,241,0.06);
  color: var(--text-secondary);
}
:deep(.markdown-body h1), :deep(.markdown-body h2), :deep(.markdown-body h3) {
  margin: 12px 0 6px;
  font-weight: 600;
}
:deep(.markdown-body h1) { font-size: 18px; }
:deep(.markdown-body h2) { font-size: 16px; }
:deep(.markdown-body h3) { font-size: 14px; }
:deep(.markdown-body a) {
  color: #6366f1;
  text-decoration: underline;
}
:deep(.markdown-body table) {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
}
:deep(.markdown-body th), :deep(.markdown-body td) {
  border: 1px solid var(--border-primary);
  padding: 6px 10px;
  font-size: 13px;
}
:deep(.markdown-body th) {
  background: var(--bg-secondary);
  font-weight: 600;
}
:deep(.markdown-body img) {
  max-width: 100%;
  border-radius: 8px;
}
:deep(.markdown-body code) {
  background: var(--bg-tertiary);
  color: #f59e0b;
  padding: 0.15em 0.4em;
  border-radius: 4px;
  font-family: 'Fira Code', 'SF Mono', monospace;
  font-size: 0.85em;
}
:deep(.markdown-body pre) {
  background: #1a1b26;
  border: 1px solid var(--border-primary);
  border-radius: 8px;
  padding: 0;
  margin: 8px 0;
  overflow-x: auto;
  position: relative;
}
:deep(.markdown-body pre code) {
  display: block;
  padding: 12px 14px;
  background: transparent;
  color: #a9b1d6;
  font-family: 'Fira Code', 'SF Mono', monospace;
  font-size: 0.82em;
  line-height: 1.6;
  white-space: pre;
  border-radius: 0;
}
:deep(.code-lang) {
  position: absolute; top: 6px; right: 50px;
  font-size: 0.7em; color: #565f89; text-transform: uppercase;
  z-index: 2;
}
:deep(.code-copy-btn) {
  position: absolute; top: 6px; right: 10px;
  padding: 2px 8px; border-radius: 4px;
  background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.12);
  color: #565f89; font-size: 11px; cursor: pointer; z-index: 2;
  transition: all 0.2s;
}
:deep(.code-copy-btn:hover) {
  background: rgba(255,255,255,0.15);
  color: #a9b1d6;
}

@keyframes bounce {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-4px); }
}
</style>
