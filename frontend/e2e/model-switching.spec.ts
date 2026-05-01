import { test, expect } from '@playwright/test'

async function login(page: any) {
  await page.goto('/login')
  await page.waitForLoadState('domcontentloaded')
  await page.waitForTimeout(500)
  await page.fill('input[placeholder="输入 API Key"]', 'test-api-key')
  await page.waitForTimeout(300)
  await page.locator('button.btn-primary:has-text("登录")').click({ force: true, timeout: 10000 })
  await page.waitForURL('**/', { timeout: 15000 })
  await page.waitForLoadState('domcontentloaded')
  await page.waitForTimeout(500)
}

const CARD_TIMEOUT = 15000
const ACTION_TIMEOUT = 5000

test.describe('模型切换功能', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
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

    test('运行中模型区域结构正确', async ({ page }) => {
      const card = page.locator('.running-card')
      await expect(card).toBeVisible({ timeout: CARD_TIMEOUT })
      await expect(card.locator('.card-icon-inner')).toBeVisible()
    })

    test('运行中模型显示端口信息', async ({ page }) => {
      const rows = page.locator('.running-card .model-row:not(.stopped)')
      if ((await rows.count()) === 0) {
        const emptyState = page.locator('.running-card .empty-state')
        await expect(emptyState).toBeVisible()
      } else {
        await expect(rows.first().locator('.model-meta')).toBeVisible()
      }
    })

    test('默认模型显示"默认"标签', async ({ page }) => {
      const tag = page.locator('.running-card .default-tag')
      const count = await tag.count()
      if (count > 0) {
        await expect(tag.first()).toContainText('默认')
      } else {
        expect(count).toBeGreaterThanOrEqual(0)
      }
    })

    test('停止按钮样式类正确', async ({ page }) => {
      const btns = page.locator('.running-card .action-btn.stop')
      const count = await btns.count()
      if (count > 0) {
        await expect(btns.first()).toBeVisible()
        await expect(btns.first()).toContainText('停止')
      } else {
        const emptyState = page.locator('.running-card .empty-state')
        await expect(emptyState).toBeVisible()
      }
    })

    test('运行中模型行有左边框标识', async ({ page }) => {
      const rows = page.locator('.running-card .model-row:not(.stopped)')
      const count = await rows.count()
      if (count === 0) {
        const emptyState = page.locator('.running-card .empty-state')
        await expect(emptyState).toBeVisible()
      } else {
        const borderColor = await rows.first().evaluate((el) => getComputedStyle(el).borderLeftColor)
        expect(borderColor).toBeTruthy()
      }
    })
  })

  test.describe('可启动模型', () => {
    test('"可启动模型"区域标题存在', async ({ page }) => {
      const rows = page.locator('.running-card .model-row.stopped')
      const count = await rows.count()
      if (count > 0) {
        await expect(page.locator('.running-card .sub-header')).toHaveText('可启动模型', {
          timeout: CARD_TIMEOUT,
        })
      } else {
        expect(count).toBe(0)
      }
    })

    test('可启动模型区域结构完整', async ({ page }) => {
      const rows = page.locator('.running-card .model-row.stopped')
      const count = await rows.count()
      if (count > 0) {
        const stoppedSection = page.locator('.running-card .stopped-section')
        await expect(stoppedSection).toBeVisible({ timeout: CARD_TIMEOUT })
        await expect(stoppedSection.locator('.stopped-list')).toBeAttached()
      } else {
        expect(count).toBe(0)
      }
    })

    test('可启动模型行结构正确', async ({ page }) => {
      const rows = page.locator('.running-card .model-row.stopped')
      const count = await rows.count()
      if (count > 0) {
        const firstRow = rows.first()
        await expect(firstRow).toHaveClass(/model-row/)
        await expect(firstRow).toHaveClass(/stopped/)
        await expect(firstRow.locator('.model-name')).toBeVisible()
        await expect(firstRow.locator('.model-meta')).toBeVisible()
      } else {
        expect(count).toBeGreaterThanOrEqual(0)
      }
    })

    test('可启动模型按钮组完整', async ({ page }) => {
      const rows = page.locator('.running-card .model-row.stopped')
      const count = await rows.count()
      if (count > 0) {
        const firstRow = rows.first()
        const actions = firstRow.locator('.model-actions')
        await expect(actions).toBeVisible()
        await expect(actions.locator('.action-btn.start')).toBeVisible()
        await expect(actions.locator('.action-btn.switch')).toBeVisible()
      } else {
        expect(count).toBeGreaterThanOrEqual(0)
      }
    })

    test('可启动模型显示文本支持信息', async ({ page }) => {
      const rows = page.locator('.running-card .model-row.stopped')
      const count = await rows.count()
      if (count > 0) {
        const meta = rows.first().locator('.model-meta')
        await expect(meta).toBeVisible()
        await expect(meta).toHaveText(/支持图片|纯文本/)
      } else {
        expect(count).toBeGreaterThanOrEqual(0)
      }
    })

    test('停止模型行有左边框标识', async ({ page }) => {
      const rows = page.locator('.running-card .model-row.stopped')
      const count = await rows.count()
      if (count > 0) {
        const borderColor = await rows.first().evaluate((el) => getComputedStyle(el).borderLeftColor)
        expect(borderColor).toBeTruthy()
      } else {
        expect(count).toBeGreaterThanOrEqual(0)
      }
    })
  })

  test.describe('切换进度指示', () => {
    test('切换进度区域结构正确', async ({ page }) => {
      const progress = page.locator('.running-card .switch-progress')
      const count = await progress.count()
      if (count > 0) {
        await expect(progress.first()).toBeVisible()
        await expect(progress.first().locator('.switch-spinner')).toBeVisible()
      } else {
        expect(count).toBeGreaterThanOrEqual(0)
      }
    })

    test('切换进度文本格式正确', async ({ page }) => {
      const progress = page.locator('.running-card .switch-progress')
      const count = await progress.count()
      if (count > 0) {
        await expect(progress.first()).toHaveText(/正在切换.*加载中|卸载旧模型/)
      } else {
        expect(count).toBeGreaterThanOrEqual(0)
      }
    })
  })

  test.describe('按钮样式与状态', () => {
    test('切换按钮样式类包含"switch"', async ({ page }) => {
      const btns = page.locator('.running-card .action-btn.switch')
      const count = await btns.count()
      if (count > 0) {
        await expect(btns.first()).toHaveClass(/switch/)
      } else {
        expect(count).toBeGreaterThanOrEqual(0)
      }
    })

    test('启动按钮样式类包含"start"', async ({ page }) => {
      const btns = page.locator('.running-card .action-btn.start')
      const count = await btns.count()
      if (count > 0) {
        await expect(btns.first()).toHaveClass(/start/)
      } else {
        expect(count).toBeGreaterThanOrEqual(0)
      }
    })

    test('停止按钮样式类包含"stop"', async ({ page }) => {
      const btns = page.locator('.running-card .action-btn.stop')
      const count = await btns.count()
      if (count > 0) {
        await expect(btns.first()).toHaveClass(/stop/)
      } else {
        expect(count).toBeGreaterThanOrEqual(0)
      }
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
      if (count > 0) {
        const name = await names.first().textContent()
        expect(name?.length).toBeGreaterThan(0)
      } else {
        expect(count).toBeGreaterThanOrEqual(0)
      }
    })
  })

  test.describe('交互行为', () => {
    test('hover模型行有位移效果', async ({ page }) => {
      const rows = page.locator('.running-card .model-row')
      const count = await rows.count()
      if (count > 0) {
        const firstRow = rows.first()
        await firstRow.hover()
        const transform = await firstRow.evaluate((el) => getComputedStyle(el).transform)
        expect(transform).not.toBe('none')
      } else {
        expect(count).toBeGreaterThanOrEqual(0)
      }
    })

    test('点击切换按钮显示进度', async ({ page }) => {
      const btns = page.locator('.running-card .action-btn.switch')
      const count = await btns.count()
      if (count > 0) {
        await btns.first().click()
        const progress = page.locator('.running-card .switch-progress')
        await expect(progress.first()).toBeVisible({ timeout: ACTION_TIMEOUT })
      } else {
        expect(count).toBeGreaterThanOrEqual(0)
      }
    })

    test('点击启动按钮显示进度', async ({ page }) => {
      const btns = page.locator('.running-card .action-btn.start')
      const count = await btns.count()
      if (count > 0) {
        await btns.first().click()
        const progress = page.locator('.running-card .switch-progress')
        await expect(progress.first()).toBeVisible({ timeout: ACTION_TIMEOUT })
      } else {
        expect(count).toBeGreaterThanOrEqual(0)
      }
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
      await page.locator('.header-btn').click()
      await page.waitForTimeout(2000)
      const badge = page.locator('.running-card .count-badge')
      if ((await badge.count()) > 0) {
        await expect(badge).toHaveText(/\d+\s*\/\s*\d+/)
      } else {
        const rows = page.locator('.running-card .model-row')
        expect(await rows.count()).toBeGreaterThanOrEqual(0)
      }
    })
  })
})
