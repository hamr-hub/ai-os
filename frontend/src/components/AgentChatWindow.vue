<script setup lang="ts">
/* eslint-disable vue/no-v-html */
import { ref, nextTick, computed, watch, onMounted, onUnmounted } from 'vue'
import {
  Send,
  Loader2,
  Bot,
  User,
  Sparkles,
  StopCircle,
  Copy,
  Check,
  ChevronDown,
  Settings,
  Wrench,
} from 'lucide-vue-next'
import {
  chatCompletionStream,
  agentChatStream,
  type ChatMessage,
  type AgentMessage,
} from '@/api/client'
import { useModels } from '@/composables/useModels'
import { useAppStore } from '@/stores/app'
import { useAgentChatStore, type Message, type ToolInvocation } from '@/stores/agentChat'
import { useServerStore } from '@/stores/server'
import { renderMarkdown } from '@/composables/useMarkdown'
import { getConnectionIssueMessage } from '@/utils/connection'

const { modelList, defaultModel } = useModels()
const appStore = useAppStore()
const agentChatStore = useAgentChatStore()
const serverStore = useServerStore()

const inputMessage = ref('')
const isLoading = ref(false)
const chatContainer = ref<HTMLElement | null>(null)
const streamingMessageId = ref<string | null>(null)
const abortController = ref<AbortController | null>(null)
const copiedId = ref<string | null>(null)
const expandedToolIds = ref<string[]>([])
const showModelPicker = ref(false)
const showSystemPrompt = ref(false)
const systemPromptInput = ref('')
const showScrollBottom = ref(false)
const isAutoScrolling = ref(true)
const enableTools = ref(false)

const currentConv = computed(() => agentChatStore.currentConversation)
const messages = computed(() => currentConv.value?.messages || [])
const selectableModelList = computed(() => modelList.value)
const activeModel = computed(
  () =>
    currentConv.value?.model ||
    defaultModel.value ||
    modelList.value.find((m) => m.running)?.name ||
    modelList.value[0]?.name ||
    null
)
const activeModelInfo = computed(() => modelList.value.find((m) => m.name === activeModel.value) || null)
const activeModelIsRunning = computed(() => activeModelInfo.value?.running ?? false)
const streamTarget = computed(() => (enableTools.value ? 'manage' : 'inference'))
const streamConnectionIssue = computed(() =>
  getConnectionIssueMessage(
    streamTarget.value,
    serverStore.connectionStatus,
    serverStore.connectionDetails,
    serverStore.lastErrorMessage
  )
)

watch(
  currentConv,
  (conv) => {
    if (conv) {
      systemPromptInput.value = conv.systemPrompt ?? ''
    }
    nextTick(() => scrollToBottom(true))
  },
  { immediate: true }
)

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})

const handleClickOutside = (e: MouseEvent) => {
  if (showModelPicker.value) {
    const target = e.target as HTMLElement
    if (!target.closest('.model-picker-wrap')) {
      showModelPicker.value = false
    }
  }
}

const handleScroll = () => {
  if (!chatContainer.value) return
  const { scrollTop, scrollHeight, clientHeight } = chatContainer.value
  const distanceToBottom = scrollHeight - scrollTop - clientHeight

  // 向上滚动超过 200px 显示按钮
  showScrollBottom.value = distanceToBottom > 200

  // 如果用户手动向上滚动，停止自动跟随
  if (isLoading.value && distanceToBottom > 20) {
    isAutoScrolling.value = false
  } else if (distanceToBottom < 10) {
    isAutoScrolling.value = true
  }
}

const scrollToBottom = (force = false) => {
  if (chatContainer.value && (isAutoScrolling.value || force)) {
    chatContainer.value.scrollTo({
      top: chatContainer.value.scrollHeight,
      behavior: force ? 'smooth' : 'auto',
    })
  }
}

const addMessage = (role: 'user' | 'assistant' | 'system', content: string) => {
  if (!currentConv.value) return null
  const message = agentChatStore.addMessage(currentConv.value.id, role, content)
  nextTick(() => scrollToBottom(true))
  return message
}

