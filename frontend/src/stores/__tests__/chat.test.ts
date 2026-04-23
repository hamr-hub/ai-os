import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useChatStore } from '../chat'

describe('useChatStore', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('createConversation 创建新会话', () => {
    const store = useChatStore()
    store.createConversation('测试会话', 'test-model')
    expect(store.conversations.length).toBe(1)
    expect(store.conversations[0].title).toBe('测试会话')
    expect(store.conversations[0].model).toBe('test-model')
  })

  it('selectConversation 选择会话', () => {
    const store = useChatStore()
    const conv = store.createConversation('会话1', 'model1')
    if (conv) {
      store.selectConversation(conv.id)
      expect(store.activeConversation).toBe(conv.id)
    }
  })

  it('deleteConversation 删除会话', () => {
    const store = useChatStore()
    const conv = store.createConversation('会话1', 'model1')
    if (conv) {
      store.deleteConversation(conv.id)
      expect(store.conversations.length).toBe(0)
    }
  })

  it('addMessage 添加消息', () => {
    const store = useChatStore()
    const conv = store.createConversation('会话1', 'model1')
    if (conv) {
      store.selectConversation(conv.id)
      const msg = store.addMessage(conv.id, 'user', '你好')
      expect(msg).toBeTruthy()
      expect(msg!.role).toBe('user')
      expect(msg!.content).toBe('你好')
      const currentConv = store.currentConversation
      expect(currentConv?.messages.length).toBe(1)
    }
  })
})
