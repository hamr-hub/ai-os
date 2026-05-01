import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useServerStore } from '../server'

describe('useServerStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('使用本地代理时生成默认基础路径', () => {
    const store = useServerStore()

    expect(store.manageBase).toBe('/api')
    expect(store.v1Base).toBe('/v1')
    expect(store.manageHealthUrl).toBe('/api/models/summary')
    expect(store.inferenceHealthUrl).toBe('/health')
  })

  it('切换远端地址时会规范化 URL', () => {
    const store = useServerStore()

    store.switchServer('http://demo.local:30000///', 'go')

    expect(store.activeUrl).toBe('http://demo.local:30000')
    expect(store.manageBase).toBe('http://demo.local:30000/manage')
    expect(store.v1Base).toBe('http://demo.local:30000/v1')
  })

  it('管理与推理探针都成功时标记为在线', async () => {
    const store = useServerStore()
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200 })
    vi.stubGlobal('fetch', fetchMock)

    const online = await store.checkConnection(1)

    expect(online).toBe(true)
    expect(store.connectionStatus).toBe('online')
    expect(store.lastErrorMessage).toBeNull()
    expect(store.connectionDetails.manage.ok).toBe(true)
    expect(store.connectionDetails.inference.ok).toBe(true)
  })

  it('仅单侧探针成功时标记为部分可用', async () => {
    const store = useServerStore()
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, status: 200 })
      .mockResolvedValueOnce({ ok: false, status: 503 })
    vi.stubGlobal('fetch', fetchMock)

    const online = await store.checkConnection(1)

    expect(online).toBe(false)
    expect(store.connectionStatus).toBe('degraded')
    expect(store.lastErrorMessage).toContain('推理接口异常')
    expect(store.connectionDetails.manage.ok).toBe(true)
    expect(store.connectionDetails.inference.ok).toBe(false)
  })

  it('双侧探针都失败时标记为离线', async () => {
    const store = useServerStore()
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new Error('manage down'))
      .mockRejectedValueOnce(new Error('inference down'))
    vi.stubGlobal('fetch', fetchMock)

    const online = await store.checkConnection(1)

    expect(online).toBe(false)
    expect(store.connectionStatus).toBe('offline')
    expect(store.lastErrorMessage).toContain('管理接口异常')
    expect(store.lastErrorMessage).toContain('推理接口异常')
  })
})
