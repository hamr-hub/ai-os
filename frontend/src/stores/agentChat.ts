import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  toolCalls?: Array<{ id: string; type: string; function: { name: string; arguments: string } }>
}

export interface Conversation {
  id: string
  title: string
  messages: Message[]
  model: string | null
  systemPrompt: string
  createdAt: Date
  updatedAt: Date
}

const STORAGE_KEY = 'agent-conversations'

export const useAgentChatStore = defineStore('agentChat', () => {
  const conversations = ref<Conversation[]>([])
  const activeConversation = ref<string | null>(null)

  const currentConversation = computed(() => {
    return conversations.value.find((c) => c.id === activeConversation.value)
  })

  const generateId = () => {
    return Date.now().toString(36) + Math.random().toString(36).substr(2)
  }

  const createConversation = (title = '新会话', model: string | null = null) => {
    const conv: Conversation = {
      id: generateId(),
      title,
      messages: [],
      model,
      systemPrompt: '',
      createdAt: new Date(),
      updatedAt: new Date(),
    }
    conversations.value.unshift(conv)
    activeConversation.value = conv.id
    saveToStorage()
    return conv
  }

  const selectConversation = (id: string) => {
    if (conversations.value.find((c) => c.id === id)) {
      activeConversation.value = id
    }
  }

  const deleteConversation = (id: string) => {
    const index = conversations.value.findIndex((c) => c.id === id)
    if (index !== -1) {
      conversations.value.splice(index, 1)
      if (activeConversation.value === id) {
        activeConversation.value = conversations.value[0]?.id || null
      }
      saveToStorage()
    }
  }

  const updateConversationTitle = (id: string, title: string) => {
    const conv = conversations.value.find((c) => c.id === id)
    if (conv) {
      conv.title = title
      conv.updatedAt = new Date()
      saveToStorage()
    }
  }

  const setConversationModel = (id: string, model: string | null) => {
    const conv = conversations.value.find((c) => c.id === id)
    if (conv) {
      conv.model = model
      conv.updatedAt = new Date()
      saveToStorage()
    }
  }

  const setConversationSystemPrompt = (id: string, prompt: string) => {
    const conv = conversations.value.find((c) => c.id === id)
    if (conv) {
      conv.systemPrompt = prompt
      conv.updatedAt = new Date()
      saveToStorage()
    }
  }

  const addMessage = (conversationId: string, role: Message['role'], content: string) => {
    const conv = conversations.value.find((c) => c.id === conversationId)
    if (conv) {
      const message: Message = {
        id: generateId(),
        role,
        content,
        timestamp: new Date(),
      }
      conv.messages.push(message)
      conv.updatedAt = new Date()

      if (conv.title === '新会话' && role === 'user') {
        conv.title = content.slice(0, 20) || '新会话'
      }

      saveToStorage()
      return message
    }
    return null
  }

  const clearMessages = (conversationId: string) => {
    const conv = conversations.value.find((c) => c.id === conversationId)
    if (conv) {
      conv.messages = []
      conv.updatedAt = new Date()
      saveToStorage()
    }
  }

  const saveToStorage = () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations.value))
  }

  const loadFromStorage = () => {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      try {
        const parsed = JSON.parse(saved)
        conversations.value = parsed.map((c: Conversation) => ({
          ...c,
          model: c.model ?? null,
          systemPrompt: c.systemPrompt ?? '',
          createdAt: new Date(c.createdAt),
          updatedAt: new Date(c.updatedAt),
          messages: c.messages.map((m: Message) => ({
            ...m,
            toolCalls: m.toolCalls ?? [],
            timestamp: new Date(m.timestamp),
          })),
        }))
        activeConversation.value = conversations.value[0]?.id || null
      } catch (e) {
        console.error('Failed to load agent conversations:', e)
      }
    }
  }

  loadFromStorage()

  return {
    conversations,
    activeConversation,
    currentConversation,
    createConversation,
    selectConversation,
    deleteConversation,
    updateConversationTitle,
    setConversationModel,
    setConversationSystemPrompt,
    addMessage,
    clearMessages,
  }
})
