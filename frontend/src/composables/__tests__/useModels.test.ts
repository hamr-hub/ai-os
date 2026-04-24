import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useModels } from '@/composables/useModels'
import { startModel, stopModel } from '@/api/client'

const { mockModelStatus } = vi.hoisted(() => ({
  mockModelStatus: {
    'model-a': {
      running: true,
      port: 8000,
      service: 'vllm',
      active_requests: 3,
      preloaded: true,
      last_used: '2026-04-23',
      supports_images: true,
      supports_tool_calling: false,
      supports_image_generation: false,
    },
    'model-b': {
      running: false,
      port: null,
      service: null,
      active_requests: 0,
      preloaded: false,
      last_used: null,
      supports_images: false,
      supports_tool_calling: false,
      supports_image_generation: false,
    },
  },
}))

vi.mock('@/api/client', () => ({
  getModelsStatus: vi.fn().mockResolvedValue(mockModelStatus),
  getDefaultModel: vi.fn().mockResolvedValue({ default_model: 'model-a' }),
  startModel: vi.fn().mockResolvedValue({ status: 'starting', model: 'model-b' }),
  stopModel: vi.fn().mockResolvedValue({ status: 'stopped', model: 'model-a' }),
  switchModel: vi.fn().mockResolvedValue({ status: 'switched', model: 'model-b' }),
  setDefaultModel: vi.fn().mockResolvedValue({ status: 'success', default_model: 'model-b' }),
  clearDefaultModel: vi.fn().mockResolvedValue({ status: 'success' }),
}))

vi.mock('vue', async () => {
  const actual = await vi.importActual('vue')
  return {
    ...actual,
    onMounted: vi.fn((cb) => cb()),
    onUnmounted: vi.fn(),
  }
})

describe('useModels', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('初始状态defaultModel为null', () => {
    const { defaultModel } = useModels()
    expect(defaultModel.value).toBeNull()
  })

  it('fetch后填充数据', async () => {
    const { modelStatus, modelList, defaultModel, fetchModelStatus } = useModels()
    await fetchModelStatus()
    expect(modelStatus.value).toBeTruthy()
    expect(modelList.value.length).toBe(2)
    expect(defaultModel.value).toBe('model-a')
  })

  it('modelList正确展开', async () => {
    const { modelList, fetchModelStatus } = useModels()
    await fetchModelStatus()
    const running = modelList.value.filter((m) => m.running)
    expect(running.length).toBe(1)
    expect(running[0].name).toBe('model-a')
  })

  it('handleStartModel调用startModel API', async () => {
    const { handleStartModel } = useModels()
    await handleStartModel('model-b')
    expect(startModel).toHaveBeenCalledWith('model-b')
  })

  it('handleStopModel调用stopModel API', async () => {
    const { handleStopModel } = useModels()
    await handleStopModel('model-a')
    expect(stopModel).toHaveBeenCalledWith('model-a')
  })

  it('runningModelsCount计算正确', async () => {
    const { runningModelsCount, fetchModelStatus } = useModels()
    await fetchModelStatus()
    expect(runningModelsCount.value).toBe(1)
  })
})
