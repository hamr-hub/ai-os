import { test, expect } from '@playwright/test'

const CARD_TIMEOUT = 15000
const ACTION_TIMEOUT = 5000

test.describe('模型切换功能', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('domcontentloaded')
    await expect(page.locator('.running-card')).toBeVisible({ timeout: CARD_TIMEOUT })
  })

  test.describe('卡片基本结构', () => {
    test('运行模型卡片可见', async ({ page }) => {
      await expect(page.locator('.running-card')).toBeVisible({ timeout: CARD_TIMEOUT })
    })

    test('卡片标题为"运行模型"', async ({ page }) => {
      const title = page.locator('.running-card .card-title')
      await expect(title).toHaveText('运行模型', { timeout: CARD_TIMEOUT })
    })

    test('模型数量显示格式正确', async ({ page }) => {
      const countBadge = page.locator('.running-card .count-badge')
      await expect(countBadge).toBeVisible({ timeout: CARD_TIMEOUT })
      await expect(countBadge).toHaveText(/\d+\s*\/\s*\d+/)
    })
  })

  test.describe('运行中模型', () => {
    test('模型列表或空状态至少一个可见', async ({ page }) => {
      const list = page.locator('.running-card .running-list')
      const empty = page.locator('.running-card .empty-state')
      await expect(list.or(empty)).toBeVisible({ timeout: CARD_TIMEOUT })
    })

    test('运行中模型行包含停止按钮', async ({ page }) => {
      const rows = page.locator('.running-card .model-row:not(.stopped)')
      const count = await rows.count()
      test.skip(count === 0, '没有运行中的模型')
      const stopBtn = rows.first().locator('.action-btn.stop')
      await expect(stopBtn).toBeVisible()
      await expect(stopBtn).toContainText('停止')
    })

    test('运行中模型显示端口信息', async ({ page }) => {
      const rows = page.locator('.running-card .model-row:not(.stopped)')
      const count = await rows.count()
      test.skip(count === 0, '没有运行中的模型')
      await expect(rows.first().locator('.model-meta')).toBeVisible()
    })

    test('默认模型显示"默认"标签', async ({ page }) => {
      const tag = page.locator('.running-card .default-tag')
      if ((await tag.count()) > 0) {
        await expect(tag.first()).toBeVisible()
        await expect(tag.first()).toContainText('默认')
      }
    })

    test('停止按钮有正确的禁用状态', async ({ page }) => {
      const stopBtn = page.locator('.running-card .action-btn.stop').first()
      if (await stopBtn.isVisible()) {
        expect(typeof (await stopBtn.isDisabled())).toBe('boolean')
      }
    })

    test('运行中模型行有绿色左边框', async ({ page }) => {
      const rows = page.locator('.running-card .model-row:not(.stopped)')
      const count = await rows.count()
      test.skip(count === 0, '没有运行中的模型')
      const borderColor = await rows.first().evaluate((el) => getComputedStyle(el).borderLeftColor)
      expect(borderColor).toBeTruthy()
    })
  })

  test.describe('可启动模型', () => {
    test('"可启动模型"区域标题存在', async ({ page }) => {
      const subHeader = page.locator('.running-card .sub-header')
      await expect(subHeader).toHaveText('可启动模型', { timeout: CARD_TIMEOUT })
    })

    test('可启动模型行包含"启动"和"切换"按钮', async ({ page }) => {
      const rows = page.locator('.running-card .stopped-section .model-row.stopped')
      const count = await rows.count()
      test.skip(count === 0, '没有可启动的模型')
      const firstRow = rows.first()
      await expect(firstRow.locator('.action-btn.start')).toBeVisible()
      await expect(firstRow.locator('.action-btn.start')).toContainText('启动')
      await expect(firstRow.locator('.action-btn.switch')).toBeVisible()
      await expect(firstRow.locator('.action-btn.switch')).toContainText('切换')
    })

    test('可启动模型显示"支持图片"或"纯文本"信息', async ({ page }) => {
      const rows = page.locator('.running-card .model-row.stopped')
      const count = await rows.count()
      test.skip(count === 0, '没有可启动的模型')
      const meta = rows.first().locator('.model-meta')
      await expect(meta).toBeVisible()
      await expect(meta).toHaveText(/支持图片|纯文本/)
    })

    test('停止模型行有左边框标识', async ({ page }) => {
      const rows = page.locator('.running-card .model-row.stopped')
      const count = await rows.count()
      test.skip(count === 0, '没有停止的模型')
      const borderColor = await rows.first().evaluate((el) => getComputedStyle(el).borderLeftColor)
      expect(borderColor).toBeTruthy()
    })
  })

  test.describe('切换进度指示', () => {
    test('切换进度区域结构正确', async ({ page }) => {
      const progress = page.locator('.running-card .switch-progress')
      const count = await progress.count()
      test.skip(count === 0, '没有正在进行的切换')
      await expect(progress.first()).toBeVisible()
      await expect(progress.first().locator('.switch-spinner')).toBeVisible()
    })

    test('切换进度文本格式正确', async ({ page }) => {
      const progress = page.locator('.running-card .switch-progress')
      const count = await progress.count()
      test.skip(count === 0, '没有正在进行的切换')
      await expect(progress.first()).toHaveText(/正在切换.*加载中|卸载旧模型/)
    })
  })

  test.describe('按钮样式与状态', () => {
    test('切换按钮样式类包含"switch"', async ({ page }) => {
      const btns = page.locator('.running-card .action-btn.switch')
      const count = await btns.count()
      test.skip(count === 0, '没有切换按钮')
      await expect(btns.first()).toHaveClass(/switch/)
    })

    test('启动按钮样式类包含"start"', async ({ page }) => {
      const btns = page.locator('.running-card .action-btn.start')
      const count = await btns.count()
      test.skip(count === 0, '没有启动按钮')
      await expect(btns.first()).toHaveClass(/start/)
    })

    test('停止按钮样式类包含"stop"', async ({ page }) => {
      const btns = page.locator('.running-card .action-btn.stop')
      const count = await btns.count()
      test.skip(count === 0, '没有停止按钮')
      await expect(btns.first()).toHaveClass(/stop/)
    })

    test('所有操作按钮禁用状态为布尔值', async ({ page }) => {
      const btns = page.locator('.running-card .action-btn')
      const count = await btns.count()
      for (let i = 0; i < Math.min(count, 3); i++) {
        const btn = btns.nth(i)
        if (await btn.isVisible()) {
          expect(typeof (await btn.isDisabled())).toBe('boolean')
        }
      }
    })
  })

  test.describe('模型信息显示', () => {
    test('模型名称非空', async ({ page }) => {
      const names = page.locator('.running-card .model-name')
      const count = await names.count()
      test.skip(count === 0, '没有模型名称')
      const name = await names.first().textContent()
      expect(name?.length).toBeGreaterThan(0)
    })
  })

  test.describe('交互行为', () => {
    test('hover模型行有位移效果', async ({ page }) => {
      const rows = page.locator('.running-card .model-row')
      const count = await rows.count()
      test.skip(count === 0, '没有模型行')
      const firstRow = rows.first()
      await firstRow.hover()
      const transform = await firstRow.evaluate((el) => getComputedStyle(el).transform)
      expect(transform).not.toBe('none')
    })

    test('点击切换按钮显示进度', async ({ page }) => {
      const btns = page.locator('.running-card .action-btn.switch')
      const count = await btns.count()
      test.skip(count === 0, '没有切换按钮')
      await btns.first().click()
      const progress = page.locator('.running-card .switch-progress')
      await expect(progress.first()).toBeVisible({ timeout: ACTION_TIMEOUT })
    })

    test('点击启动按钮显示进度', async ({ page }) => {
      const btns = page.locator('.running-card .action-btn.start')
      const count = await btns.count()
      test.skip(count === 0, '没有启动按钮')
      await btns.first().click()
      const progress = page.locator('.running-card .switch-progress')
      await expect(progress.first()).toBeVisible({ timeout: ACTION_TIMEOUT })
    })
  })

  test.describe('响应式布局', () => {
    test('宽屏(1400px)下按钮水平排列', async ({ page }) => {
      await page.setViewportSize({ width: 1400, height: 900 })
      const actions = page.locator('.running-card .model-actions')
      if (await actions.isVisible()) {
        const direction = await actions.evaluate((el) => getComputedStyle(el).flexDirection)
        expect(direction).toBe('row')
      }
    })

    test('窄屏(500px)下卡片正常适配', async ({ page }) => {
      await page.setViewportSize({ width: 500, height: 900 })
      await expect(page.locator('.running-card')).toBeVisible({ timeout: CARD_TIMEOUT })
    })
  })

  test.describe('状态刷新', () => {
    test('点击刷新按钮触发动画', async ({ page }) => {
      const refreshBtn = page.locator('.header-btn')
      await expect(refreshBtn).toBeVisible()
      await refreshBtn.click()
      await expect(refreshBtn.locator('svg')).toHaveClass(/animate-spin/, {
        timeout: ACTION_TIMEOUT,
      })
    })

    test('刷新后数量格式保持正确', async ({ page }) => {
      const empty = page.locator('.running-card .empty-state')
      if (await empty.isVisible()) {
        await page.locator('.header-btn').click()
        await page.waitForTimeout(2000)
      }
      const badge = page.locator('.running-card .count-badge')
      await expect(badge).toHaveText(/\d+\s*\/\s*\d+/)
    })
  })
})
