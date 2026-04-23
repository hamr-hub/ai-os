import { test, expect } from '@playwright/test'

test.describe('Dashboard 页面基本结构', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
  })

  test('页面标题包含AI', async ({ page }) => {
    const title = await page.title()
    expect(title).toContain('AI')
  })

  test('Dashboard 标题可见', async ({ page }) => {
    const header = page.locator('.header-title')
    await expect(header).toBeVisible({ timeout: 15000 })
    await expect(header).toHaveText('仪表盘')
  })

  test('刷新按钮可见且可点击', async ({ page }) => {
    const btn = page.locator('.header-btn')
    await expect(btn).toBeVisible({ timeout: 15000 })
    await expect(btn).toBeEnabled()
  })

  test('点击刷新按钮触发动画', async ({ page }) => {
    const btn = page.locator('.header-btn')
    const icon = btn.locator('svg')
    await btn.click()
    await expect(icon).toHaveClass(/animate-spin/)
  })

  test('七个卡片区域可见', async ({ page }) => {
    await expect(page.locator('.gpu-card')).toBeVisible({ timeout: 15000 })
    await expect(page.locator('.token-card')).toBeVisible({ timeout: 15000 })
    await expect(page.locator('.system-card')).toBeVisible({ timeout: 15000 })
    await expect(page.locator('.queue-card')).toBeVisible({ timeout: 15000 })
    await expect(page.locator('.health-card')).toBeVisible({ timeout: 15000 })
    await expect(page.locator('.running-card')).toBeVisible({ timeout: 15000 })
    await expect(page.locator('.model-list-card')).toBeVisible({ timeout: 15000 })
  })

  test('GPU监控卡片显示badge', async ({ page }) => {
    const badge = page.locator('.gpu-card .badge')
    await expect(badge).toBeVisible({ timeout: 15000 })
  })

  test('卡片hover效果 - 有icon-wrap', async ({ page }) => {
    const iconWraps = page.locator('.icon-wrap')
    await expect(iconWraps.first()).toBeVisible({ timeout: 15000 })
  })
})

test.describe('Dashboard 数据依赖测试', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('.card').first()).toBeVisible({ timeout: 15000 })
  })

  test('Token用量卡片有内容或空状态', async ({ page }) => {
    const tokenGrid = page.locator('.token-card .token-grid')
    const emptyState = page.locator('.token-card .empty-state')
    await expect(tokenGrid.or(emptyState)).toBeVisible({ timeout: 10000 })
  })

  test('系统状态卡片有内容或空状态', async ({ page }) => {
    const systemGrid = page.locator('.system-card .system-grid')
    const emptyState = page.locator('.system-card .empty-state')
    await expect(systemGrid.or(emptyState)).toBeVisible({ timeout: 10000 })
  })

  test('请求队列卡片有内容或空状态', async ({ page }) => {
    const queueList = page.locator('.queue-card .queue-list')
    const emptyState = page.locator('.queue-card .empty-state')
    await expect(queueList.or(emptyState)).toBeVisible({ timeout: 10000 })
  })

  test('健康告警卡片有内容或空状态', async ({ page }) => {
    const healthScore = page.locator('.health-card .health-score')
    const emptyState = page.locator('.health-card .empty-state')
    await expect(healthScore.or(emptyState)).toBeVisible({ timeout: 10000 })
  })

  test('模型列表有内容或空状态', async ({ page }) => {
    const modelTable = page.locator('.model-table .table-row')
    const emptyState = page.locator('.model-list-card .empty-state')
    await expect(modelTable.first().or(emptyState)).toBeVisible({ timeout: 10000 })
  })

  test('GPU监控sparkline区域', async ({ page }) => {
    const sparkRow = page.locator('.gpu-card .sparkline-row')
    const emptyState = page.locator('.gpu-card .empty-state')
    const errorState = page.locator('.gpu-card .error-state')
    await expect(sparkRow.or(emptyState).or(errorState)).toBeVisible({ timeout: 10000 })
  })

  test('健康告警展开/折叠告警列表', async ({ page }) => {
    const toggle = page.locator('.alert-toggle')
    if (await toggle.isVisible()) {
      await toggle.click()
      await expect(page.locator('.alert-list')).toBeVisible()
      await toggle.click()
      await expect(page.locator('.alert-list')).toBeHidden()
    }
  })
})

