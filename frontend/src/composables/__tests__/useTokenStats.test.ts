import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useTokenStats } from '@/composables/useTokenStats'

vi.mock('@/api/client', () => ({
  getTokenStats: vi.fn().mockResolvedValue({
    total_prompt_tokens: 10000,
    total_completion_tokens: 5000,
    total_tokens: 15000,
    models: {
      'model-a': { prompt_tokens: 6000, completion_tokens: 3000, total_tokens: 9000 },
      'model-b': { prompt_tokens: 4000, completion_tokens: 2000, total_tokens: 6000 },
    },
    timestamp: '2026-04-23T00:00:00Z',
  }),
}))

describe('useTokenStats', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('初始状态stats为null', () => {
    const { stats, totalTokens, promptTokens, completionTokens } = useTokenStats()
    expect(stats.value).toBeNull()
    expect(totalTokens.value).toBe(0)
    expect(promptTokens.value).toBe(0)
    expect(completionTokens.value).toBe(0)
  })

  it('fetch后填充数据', async () => {
    const { stats, totalTokens, promptTokens, completionTokens, modelStats, fetch } =
      useTokenStats()
    await fetch()
    expect(stats.value).toBeTruthy()
    expect(totalTokens.value).toBe(15000)
    expect(promptTokens.value).toBe(10000)
    expect(completionTokens.value).toBe(5000)
    expect(Object.keys(modelStats.value)).toHaveLength(2)
  })

  it('formatTokens格式化数字', () => {
    const { formatTokens } = useTokenStats()
    expect(formatTokens(15000)).toBe('15.0K')
    expect(formatTokens(1500000)).toBe('1.50M')
    expect(formatTokens(500)).toBe('500')
  })
})
