import { test, expect } from '@playwright/test'

const CARD_TIMEOUT = 20000

async function login(page: any) {
  await page.goto('/login')
  await page.waitForLoadState('domcontentloaded')
  await page.fill('input[placeholder="输入 API Key"]', 'test-api-key')
  await page.locator('button.btn-primary:has-text("登录")').click({ force: true, timeout: 10000 })
  await page.waitForURL('**/', { timeout: 15000 })
  await page.waitForLoadState('domcontentloaded')
}

test.describe('AI OS 页面级 E2E', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('GPU 监控页可切换到 GPU 管理 tab', async ({ page }) => {
    await page.goto('/gpumonitor')
    await expect(page.locator('h1')).toContainText('GPU 监控', { timeout: CARD_TIMEOUT })
    await page.locator('.tab-btn:has-text("GPU 管理")').click()
    await expect(page).toHaveURL(/tab=manage/)
    await expect(page.locator('.gpu-manage-page')).toBeVisible({ timeout: CARD_TIMEOUT })
    await expect(page.locator('.page-title')).toContainText('GPU 管理')
  })

  test('GPU 管理页显示核心卡片与模型区块', async ({ page }) => {
    await page.goto('/gpumonitor?tab=manage')
    await expect(page.locator('.gpu-manage-page')).toBeVisible({ timeout: CARD_TIMEOUT })
    await expect(page.locator('.card-title:has-text("GPU 健康评分")')).toBeVisible()
    await expect(page.locator('.card-title:has-text("模型管理")')).toBeVisible()
    await expect(page.locator('.card-title:has-text("vLLM 运行时指标")').or(page.locator('.gpu-unavailable'))).toBeVisible()
  })

  test('GPU 管理页轮询按钮可切换状态', async ({ page }) => {
    await page.goto('/gpumonitor?tab=manage')
    const toggleBtn = page.locator('.header-right .btn').filter({ hasText: /开启轮询|轮询中/ }).first()
    await expect(toggleBtn).toBeVisible({ timeout: CARD_TIMEOUT })
    await toggleBtn.click()
    await expect(toggleBtn).toContainText('轮询中')
    await toggleBtn.click()
    await expect(toggleBtn).toContainText('开启轮询')
  })

  test('GPU 管理页存在运行中或已停止模型列表', async ({ page }) => {
    await page.goto('/gpumonitor?tab=manage')
    const runningSection = page.locator('.section-title:has-text("运行中的模型")')
    const stoppedSection = page.locator('.section-title:has-text("已停止的模型")')
    await expect(runningSection.or(stoppedSection)).toBeVisible({ timeout: CARD_TIMEOUT })
    const modelNames = page.locator('.model-item .model-name')
    expect(await modelNames.count()).toBeGreaterThan(0)
  })

  test('系统运维页可进入引擎管理 tab', async ({ page }) => {
    await page.goto('/systemops')
    await page.locator('.tab-btn:has-text("引擎管理")').click()
    await expect(page).toHaveURL(/tab=engine/)
    await expect(page.locator('h1')).toContainText('Engine Management', { timeout: CARD_TIMEOUT })
    await expect(page.locator('.header-subtitle')).toContainText('推理引擎管理')
  })

  test('引擎管理页状态概览渲染成功', async ({ page }) => {
    await page.goto('/systemops?tab=engine')
    await expect(page.locator('.engine-page')).toBeVisible({ timeout: CARD_TIMEOUT })
    await expect(page.locator('.health-summary')).toBeVisible()
    await expect(page.locator('.engine-card')).toHaveCount(3)
  })

  test('引擎管理页可切换到热切换 tab 并展示表单', async ({ page }) => {
    await page.goto('/systemops?tab=engine')
    await page.locator('.tab-btn:has-text("热切换")').click()
    await expect(page.locator('.switch-form')).toBeVisible({ timeout: CARD_TIMEOUT })
    await expect(page.locator('.section-title:has-text("引擎热切换")')).toBeVisible()
    await expect(page.locator('input[placeholder="输入模型名称或从列表选择"]')).toBeVisible()
    await expect(page.locator('input[type="number"]')).toBeVisible()
  })

  test('引擎管理页可切换到配置编辑并进入编辑态', async ({ page }) => {
    await page.goto('/systemops?tab=engine')
    await page.locator('.tab-btn:has-text("配置编辑")').click()
    const editBtn = page.locator('button:has-text("编辑配置")')
    await expect(editBtn).toBeVisible({ timeout: CARD_TIMEOUT })
    await editBtn.click()
    await expect(page.locator('button:has-text("保存")')).toBeVisible()
    await expect(page.locator('button:has-text("取消")')).toBeVisible()
  })

  test('引擎管理页可切换到日志 tab 并展示日志区域', async ({ page }) => {
    await page.goto('/systemops?tab=engine')
    await page.locator('.tab-btn:has-text("引擎日志")').click()
    await expect(page.locator('button:has-text("刷新日志")').or(page.locator('button:has-text("刷新")'))).toBeVisible({ timeout: CARD_TIMEOUT })
    await expect(page.locator('.logs-section, .log-section, pre, .code-block').first()).toBeVisible({ timeout: CARD_TIMEOUT })
  })
})