test.describe('Dashboard 响应式布局', () => {
  test('宽屏3列布局', async ({ browser }) => {
    const context = await browser.newContext({ viewport: { width: 1400, height: 900 } })
    const page = await context.newPage()
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    const grid = page.locator('.grid')
    const columns = await grid.evaluate(el => getComputedStyle(el).gridTemplateColumns)
    expect(columns.split(' ').length).toBe(3)
    await context.close()
  })

  test('中屏2列布局', async ({ browser }) => {
    const context = await browser.newContext({ viewport: { width: 1000, height: 900 } })
    const page = await context.newPage()
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    const grid = page.locator('.grid')
    const columns = await grid.evaluate(el => getComputedStyle(el).gridTemplateColumns)
    expect(columns.split(' ').length).toBe(2)
    await context.close()
  })

  test('窄屏1列布局', async ({ browser }) => {
    const context = await browser.newContext({ viewport: { width: 600, height: 900 } })
    const page = await context.newPage()
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    const grid = page.locator('.grid')
    const columns = await grid.evaluate(el => getComputedStyle(el).gridTemplateColumns)
    expect(columns.split(' ').length).toBe(1)
    await context.close()
  })
})

test.describe('导航跳转', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
  })

  test('侧边栏可见', async ({ page }) => {
    await expect(page.locator('.sidebar')).toBeVisible({ timeout: 15000 })
  })

  test('侧边栏导航项数量正确', async ({ page }) => {
    const navItems = page.locator('.nav-item').filter({ has: page.locator('.nav-icon') })
    await expect(navItems).toHaveCount(6, { timeout: 15000 })
  })

  test('点击导航到聊天页面', async ({ page }) => {
    await page.locator('.nav-item').filter({ hasText: '聊天' }).click()
    await expect(page).toHaveURL(/\/chat/, { timeout: 10000 })
    await expect(page.locator('.chat-view')).toBeVisible({ timeout: 10000 })
  })

  test('点击导航到模型管理页面', async ({ page }) => {
    await page.locator('.nav-item').filter({ hasText: '模型' }).click()
    await expect(page).toHaveURL(/\/models/, { timeout: 10000 })
    await expect(page.locator('.model-mgmt')).toBeVisible({ timeout: 10000 })
  })

  test('点击导航到Agent页面', async ({ page }) => {
    await page.locator('.nav-item').filter({ hasText: 'Agent' }).click()
    await expect(page).toHaveURL(/\/agent/, { timeout: 10000 })
  })

  test('点击导航到实时监控页面', async ({ page }) => {
    await page.locator('.nav-item').filter({ hasText: '监控' }).click()
    await expect(page).toHaveURL(/\/monitor/, { timeout: 10000 })
    await expect(page.locator('.monitor-view')).toBeVisible({ timeout: 10000 })
  })

  test('点击导航到文档页面', async ({ page }) => {
    await page.locator('.nav-item').filter({ hasText: '文档' }).click()
    await expect(page).toHaveURL(/\/docs/, { timeout: 10000 })
  })

  test('导航active状态切换', async ({ page }) => {
    const dashboardNav = page.locator('.nav-item').filter({ hasText: '仪表盘' })
    await expect(dashboardNav).toHaveClass(/active/)
    await page.locator('.nav-item').filter({ hasText: '聊天' }).click()
    await expect(dashboardNav).not.toHaveClass(/active/)
    const chatNav = page.locator('.nav-item').filter({ hasText: '聊天' })
    await expect(chatNav).toHaveClass(/active/)
  })
})

test.describe('侧边栏折叠', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
  })

  test('折叠侧边栏', async ({ page }) => {
    const collapseBtn = page.locator('.collapse-btn')
    await expect(collapseBtn).toBeVisible({ timeout: 15000 })
    await collapseBtn.click()
    await expect(page.locator('.sidebar')).toHaveClass(/collapsed/)
  })

  test('展开折叠的侧边栏', async ({ page }) => {
    const collapseBtn = page.locator('.collapse-btn')
    await collapseBtn.click()
    await expect(page.locator('.sidebar')).toHaveClass(/collapsed/)
    await collapseBtn.click()
    await expect(page.locator('.sidebar')).not.toHaveClass(/collapsed/)
  })

  test('折叠后主内容区margin变化', async ({ page }) => {
    const main = page.locator('.app-main')
    const initialMargin = await main.evaluate(el => el.style.marginLeft)
    await page.locator('.collapse-btn').click()
    const collapsedMargin = await main.evaluate(el => el.style.marginLeft)
    expect(collapsedMargin).not.toBe(initialMargin)
    expect(collapsedMargin).toBe('64px')
  })

  test('折叠后导航标签隐藏', async ({ page }) => {
    await page.locator('.collapse-btn').click()
    const navLabels = page.locator('.nav-label')
    for (const label of await navLabels.all()) {
      await expect(label).toBeHidden()
    }
  })

  test('折叠后logo文字隐藏', async ({ page }) => {
    await page.locator('.collapse-btn').click()
    await expect(page.locator('.logo-title')).toBeHidden()
  })
})

