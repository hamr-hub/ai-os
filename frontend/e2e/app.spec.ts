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
  })

  test('刷新按钮可见且可点击', async ({ page }) => {
    const btn = page.locator('.header-btn')
    await expect(btn).toBeVisible({ timeout: 15000 })
    await expect(btn).toBeEnabled()
  })

  test('卡片区域可见', async ({ page }) => {
    const cards = page.locator('.card')
    await expect(cards.first()).toBeVisible({ timeout: 15000 })
  })

  test('GPU监控卡片可见', async ({ page }) => {
    const gpuCard = page.locator('.gpu-card')
    await expect(gpuCard).toBeVisible({ timeout: 15000 })
  })

  test('模型列表卡片可见', async ({ page }) => {
    const card = page.locator('.model-list-card')
    await expect(card).toBeVisible({ timeout: 15000 })
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

  test('GPU监控卡片显示badge', async ({ page }) => {
    const badge = page.locator('.gpu-card .badge')
    await expect(badge).toBeVisible({ timeout: 15000 })
  })

  test('模型列表有内容或空状态', async ({ page }) => {
    const modelTable = page.locator('.model-table .table-row')
    const emptyState = page.locator('.model-list-card .empty-state')
    await expect(modelTable.first().or(emptyState)).toBeVisible({ timeout: 10000 })
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

  test('点击导航到聊天页面', async ({ page }) => {
    await page.locator('.nav-item').filter({ hasText: '聊天' }).click()
    await expect(page).toHaveURL(/\/chat/, { timeout: 10000 })
  })

  test('点击导航到模型管理页面', async ({ page }) => {
    await page.locator('.nav-item').filter({ hasText: '模型' }).click()
    await expect(page).toHaveURL(/\/models/, { timeout: 10000 })
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
})