const getToolStatusLabel = (status: ToolInvocation['status']) => {
  switch (status) {
    case 'running':
      return '执行中'
    case 'success':
      return '成功'
    case 'error':
      return '失败'
    case 'cancelled':
      return '已中断'
    default:
      return '等待中'
  }
}

const getToolPhaseLabel = (message: Message) => {
  switch (message.toolPhase) {
    case 'preparing':
      return message.expectedToolCalls ? `准备调用 ${message.expectedToolCalls} 个工具` : '准备调用工具'
    case 'running':
      return '工具执行中'
    case 'cancelled':
      return '工具调用已中断'
    case 'finished':
      return '工具调用完成'
    default:
      return '工具调用'
  }
}

const isToolExpanded = (toolId: string) => expandedToolIds.value.includes(toolId)

const toggleToolExpanded = (toolId: string) => {
  if (isToolExpanded(toolId)) {
    expandedToolIds.value = expandedToolIds.value.filter((id) => id !== toolId)
    return
  }
  expandedToolIds.value = [...expandedToolIds.value, toolId]
}

const updateStreamingMessage = (updater: (message: Message) => void) => {
  if (!streamingMessageId.value || !currentConv.value) return false
  return agentChatStore.updateMessage(currentConv.value.id, streamingMessageId.value, updater)
}

const upsertToolInvocation = (
  toolId: string,
  toolName: string,
  updater: (tool: ToolInvocation) => void
) => {
  updateStreamingMessage((message) => {
    if (!message.toolInvocations) {
      message.toolInvocations = []
    }

    let tool = message.toolInvocations.find((item) => item.id === toolId)
    if (!tool) {
      tool = {
        id: toolId,
        name: toolName,
        status: 'pending',
      }
      message.toolInvocations.push(tool)
    }

    updater(tool)
  })
}

const finalizeToolInvocations = (status: ToolInvocation['status']) => {
  updateStreamingMessage((message) => {
    if (!message.toolInvocations?.length) return
    message.toolInvocations.forEach((tool) => {
      if (tool.status === 'pending' || tool.status === 'running') {
        tool.status = status
        tool.finishedAt = new Date()
      }
    })
    message.toolPhase = status === 'cancelled' ? 'cancelled' : 'finished'
  })
}

const setStreamingError = (message: string) => {
  if (streamingMessageId.value && currentConv.value) {
    updateStreamingMessage((msg) => {
      msg.content = `请求失败：${message}`
      if (msg.toolInvocations?.length) {
        msg.toolPhase = 'finished'
        msg.toolInvocations.forEach((tool) => {
          if (tool.status === 'pending' || tool.status === 'running') {
            tool.status = 'error'
            tool.error = message
            tool.finishedAt = new Date()
          }
        })
      }
    })
    nextTick(() => scrollToBottom(true))
    return
  }
  addMessage('system', `Error: ${message}`)
}

const appendStreamingNote = (note: string) => {
  const updated = updateStreamingMessage((msg) => {
    msg.content = msg.content.trim() ? `${msg.content}\n\n${note}` : note
  })
  if (!updated) return
  nextTick(() => scrollToBottom(true))
}

