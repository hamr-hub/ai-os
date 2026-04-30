import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/client', () => ({
  getSwitchStatus: vi.fn(),
}))

vi.mock('@/stores/server', () => ({
  useServerStore: vi.fn(() => ({ activeUrl: 'http://localhost:3000' })),
}))

vi.mock('@/stores/app', () => ({
  useAppStore: vi.fn(() => ({
    success: vi.fn(),
    error: vi.fn(),
  })),
}))

vi.stubGlobal('WebSocket', class MockWS {
  send = vi.fn()
  close = vi.fn()
  readyState = 1
  onopen: (() => void) | null = null
  onmessage: ((ev: { data: string }) => void) | null = null
  onclose: (() => void) | null = null
  onerror: (() => void) | null = null
  addEventListener = vi.fn()
  removeEventListener = vi.fn()
})

import { useModelSwitch } from '@/composables/useModelSwitch'

describe('useModelSwitch', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('初始状态isSwitching为false', () => {
    const { isSwitching, currentSession, error, overallProgress } = useModelSwitch()
    expect(isSwitching.value).toBe(false)
    expect(currentSession.value).toBeNull()
    expect(error.value).toBeNull()
    expect(overallProgress.value).toBe(0)
  })

  it('triggerSwitch设置isSwitching=true', () => {
    const { triggerSwitch, isSwitching } = useModelSwitch()
    triggerSwitch('llama', false, 'switch')
    expect(isSwitching.value).toBe(true)
  })

  it('computed属性overallProgress/phases/isCompleted/isFailed正确计算', () => {
    const { triggerSwitch, currentSession, overallProgress, overallPhase, phases, isCompleted, isFailed } = useModelSwitch()
    triggerSwitch('llama')

    currentSession.value = {
      session_id: 'sess-1',
      action: 'switch',
      target_model: 'llama',
      previous_model: 'qwen',
      started_at: '2026-01-01',
      finished_at: null,
      overall_phase: 'phase1',
      overall_progress: 30,
      phases: [{
        phase: 1,
        name: 'phase1',
        status: 'running',
        progress: 30,
        started_at: '2026-01-01',
        finished_at: null,
        logs: [],
        error: null,
      }],
      error: null,
      rollback_reason: null,
      completed_successfully: false,
    }

    expect(overallProgress.value).toBe(30)
    expect(overallPhase.value).toBe('phase1')
    expect(phases.value).toEqual([{
      phase: 1,
      name: 'phase1',
      status: 'running',
      progress: 30,
      started_at: '2026-01-01',
      finished_at: null,
      logs: [],
      error: null,
    }])
    expect(isCompleted.value).toBe(false)
    expect(isFailed.value).toBe(false)
  })

  it('isCompleted为true当overallPhase为completed', () => {
    const { currentSession, isCompleted, isFailed } = useModelSwitch()
    currentSession.value = {
      session_id: 'sess-1',
      action: 'switch',
      target_model: 'llama',
      previous_model: 'qwen',
      started_at: '2026-01-01',
      finished_at: '2026-01-01',
      overall_phase: 'completed',
      overall_progress: 100,
      phases: [],
      error: null,
      rollback_reason: null,
      completed_successfully: true,
    }

    expect(isCompleted.value).toBe(true)
    expect(isFailed.value).toBe(false)
  })

  it('isFailed为true当overallPhase为failed', () => {
    const { currentSession, isFailed } = useModelSwitch()
    currentSession.value = {
      session_id: 'sess-1',
      action: 'switch',
      target_model: 'llama',
      previous_model: 'qwen',
      started_at: '2026-01-01',
      finished_at: '2026-01-01',
      overall_phase: 'failed',
      overall_progress: 0,
      phases: [],
      error: '切换失败',
      rollback_reason: null,
      completed_successfully: false,
    }

    expect(isFailed.value).toBe(true)
  })

  it('triggerCancel重置isSwitching并断开WS', () => {
    const { triggerSwitch, triggerCancel, isSwitching } = useModelSwitch()
    triggerSwitch('llama')
    expect(isSwitching.value).toBe(true)

    triggerCancel()
    expect(isSwitching.value).toBe(false)
  })
})
