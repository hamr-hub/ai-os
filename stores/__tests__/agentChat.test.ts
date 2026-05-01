import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAgentChatStore } from '../agentChat'

describe('useAgentChatStore', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('支持更新消息内容与工具调用状态', () => {
    const store = useAgentChatStore()
    const conversation = store.createConversation('测试会话', 'demo-model')
    const message = store.addMessage(conversation.id, 'assistant', '')

    expect(message).not.toBeNull()

    store.updateMessage(conversation.id, message!.id, (msg) => {
      msg.content = '处理中'
      msg.toolPhase = 'running'
      msg.expectedToolCalls = 1
      msg.toolInvocations = [
        {
          id: 'tool-1',
          name: 'search',
          status: 'running',
          startedAt: new Date('2026-01-01T00:00:00.000Z'),
        },
      ]
    })

    const current = store.currentConversation?.messages[0]
    expect(current?.content).toBe('处理中')
    expect(current?.toolPhase).toBe('running')
    expect(current?.toolInvocations?.[0].name).toBe('search')
  })

  it('支持保存工具详情内容', () => {
    const store = useAgentChatStore()
    const conversation = store.createConversation('测试详情', 'demo-model')
    const message = store.addMessage(conversation.id, 'assistant', '')

    store.updateMessage(conversation.id, message!.id, (msg) => {
      msg.toolInvocations = [
        {
          id: 'tool-1',
          name: 'search',
          status: 'success',
          resultPreview: '{"ok":true}',
          resultDetails: '{\n  "ok": true,\n  "items": [1, 2, 3]\n}',
        },
      ]
      msg.toolPhase = 'finished'
    })

    const current = store.currentConversation?.messages[0]
    expect(current?.toolInvocations?.[0].resultDetails).toContain('"items"')
  })

  it('从本地存储恢复工具调用时间字段', () => {
    localStorage.setItem(
      'agent-conversations',
      JSON.stringify([
        {
          id: 'conv-1',
          title: '已保存会话',
          messages: [
            {
              id: 'msg-1',
              role: 'assistant',
              content: 'ok',
              timestamp: '2026-01-01T00:00:00.000Z',
              toolInvocations: [
                {
                  id: 'tool-1',
                  name: 'search',
                  status: 'success',
                  startedAt: '2026-01-01T00:00:01.000Z',
                  finishedAt: '2026-01-01T00:00:02.000Z',
                },
              ],
              toolPhase: 'finished',
              expectedToolCalls: 1,
            },
          ],
          model: 'demo-model',
          systemPrompt: '',
          createdAt: '2026-01-01T00:00:00.000Z',
          updatedAt: '2026-01-01T00:00:00.000Z',
        },
      ])
    )

    const store = useAgentChatStore()
    const restored = store.currentConversation?.messages[0]

    expect(restored?.toolInvocations?.[0].startedAt).toBeInstanceOf(Date)
    expect(restored?.toolInvocations?.[0].finishedAt).toBeInstanceOf(Date)
    expect(restored?.toolPhase).toBe('finished')
  })
})