const handleSend = async () => {
  if (!inputMessage.value.trim() || isLoading.value || !currentConv.value) return

  if (!activeModel.value) {
    appStore.warning('当前没有可用模型，请先启动模型或设置默认模型')
    return
  }

  if (streamTarget.value === 'manage' && !serverStore.connectionDetails.manage.ok) {
    appStore.warning(streamConnectionIssue.value)
    return
  }

  if (streamTarget.value === 'inference' && !serverStore.connectionDetails.inference.ok) {
    appStore.warning(streamConnectionIssue.value)
    return
  }

  const userMessage = inputMessage.value.trim()
  inputMessage.value = ''
  addMessage('user', userMessage)
  isLoading.value = true
  isAutoScrolling.value = true

  try {
    const assistantMessage = addMessage('assistant', '')
    if (!assistantMessage) return

    streamingMessageId.value = assistantMessage.id
    abortController.value = new AbortController()

    const apiMessages: ChatMessage[] = []
    const agentMessages: AgentMessage[] = []

    if (currentConv.value?.systemPrompt) {
      apiMessages.push({ role: 'system', content: currentConv.value.systemPrompt })
      agentMessages.push({ role: 'system', content: currentConv.value.systemPrompt })
    }

    messages.value
      .filter((m) => m.role !== 'system')
      .slice(0, -1)
      .forEach((m) => {
        apiMessages.push({ role: m.role, content: m.content })
        agentMessages.push({ role: m.role, content: m.content })
      })

    if (enableTools.value) {
      // Agent mode with tool calling
      await agentChatStream(
        {
          model: activeModel.value || undefined,
          messages: agentMessages,
          max_iterations: 5,
          auto_confirm: false,
        },
        (data) => {
          // Handle different event types
          const typedData = data as Record<string, unknown>
          const type = typedData.type as string | undefined

          if (type === 'tool_calls_start') {
            updateStreamingMessage((msg) => {
              msg.toolPhase = 'preparing'
              msg.expectedToolCalls = Number(typedData.calls || 0)
              msg.toolInvocations = []
              msg.content = ''
            })
          } else if (type === 'tool_executing') {
            const name = typedData.name as string
            const id = typedData.id as string
            upsertToolInvocation(id, name, (tool) => {
              tool.name = name
              tool.status = 'running'
              tool.startedAt = tool.startedAt || new Date()
            })
            updateStreamingMessage((msg) => {
              msg.toolPhase = 'running'
            })
            nextTick(() => scrollToBottom())
          } else if (type === 'tool_result') {
            const name = typedData.name as string
            const success = typedData.success as boolean
            const id = typedData.id as string
            upsertToolInvocation(id, name, (tool) => {
              tool.name = name
              tool.status = success ? 'success' : 'error'
              tool.error = (typedData.error as string | undefined) || undefined
              tool.resultDetails = success ? JSON.stringify(typedData.result ?? '', null, 2) : undefined
              tool.resultPreview = success ? JSON.stringify(typedData.result ?? '').slice(0, 120) : undefined
              tool.finishedAt = new Date()
            })
            updateStreamingMessage((msg) => {
              if (msg.toolInvocations?.length) {
                const hasPending = msg.toolInvocations.some(
                  (tool) => tool.status === 'pending' || tool.status === 'running'
                )
                msg.toolPhase = hasPending ? 'running' : 'finished'
              }
            })
            nextTick(() => scrollToBottom())
          } else if (type === 'tool_calls_end') {
            updateStreamingMessage((msg) => {
              if (msg.toolInvocations?.length) {
                const hasPending = msg.toolInvocations.some(
                  (tool) => tool.status === 'pending' || tool.status === 'running'
                )
                msg.toolPhase = hasPending ? 'running' : 'finished'
              } else {
                msg.toolPhase = 'finished'
              }
            })
          } else if (typedData.choices && Array.isArray(typedData.choices)) {
            // Regular streaming content
            const delta = typedData.choices[0]?.delta as { content?: string } | undefined
            if (delta?.content) {
              updateStreamingMessage((msg) => {
                msg.content += delta.content
                if (msg.toolInvocations?.length) {
                  msg.toolPhase = 'finished'
                }
              })
              nextTick(() => scrollToBottom())
            }
          }
        },
        (error) => {
          appStore.error(`请求失败: ${error.message}`)
          setStreamingError(error.message)
          streamingMessageId.value = null
        },
        abortController.value.signal
      )
    } else {
      // Normal chat mode
      await chatCompletionStream(
        {
          model: activeModel.value || undefined,
          messages: apiMessages,
          max_tokens: 2048,
          temperature: 0.7,
        },
        (chunk) => {
          updateStreamingMessage((msg) => {
            msg.content += chunk
          })
          nextTick(() => scrollToBottom())
        },
        (error) => {
          appStore.error(`请求失败: ${error.message}`)
          setStreamingError(error.message)
          streamingMessageId.value = null
        },
        abortController.value.signal
      )
    }

    streamingMessageId.value = null
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      finalizeToolInvocations('cancelled')
      appendStreamingNote('已停止生成')
      streamingMessageId.value = null
      return
    }
    const errorMessage = error instanceof Error ? error.message : 'Failed to get response'
    appStore.error(errorMessage)
    setStreamingError(errorMessage)
  } finally {
    isLoading.value = false
    abortController.value = null
  }
}