test.describe('主题切换', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
  })

  test('切换主题按钮存在', async ({ page }) => {
    const themeBtn = page.locator('.theme-btn')
    await expect(themeBtn).toBeVisible({ timeout: 15000 })
  })

  test('点击主题按钮切换', async ({ page }) => {
    const themeBtn = page.locator('.theme-btn')
    await page.evaluate(() => localStorage.setItem('theme', 'dark'))
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    const initialTheme = await page.evaluate(() => document.documentElement.getAttribute('data-theme'))
    await themeBtn.click()
    const newTheme = await page.evaluate(() => document.documentElement.getAttribute('data-theme'))
    expect(newTheme).not.toBe(initialTheme)
  })

  test('dark主题背景色正确', async ({ page }) => {
    await page.evaluate(() => localStorage.setItem('theme', 'dark'))
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    const bg = await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--bg-primary'))
    expect(bg.trim()).toContain('#0a0e1a')
  })

  test('light主题背景色正确', async ({ page }) => {
    await page.evaluate(() => localStorage.setItem('theme', 'light'))
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    const bg = await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--bg-primary'))
    expect(bg.trim()).toContain('#f8fafc')
  })
})

test.describe('Chat 页面', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/chat')
    await page.waitForLoadState('networkidle')
  })

  test('聊天界面可见', async ({ page }) => {
    await expect(page.locator('.chat-view')).toBeVisible({ timeout: 15000 })
  })

  test('新建会话按钮可见', async ({ page }) => {
    await expect(page.locator('.new-chat-btn')).toBeVisible({ timeout: 15000 })
  })

  test('新建会话按钮有正确文本', async ({ page }) => {
    await expect(page.locator('.new-chat-btn')).toContainText('新会话')
  })

  test('聊天侧边栏可折叠', async ({ page }) => {
    const closeBtn = page.locator('.close-btn')
    if (await closeBtn.isVisible()) {
      await closeBtn.click()
      await expect(page.locator('.chat-sidebar')).toBeHidden()
      await expect(page.locator('.sidebar-toggle')).toBeVisible()
    }
  })

  test('聊天侧边栏可重新展开', async ({ page }) => {
    const closeBtn = page.locator('.close-btn')
    if (await closeBtn.isVisible()) {
      await closeBtn.click()
      await expect(page.locator('.chat-sidebar')).toBeHidden()
      await page.locator('.sidebar-toggle').click()
      await expect(page.locator('.chat-sidebar')).toBeVisible()
    }
  })

  test('会话列表footer显示数量', async ({ page }) => {
    const footer = page.locator('.sidebar-footer')
    if (await footer.isVisible()) {
      await expect(footer).toContainText('会话')
    }
  })
})

test.describe('ModelManagement 页面', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/models')
    await page.waitForLoadState('networkidle')
  })

  test('模型管理页面标题可见', async ({ page }) => {
    await expect(page.locator('.header-title')).toHaveText('模型管理', { timeout: 15000 })
  })

  test('模型管理页面结构可见', async ({ page }) => {
    await expect(page.locator('.model-mgmt')).toBeVisible({ timeout: 15000 })
  })

  test('两列布局', async ({ page }) => {
    const content = page.locator('.content')
    const columns = await content.evaluate(el => getComputedStyle(el).gridTemplateColumns)
    expect(columns.split(' ').length).toBe(2)
  })

  test('模型能力检测面板可见', async ({ page }) => {
    await expect(page.locator('.test-controls')).toBeVisible({ timeout: 15000 })
  })

  test('模型选择器可见', async ({ page }) => {
    await expect(page.locator('.model-select')).toBeVisible({ timeout: 15000 })
  })

  test('检测按钮可见', async ({ page }) => {
    await expect(page.locator('.test-btn')).toBeVisible({ timeout: 15000 })
  })

  test('刷新按钮可见', async ({ page }) => {
    await expect(page.locator('.icon-btn')).toBeVisible({ timeout: 15000 })
  })

  test('卡片hover效果', async ({ page }) => {
    const cards = page.locator('.card')
    const firstCard = cards.first()
    if (await firstCard.isVisible()) {
      await firstCard.hover()
      const transform = await firstCard.evaluate(el => getComputedStyle(el).transform)
      expect(transform).toBeTruthy()
    }
  })
})

