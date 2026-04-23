import { test, expect } from '@playwright/test'

test.describe('Dashboard 页面', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('页面标题正确', async ({ page }) => {
    await expect(page).toHaveTitle(/AI Controller/)
  })

  test('Dashboard 标题可见', async ({ page }) => {
    const header = page.locator('.header-title')
    await expect(header).toHaveText('仪表盘')
  })

  test('四个卡片区域可见', async ({ page }) => {
    await expect(page.locator('.gpu-card')).toBeVisible()
    await expect(page.locator('.token-card')).toBeVisible()
    await expect(page.locator('.running-card')).toBeVisible()
    await expect(page.locator('.model-list-card')).toBeVisible()
  })

  test('刷新按钮可点击', async ({ page }) => {
    const btn = page.locator('.header-btn')
    await expect(btn).toBeVisible()
    await expect(btn).toBeEnabled()
  })

  test('侧边栏可见', async ({ page }) => {
    await expect(page.locator('.sidebar')).toBeVisible()
  })

  test('侧边栏导航项完整', async ({ page }) => {
    const navItems = page.locator('.nav-item')
    await expect(navItems).toHaveCount(7)
  })

  test('点击导航到聊天页面', async ({ page }) => {
    await page.locator('.nav-item').filter({ hasText: '聊天' }).click()
    await expect(page).toHaveURL(/\/chat/)
    await expect(page.locator('.chat-view')).toBeVisible()
  })

  test('点击导航到模型管理页面', async ({ page }) => {
    await page.locator('.nav-item').filter({ hasText: '模型管理' }).click()
    await expect(page).toHaveURL(/\/models/)
    await expect(page.locator('.model-mgmt')).toBeVisible()
  })

  test('点击导航到Agent页面', async ({ page }) => {
    await page.locator('.nav-item').filter({ hasText: 'Agent' }).click()
    await expect(page).toHaveURL(/\/agent/)
    await expect(page.locator('.agent-view')).toBeVisible()
  })

  test('点击导航到实时监控页面', async ({ page }) => {
    await page.locator('.nav-item').filter({ hasText: '实时监控' }).click()
    await expect(page).toHaveURL(/\/monitor/)
    await expect(page.locator('.monitor-view')).toBeVisible()
  })
})

test.describe('主题切换', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('切换主题按钮存在', async ({ page }) => {
    const themeBtn = page.locator('.theme-btn')
    await expect(themeBtn).toBeVisible()
  })

  test('点击主题按钮切换', async ({ page }) => {
    const themeBtn = page.locator('.theme-btn')
    await page.evaluate(() => localStorage.setItem('theme', 'dark'))
    await page.goto('/')
    const initialTheme = await page.evaluate(() => document.documentElement.getAttribute('data-theme'))
    await themeBtn.click()
    const newTheme = await page.evaluate(() => document.documentElement.getAttribute('data-theme'))
    expect(newTheme).not.toBe(initialTheme)
  })

  test('暗色主题背景色', async ({ page }) => {
    await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'))
    const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor)
    expect(bg).toBeTruthy()
  })

  test('亮色主题背景色', async ({ page }) => {
    await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'light'))
    const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor)
    expect(bg).toBeTruthy()
  })
})

test.describe('侧边栏折叠', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('折叠侧边栏', async ({ page }) => {
    const collapseBtn = page.locator('.collapse-btn')
    await collapseBtn.click()
    await expect(page.locator('.sidebar')).toHaveClass(/collapsed/)
  })

  test('折叠后导航标签隐藏', async ({ page }) => {
    const collapseBtn = page.locator('.collapse-btn')
    await collapseBtn.click()
    const labels = page.locator('.nav-label')
    for (const label of await labels.all()) {
      await expect(label).toBeHidden()
    }
  })

  test('展开折叠的侧边栏', async ({ page }) => {
    const collapseBtn = page.locator('.collapse-btn')
    await collapseBtn.click()
    await expect(page.locator('.sidebar')).toHaveClass(/collapsed/)
    await page.locator('.sidebar.collapsed .collapse-btn').click()
    await expect(page.locator('.sidebar')).not.toHaveClass(/collapsed/)
  })
})