const handleStop = () => {
  if (abortController.value) {
    abortController.value.abort()
    isLoading.value = false
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
  agentChatStore.createConversation('新会话', activeModel.value || null)
  systemPromptInput.value = ''
}

const selectModel = (name: string) => {
  if (currentConv.value) {
    agentChatStore.setConversationModel(currentConv.value.id, name)
  }
  showModelPicker.value = false
}

const applySystemPrompt = () => {
  if (currentConv.value) {
    agentChatStore.setConversationSystemPrompt(currentConv.value.id, systemPromptInput.value)
  }
}

const copyMessage = async (id: string, content: string) => {
  try {
    await navigator.clipboard.writeText(content)
    copiedId.value = id
    setTimeout(() => {
      copiedId.value = null
    }, 2000)
  } catch (err) {
    console.warn('[AgentChat] Clipboard copy failed:', err)
  }
}

const autoResize = (event: Event) => {
  const el = event.target as HTMLTextAreaElement
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 160) + 'px'
}
</script>

<template>
  <div class="agent-chat">
    <div v-if="!currentConv" class="empty-state">
      <div class="empty-content">
        <div class="empty-icon">
          <Bot class="w-10 h-10 text-white" />
        </div>
        <h2 class="empty-title">Agent</h2>
        <p class="empty-desc">与 AI Agent 对话，连接已部署的模型</p>
        <button class="start-btn" @click="handleNewChat">开始对话</button>
      </div>
    </div>

    <template v-else>
      <div class="chat-topbar">
        <div class="topbar-left model-picker-wrap">
          <div class="model-selector" @click.stop="showModelPicker = !showModelPicker">
            <span class="model-dot" :class="activeModelIsRunning ? 'online' : 'offline'"></span>
            <span class="model-name">{{ activeModel || '选择模型' }}</span>
            <ChevronDown class="w-3.5 h-3.5" />
          </div>
          <div v-if="showModelPicker" class="model-picker">
            <div
              v-for="m in selectableModelList"
              :key="m.name"
              class="picker-item"
              :class="{ active: m.name === activeModel }"
              @click.stop="selectModel(m.name)"
            >
              <span class="picker-dot" :class="m.running ? 'online' : 'offline'"></span>
              {{ m.name }}
              <Check v-if="m.name === activeModel" class="w-3.5 h-3.5" />
            </div>
            <div v-if="!selectableModelList.length" class="picker-empty">暂无可用模型</div>
          </div>
        </div>
        <button
          class="sys-prompt-toggle"
          :class="{ active: showSystemPrompt }"
          title="系统提示词"
          @click="showSystemPrompt = !showSystemPrompt"
        >
          <Settings class="w-4 h-4" />
        </button>
        <button
          class="tool-toggle"
          :class="{ active: enableTools }"
          title="工具调用"
          @click="enableTools = !enableTools"
        >
          <Wrench class="w-4 h-4" />
        </button>
      </div>

      <div v-if="showSystemPrompt" class="sys-prompt-panel">
        <div class="sys-prompt-header">
          <span>系统提示词</span>
          <button class="sys-prompt-apply" @click="applySystemPrompt">应用</button>
        </div>
        <textarea
          v-model="systemPromptInput"
          class="sys-prompt-input"
          placeholder="设定 Agent 的角色和行为..."
          rows="3"
        ></textarea>
        <p class="sys-prompt-hint">设定后将在下次发送消息时生效</p>
      </div>

      <div
        v-if="serverStore.connectionStatus !== 'online' && serverStore.connectionStatus !== 'checking'"
        class="connection-banner"
        :class="serverStore.connectionStatus"
      >
        <span class="banner-label">
          {{ serverStore.connectionStatus === 'degraded' ? '部分可用' : '连接异常' }}
        </span>
        <span class="banner-text">{{ streamConnectionIssue }}</span>
      </div>

      <div ref="chatContainer" class="messages-area scrollbar-thin" @scroll="handleScroll">
        <div v-if="messages.length === 0" class="msg-empty">
          <Bot class="w-8 h-8 opacity-40" />
          <p>发送消息开始对话</p>
          <p class="sub">支持多轮对话，Agent 会记住上下文</p>
        </div>

        <div
          v-for="message in messages"
          :key="message.id"
          class="msg-row"
          :class="{ 'msg-user': message.role === 'user' }"
        >
          <div
            class="msg-avatar"
            :class="{
              'avatar-user': message.role === 'user',
              'avatar-agent': message.role === 'assistant',
              'avatar-sys': message.role === 'system',
            }"
          >
            <User v-if="message.role === 'user'" class="w-4 h-4 text-white" />
            <Bot v-else-if="message.role === 'assistant'" class="w-4 h-4 text-white" />
            <Sparkles v-else class="w-4 h-4 text-white" />
          </div>

          <div class="msg-body">
            <div
              class="msg-bubble"
              :class="{
                'bubble-user': message.role === 'user',
                'bubble-agent': message.role === 'assistant',
                'bubble-sys': message.role === 'system',
              }"
            >
              <div
                v-if="message.role === 'assistant'"
                class="msg-text markdown-body"
                v-html="renderMarkdown(message.content)"
              ></div>
              <p v-else class="msg-text">{{ message.content }}</p>

              <div
                v-if="message.toolInvocations?.length || (message.toolPhase && message.toolPhase !== 'idle')"
                class="tool-calls-block"
              >
                <div class="tool-calls-header">
                  <Wrench class="w-3.5 h-3.5" />
                  <span class="tc-title">{{ getToolPhaseLabel(message) }}</span>
                  <span
                    v-if="message.toolInvocations?.length"
                    class="tc-badge"
                  >
                    {{ message.toolInvocations.length }} 个
                  </span>
                </div>
                <div
                  v-for="tool in message.toolInvocations || []"
                  :key="tool.id"
                  class="tool-call-item"
                >
                  <div class="tool-call-main">
                    <span class="tc-name">{{ tool.name }}</span>
                    <span class="tc-status" :class="`status-${tool.status}`">
                      {{ getToolStatusLabel(tool.status) }}
                    </span>
                  </div>
                  <p v-if="tool.error" class="tc-error">{{ tool.error }}</p>
                  <p
                    v-else-if="tool.resultPreview && tool.status === 'success'"
                    class="tc-result"
                  >
                    {{ tool.resultPreview }}
                  </p>
                  <button
                    v-if="tool.resultDetails || tool.error"
                    class="tc-toggle"
                    @click="toggleToolExpanded(tool.id)"
                  >
                    {{ isToolExpanded(tool.id) ? '收起详情' : '查看详情' }}
                  </button>
                  <pre
                    v-if="isToolExpanded(tool.id) && (tool.resultDetails || tool.error)"
                    class="tc-details"
                  ><code>{{ tool.resultDetails || tool.error }}</code></pre>
                </div>
              </div>

              <span v-if="streamingMessageId === message.id" class="streaming-cursor">
                <span style="animation-delay: 0ms"></span>
                <span style="animation-delay: 150ms"></span>
                <span style="animation-delay: 300ms"></span>
              </span>

              <button
                v-if="
                  message.role === 'assistant' &&
                  message.content &&
                  streamingMessageId !== message.id
                "
                class="copy-btn"
                @click="copyMessage(message.id, message.content)"
              >
                <Check v-if="copiedId === message.id" class="w-3.5 h-3.5 text-green-400" />
                <Copy v-else class="w-3.5 h-3.5" />
              </button>
            </div>
            <p class="msg-time" :class="{ 'text-right': message.role === 'user' }">
              {{ formatTime(message.timestamp) }}
            </p>
          </div>
        </div>

        <div v-if="isLoading && !streamingMessageId" class="thinking-row">
          <Loader2 class="w-4 h-4 animate-spin" />
          <span>正在思考...</span>
        </div>

        <!-- 滚动到底部按钮 -->
        <Transition name="fade">
          <button
            v-if="showScrollBottom"
            class="scroll-bottom-btn"
            title="滚动到底部"
            @click="scrollToBottom(true)"
          >
            <ChevronDown class="w-5 h-5" />
          </button>
        </Transition>
      </div>

      <div class="input-area">
        <div class="input-row">
          <textarea
            v-model="inputMessage"
            placeholder="输入消息... (Enter 发送，Shift+Enter 换行)"
            class="msg-input scrollbar-thin"
            :disabled="isLoading"
            rows="1"
            @keydown="handleKeyPress"
            @input="autoResize"
          ></textarea>
          <button
            v-if="!isLoading"
            :disabled="!inputMessage.trim()"
            class="send-btn"
            title="发送"
            @click="handleSend"
          >
            <Send class="w-4 h-4" />
          </button>
          <button v-else class="stop-btn" title="停止" @click="handleStop">
            <StopCircle class="w-4 h-4" />
          </button>
        </div>
        <div class="input-footer">
          <span v-if="activeModel" class="model-info">
            <span class="model-dot" :class="activeModelIsRunning ? 'online' : 'offline'"></span>
            {{ activeModel }}
            <span v-if="!activeModelIsRunning">未运行</span>
          </span>
          <span v-else class="model-warn">请先选择或启动模型</span>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.agent-chat {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-primary);
  position: relative;
}