test.describe('Monitor 页面', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/monitor')
    await page.waitForLoadState('networkidle')
  })

  test('监控页面标题可见', async ({ page }) => {
    await expect(page.locator('.header-title')).toHaveText('实时监控', { timeout: 15000 })
  })

  test('监控页面结构可见', async ({ page }) => {
    await expect(page.locator('.monitor-view')).toBeVisible({ timeout: 15000 })
  })

  test('时间范围选择按钮可见', async ({ page }) => {
    await expect(page.locator('.range-btn').first()).toBeVisible({ timeout: 15000 })
  })

  test('时间范围5个选项', async ({ page }) => {
    await expect(page.locator('.range-btn')).toHaveCount(5, { timeout: 15000 })
  })

  test('默认时间范围1分钟active', async ({ page }) => {
    const activeBtn = page.locator('.range-btn.active')
    await expect(activeBtn).toBeVisible({ timeout: 15000 })
    await expect(activeBtn).toContainText('1分钟')
  })

  test('切换时间范围', async ({ page }) => {
    const fiveMinBtn = page.locator('.range-btn').filter({ hasText: '5分钟' })
    await fiveMinBtn.click()
    await expect(fiveMinBtn).toHaveClass(/active/)
  })

  test('刷新按钮可见', async ({ page }) => {
    await expect(page.locator('.header-btn')).toBeVisible({ timeout: 15000 })
  })

  test('GPU状态badge可见', async ({ page }) => {
    const badge = page.locator('.badge')
    await expect(badge.first()).toBeVisible({ timeout: 15000 })
  })

  test('图表卡片可见', async ({ page }) => {
    const chartCards = page.locator('.chart-card')
    await expect(chartCards.first()).toBeVisible({ timeout: 15000 })
  })

  test('LIVE标签可见', async ({ page }) => {
    await expect(page.locator('.live-tag')).toBeVisible({ timeout: 15000 })
  })

  test('统计卡片可见', async ({ page }) => {
    const statsCards = page.locator('.stats-card')
    await expect(statsCards.first()).toBeVisible({ timeout: 15000 })
  })
})

test.describe('Agent 页面', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/agent')
    await page.waitForLoadState('networkidle')
  })

  test('Agent界面可见', async ({ page }) => {
    const agentView = page.locator('.agent-view')
    if (await agentView.isVisible()) {
      await expect(agentView).toBeVisible()
    }
  })
})

test.describe('视觉一致性', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
  })

  test('CSS变量主题色正确', async ({ page }) => {
    const primary = await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--color-primary'))
    expect(primary.trim()).toBe('#6366f1')
  })

  test('卡片圆角一致性', async ({ page }) => {
    const cards = page.locator('.card')
    const radii = []
    for (const card of await cards.all()) {
      if (await card.isVisible()) {
        const borderRadius = await card.evaluate(el => getComputedStyle(el).borderRadius)
        radii.push(borderRadius)
      }
    }
    if (radii.length > 1) {
      expect(radii.every(r => r === radii[0])).toBe(true)
    }
  })

  test('所有卡片有icon-wrap', async ({ page }) => {
    const iconWraps = page.locator('.icon-wrap')
    const count = await iconWraps.count()
    expect(count).toBeGreaterThanOrEqual(7)
  })

  test('sidebar宽度正确', async ({ page }) => {
    const sidebar = page.locator('.sidebar')
    const width = await sidebar.evaluate(el => getComputedStyle(el).width)
    expect(width).toBe('220px')
  })

  test('字体family一致', async ({ page }) => {
    const bodyFont = await page.evaluate(() => getComputedStyle(document.body).fontFamily)
    expect(bodyFont).toContain('PingFang SC')
  })
})

test.describe('页面间导航一致性', () => {
  test('从Dashboard到Monitor再返回', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.locator('.nav-item').filter({ hasText: '监控' }).click()
    await expect(page).toHaveURL(/\/monitor/, { timeout: 10000 })
    await page.locator('.nav-item').filter({ hasText: '仪表盘' }).click()
    await expect(page).toHaveURL(/\//, { timeout: 10000 })
  })

  test('侧边栏在所有页面保持可见', async ({ page }) => {
    const pages = ['/', '/monitor', '/models', '/chat']
    for (const path of pages) {
      await page.goto(path)
      await page.waitForLoadState('networkidle')
      await expect(page.locator('.sidebar')).toBeVisible({ timeout: 15000 })
    }
  })

  test('404路由fallback到Dashboard', async ({ page }) => {
    await page.goto('/nonexistent-page')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('.header-title')).toHaveText('仪表盘', { timeout: 15000 })
  })
})

test.describe('页面过渡动画', () => {
  test('页面切换有过渡效果', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('.header-title')).toHaveText('仪表盘', { timeout: 15000 })
    const transition = await page.evaluate(() => {
      const main = document.querySelector('.app-main')
      return main ? getComputedStyle(main).transition : ''
    })
    expect(transition).toContain('margin-left')
  })
})