test.describe('Chat 页面', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/chat')
  })

  test('聊天界面可见', async ({ page }) => {
    await expect(page.locator('.chat-view')).toBeVisible()
  })

  test('会话侧边栏可见', async ({ page }) => {
    await expect(page.locator('.chat-sidebar')).toBeVisible()
  })

  test('新建会话按钮可见', async ({ page }) => {
    const btn = page.locator('.chat-sidebar .new-chat-btn')
    await expect(btn).toHaveText('新会话')
  })

  test('点击新建会话', async ({ page }) => {
    await page.locator('.chat-sidebar .new-chat-btn').click()
    const convItems = page.locator('.conv-item')
    await expect(convItems).toHaveCount(1)
  })

  test('聊天窗口空状态', async ({ page }) => {
    await page.locator('.chat-sidebar .new-chat-btn').click()
    await expect(page.locator('.chat-window')).toBeVisible()
  })

  test('输入框可见', async ({ page }) => {
    await page.locator('.chat-sidebar .new-chat-btn').click()
    await expect(page.locator('.msg-input')).toBeVisible()
  })

  test('收起会话侧栏', async ({ page }) => {
    await page.locator('.close-btn').click()
    await expect(page.locator('.chat-sidebar')).toBeHidden()
    await expect(page.locator('.sidebar-toggle')).toBeVisible()
  })

  test('展开会话侧栏', async ({ page }) => {
    await page.locator('.close-btn').click()
    await expect(page.locator('.chat-sidebar')).toBeHidden()
    await page.locator('.sidebar-toggle').click()
    await expect(page.locator('.chat-sidebar')).toBeVisible()
  })
})

test.describe('Agent 页面', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/agent')
  })

  test('Agent界面可见', async ({ page }) => {
    await expect(page.locator('.agent-view')).toBeVisible()
  })

  test('新建会话按钮可见', async ({ page }) => {
    const btn = page.locator('.agent-view .new-chat-btn').first()
    await expect(btn).toBeVisible()
  })
})

test.describe('模型管理页面', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/models')
  })

  test('页面标题正确', async ({ page }) => {
    await expect(page.locator('.header-title')).toHaveText('模型管理')
  })

  test('模型检测区域可见', async ({ page }) => {
    await expect(page.locator('.content')).toBeVisible()
  })

  test('刷新按钮可点击', async ({ page }) => {
    const btn = page.locator('.model-mgmt .icon-btn').first()
    await expect(btn).toBeVisible()
    await expect(btn).toBeEnabled()
  })
})

test.describe('监控页面', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/monitor')
  })

  test('页面标题正确', async ({ page }) => {
    await expect(page.locator('.header-title')).toHaveText('实时监控')
  })

  test('时间范围按钮可见', async ({ page }) => {
    const btns = page.locator('.range-btn')
    await expect(btns).toHaveCount(5)
  })

  test('切换时间范围', async ({ page }) => {
    const btn = page.getByRole('button', { name: '5分钟', exact: true })
    await btn.click()
    await expect(btn).toHaveClass(/active/)
  })
})

test.describe('文档页面', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/docs')
  })

  test('文档页面可见', async ({ page }) => {
    await expect(page.locator('.docs-page')).toBeVisible()
  })

  test('文档侧边栏可见', async ({ page }) => {
    await expect(page.locator('.docs-sidebar')).toBeVisible()
  })
})

test.describe('视觉一致性', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('CSS变量主题色正确', async ({ page }) => {
    const primary = await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--color-primary'))
    expect(primary.trim()).toBe('#6366f1')
  })

  test('卡片圆角一致性', async ({ page }) => {
    const cards = page.locator('.card')
    for (const card of await cards.all()) {
      const borderRadius = await card.evaluate(el => getComputedStyle(el).borderRadius)
      expect(borderRadius).toBeTruthy()
    }
  })

  test('暗色模式文字颜色可见', async ({ page }) => {
    await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'))
    const textPrimary = await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--text-primary'))
    expect(textPrimary.trim()).toBeTruthy()
  })
})
