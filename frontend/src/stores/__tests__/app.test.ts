import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAppStore } from '../app'

describe('useAppStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('初始状态 sidebarCollapsed 为 false', () => {
    const store = useAppStore()
    expect(store.sidebarCollapsed).toBe(false)
  })

  it('toggleSidebar 切换折叠状态', () => {
    const store = useAppStore()
    expect(store.sidebarCollapsed).toBe(false)
    store.toggleSidebar()
    expect(store.sidebarCollapsed).toBe(true)
    store.toggleSidebar()
    expect(store.sidebarCollapsed).toBe(false)
  })

  it('setTheme 设置主题', () => {
    const store = useAppStore()
    store.setTheme('dark')
    expect(store.theme).toBe('dark')
    store.setTheme('light')
    expect(store.theme).toBe('light')
  })

  it('addToast 添加通知', () => {
    const store = useAppStore()
    store.addToast('success', '测试成功')
    expect(store.toasts.length).toBe(1)
    expect(store.toasts[0].type).toBe('success')
    expect(store.toasts[0].message).toBe('测试成功')
  })

  it('removeToast 移除通知', () => {
    const store = useAppStore()
    const id = store.addToast('info', '信息')
    store.removeToast(id)
    expect(store.toasts.length).toBe(0)
  })

  it('success/warning/error/info 快捷方法', () => {
    const store = useAppStore()
    store.success('成功')
    store.warning('警告')
    store.error('错误')
    store.info('信息')
    expect(store.toasts.length).toBe(4)
    expect(store.toasts[0].type).toBe('success')
    expect(store.toasts[1].type).toBe('warning')
    expect(store.toasts[2].type).toBe('error')
    expect(store.toasts[3].type).toBe('info')
  })
})