.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
.empty-content {
  text-align: center;
  max-width: 360px;
  padding: 24px;
}
.empty-icon {
  width: 72px;
  height: 72px;
  margin: 0 auto 20px;
  border-radius: 20px;
  background: linear-gradient(135deg, #6366f1, #4f46e5);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 24px rgba(99, 102, 241, 0.4);
}
.empty-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 6px;
}
.empty-desc {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 20px;
  line-height: 1.6;
}
.start-btn {
  padding: 10px 24px;
  border-radius: 12px;
  border: none;
  background: linear-gradient(135deg, #6366f1, #4f46e5);
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  box-shadow: 0 4px 16px rgba(99, 102, 241, 0.3);
  transition: all 0.2s;
}
.start-btn:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}

.chat-topbar {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border-primary);
  background: var(--bg-card);
  z-index: 10;
}

.model-selector {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  border-radius: 8px;
  border: 1px solid var(--border-primary);
  background: var(--bg-secondary);
  cursor: pointer;
  font-size: 13px;
  color: var(--text-primary);
  transition: all 0.2s;
}
.model-selector:hover {
  border-color: var(--border-secondary);
}
.model-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}
.model-dot.online {
  background: #22c55e;
  box-shadow: 0 0 6px rgba(34, 197, 94, 0.4);
}
.model-dot.offline {
  background: #6b7280;
}

.model-picker {
  position: absolute;
  top: 100%;
  left: 16px;
  min-width: 240px;
  background: var(--bg-card);
  border: 1px solid var(--border-primary);
  border-radius: 10px;
  box-shadow: var(--shadow-md);
  z-index: 20;
  overflow: hidden;
}
.picker-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 14px;
  font-size: 13px;
  color: var(--text-primary);
  cursor: pointer;
  transition: background 0.2s;
}
.picker-item:hover {
  background: var(--bg-secondary);
}
.picker-item.active {
  color: #6366f1;
}
.picker-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
.picker-dot.online {
  background: #22c55e;
}
.picker-dot.offline {
  background: #6b7280;
}
.picker-empty {
  padding: 14px;
  text-align: center;
  font-size: 12px;
  color: var(--text-muted);
}

.topbar-left {
  position: relative;
}

.sys-prompt-toggle {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid var(--border-primary);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}
.sys-prompt-toggle:hover {
  color: var(--text-primary);
  background: var(--bg-secondary);
}
.sys-prompt-toggle.active {
  color: #6366f1;
  border-color: #6366f1;
  background: rgba(99, 102, 241, 0.1);
}

.tool-toggle {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid var(--border-primary);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  margin-left: 8px;
}
.tool-toggle:hover {
  color: var(--text-primary);
  background: var(--bg-secondary);
}
.tool-toggle.active {
  color: #f59e0b;
  border-color: #f59e0b;
  background: rgba(245, 158, 11, 0.1);
}

.sys-prompt-panel {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-primary);
  background: var(--bg-card);
}
.sys-prompt-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}
.sys-prompt-apply {
  padding: 4px 12px;
  border-radius: 6px;
  border: none;
  background: #6366f1;
  color: #fff;
  font-size: 12px;
  cursor: pointer;
  transition: opacity 0.2s;
}
.sys-prompt-apply:hover {
  opacity: 0.85;
}
.sys-prompt-input {
  width: 100%;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid var(--border-primary);
  background: var(--bg-input);
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
  resize: vertical;
  min-height: 60px;
  transition: border-color 0.2s;
}
.sys-prompt-input:focus {
  border-color: #6366f1;
}
.sys-prompt-input::placeholder {
  color: var(--text-muted);
}
.sys-prompt-hint {
  margin-top: 4px;
  font-size: 11px;
  color: var(--text-muted);
}

.connection-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border-primary);
  font-size: 12px;
}
.connection-banner.degraded {
  background: rgba(249, 115, 22, 0.08);
  color: #f97316;
}
.connection-banner.offline {
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
}
.banner-label {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.12);
}
.banner-text {
  color: var(--text-secondary);
}

.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  position: relative;
}

.msg-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 48px 0;
  color: var(--text-muted);
  font-size: 13px;
}
.msg-empty .sub {
  font-size: 12px;
  opacity: 0.7;
}

.msg-row {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
}
.msg-row.msg-user {
  flex-direction: row-reverse;
}

.msg-avatar {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.avatar-user {
  background: linear-gradient(135deg, #3b82f6, #2563eb);
}
.avatar-agent {
  background: linear-gradient(135deg, #6366f1, #4f46e5);
}
.avatar-sys {
  background: var(--bg-tertiary);
}

.msg-body {
  flex: 1;
  max-width: 72%;
  min-width: 0;
}

.msg-bubble {
  position: relative;
  padding: 12px 16px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.65;
  word-break: break-word;
}
.bubble-user {
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: #fff;
  border-top-right-radius: 4px;
}
.bubble-agent {
  background: var(--bg-card);
  color: var(--text-primary);
  border: 1px solid var(--border-primary);
  border-top-left-radius: 4px;
}
.bubble-sys {
  background: var(--bg-tertiary);
  color: var(--text-muted);
}

.msg-text {
  white-space: pre-wrap;
}

.tool-calls-block {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.tool-calls-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
}
.tc-title {
  font-weight: 600;
  color: var(--text-primary);
}
.tool-call-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(99, 102, 241, 0.06);
  border: 1px solid rgba(99, 102, 241, 0.15);
  font-size: 12px;
  color: var(--text-secondary);
}
.tool-call-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
}
.tc-name {
  font-weight: 500;
  color: var(--text-primary);
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 11px;
}
.tc-badge {
  font-size: 10px;
  color: #6366f1;
  background: rgba(99, 102, 241, 0.1);
  padding: 1px 5px;
  border-radius: 3px;
}
.tc-status {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 999px;
  font-weight: 600;
}
.tc-status.status-pending,
.tc-status.status-running {
  background: rgba(245, 158, 11, 0.12);
  color: #f59e0b;
}
.tc-status.status-success {
  background: rgba(34, 197, 94, 0.12);
  color: #22c55e;
}
.tc-status.status-error,
.tc-status.status-cancelled {
  background: rgba(239, 68, 68, 0.12);
  color: #ef4444;
}
.tc-error,
.tc-result {
  margin: 0;
  font-size: 11px;
  line-height: 1.5;
}
.tc-error {
  color: #ef4444;
}
.tc-result {
  color: var(--text-muted);
  word-break: break-word;
}
.tc-toggle {
  align-self: flex-start;
  padding: 0;
  border: none;
  background: transparent;
  color: #6366f1;
  font-size: 11px;
  cursor: pointer;
}
.tc-details {
  margin: 0;
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid rgba(99, 102, 241, 0.15);
  color: #cbd5e1;
  font-size: 11px;
  line-height: 1.5;
  overflow-x: auto;
  white-space: pre-wrap;
}

.streaming-cursor {
  display: inline-flex;
  gap: 2px;
  margin-left: 4px;
  vertical-align: middle;
}
.streaming-cursor span {
  width: 4px;
  height: 16px;
  border-radius: 2px;
  background: currentColor;
  opacity: 0.6;
  animation: bounce 1s infinite;
}

.copy-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 4px;
  border-radius: 6px;
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  opacity: 0;
  transition: all 0.2s;
}
.msg-row:hover .copy-btn {
  opacity: 1;
}

.msg-time {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 4px;
  padding: 0 4px;
}

.thinking-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  color: var(--text-muted);
  font-size: 13px;
}

.scroll-bottom-btn {
  position: absolute;
  bottom: 20px;
  right: 20px;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--bg-card);
  border: 1px solid var(--border-primary);
  color: var(--text-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: var(--shadow-md);
  z-index: 30;
  transition: all 0.2s;
}
.scroll-bottom-btn:hover {
  background: var(--bg-hover);
  transform: translateY(-2px);
}

.fade-enter-active,
.fade-leave-active {
  transition:
    opacity 0.2s,
    transform 0.2s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(10px);
}

.input-area {
  padding: 12px 16px 16px;
  border-top: 1px solid var(--border-primary);
  background: var(--bg-card);
}
.input-row {
  display: flex;
  gap: 10px;
  align-items: flex-end;
}

.msg-input {
  flex: 1;
  padding: 10px 14px;
  border-radius: 16px;
  border: 1px solid var(--border-primary);
  background: var(--bg-input);
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
  resize: none;
  min-height: 44px;
  max-height: 160px;
  transition: border-color 0.2s;
}
.msg-input:focus {
  border-color: #6366f1;
}
.msg-input:disabled {
  opacity: 0.5;
}
.msg-input::placeholder {
  color: var(--text-muted);
}

.send-btn,
.stop-btn {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
}
.send-btn {
  background: linear-gradient(135deg, #6366f1, #4f46e5);
  color: #fff;
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}
.send-btn:hover:not(:disabled) {
  transform: translateY(-1px);
}
.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.stop-btn {
  background: #ef4444;
  color: #fff;
}

.input-footer {
  display: flex;
  justify-content: center;
  margin-top: 6px;
  font-size: 12px;
}
.model-info {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--text-muted);
}
.model-warn {
  color: #f59e0b;
}

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
:deep(.markdown-body ul),
:deep(.markdown-body ol) {
  margin: 0 0 8px;
  padding-left: 20px;
}
:deep(.markdown-body blockquote) {
  margin: 0 0 8px;
  padding: 8px 12px;
  border-left: 3px solid #6366f1;
  background: rgba(99, 102, 241, 0.06);
  color: var(--text-secondary);
}
:deep(.markdown-body h1),
:deep(.markdown-body h2),
:deep(.markdown-body h3) {
  margin: 12px 0 6px;
  font-weight: 600;
}
:deep(.markdown-body h1) {
  font-size: 18px;
}
:deep(.markdown-body h2) {
  font-size: 16px;
}
:deep(.markdown-body h3) {
  font-size: 14px;
}
:deep(.markdown-body a) {
  color: #6366f1;
  text-decoration: underline;
}
:deep(.markdown-body table) {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
}
:deep(.markdown-body th),
:deep(.markdown-body td) {
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
  position: absolute;
  top: 6px;
  right: 50px;
  font-size: 0.7em;
  color: #565f89;
  text-transform: uppercase;
  z-index: 2;
}
:deep(.code-copy-btn) {
  position: absolute;
  top: 6px;
  right: 10px;
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: #565f89;
  font-size: 11px;
  cursor: pointer;
  z-index: 2;
  transition: all 0.2s;
}
:deep(.code-copy-btn:hover) {
  background: rgba(255, 255, 255, 0.15);
  color: #a9b1d6;
}

@keyframes bounce {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-4px);
  }
}
</style>
