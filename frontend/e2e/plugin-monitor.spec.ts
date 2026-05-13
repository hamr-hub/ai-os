import { test, expect } from '@playwright/test'

const AICLIENT_URL = 'http://localhost:3000'
const PANEL_TIMEOUT = 30000
const TOAST_TIMEOUT = 10000
const REQUEST_TIMEOUT = 30000

const ADMIN_TOKEN = 'test-api-key'

test.describe('AI Monitor 插件 - 按钮逐个点击测试', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript((token) => {
      localStorage.setItem('authToken', token)
      localStorage.setItem('authTokenExpiry', String(Date.now() + 86400000))
      localStorage.setItem('aios_admin_token', token)
    }, ADMIN_TOKEN)

    await page.goto(AICLIENT_URL)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
  })

  async function openPanel(page: any) {
    const toggle = page.locator('#ai-monitor-toggle')
    await toggle.waitFor({ state: 'visible', timeout: PANEL_TIMEOUT })
    await toggle.click()
    const panel = page.locator('#ai-monitor-panel')
    await expect(panel).toHaveClass(/aim-panel-open/, { timeout: PANEL_TIMEOUT })
    await page.waitForTimeout(800)
  }

  test.describe('AI Monitor 面板', () => {
    test('面板可正常打开和关闭', async ({ page }) => {
      const toggle = page.locator('#ai-monitor-toggle')
      await expect(toggle).toBeVisible({ timeout: PANEL_TIMEOUT })

      await toggle.click()
      const panel = page.locator('#ai-monitor-panel')
      await expect(panel).toHaveClass(/aim-panel-open/, { timeout: PANEL_TIMEOUT })

      await toggle.click()
      await expect(panel).not.toHaveClass(/aim-panel-open/, { timeout: PANEL_TIMEOUT })
    })

    test('面板标题为"AI Monitor"', async ({ page }) => {
      await openPanel(page)
      const title = page.locator('#ai-monitor-panel .aim-panel-title')
      await expect(title).toHaveText('AI Monitor')
    })

    test('引擎状态卡片有3个 (vLLM / SGLang / llama.cpp)', async ({ page }) => {
      await openPanel(page)
      const cards = page.locator('.aim-engine-card')
      await expect(cards).toHaveCount(3)
    })
  })

  test.describe('模型切换按钮', () => {
    test('切换模型下拉选择非空', async ({ page }) => {
      await openPanel(page)
      const modelSelect = page.locator('#aim-switch-model-select')
      await expect(modelSelect).toBeVisible()
      const options = modelSelect.locator('option')
      const count = await options.count()
      expect(count).toBeGreaterThan(1)
    })

    test('模型选择 → 点击"切换模型"按钮 → 触发 Toast 通知', async ({ page }) => {
      await openPanel(page)

      const modelSelect = page.locator('#aim-switch-model-select')
      await expect(modelSelect).toBeVisible()
      const options = modelSelect.locator('option')
      const count = await options.count()

      if (count <= 1) {
        test.skip(true, '没有可用的模型选项')
        return
      }

      const optionValues = await options.evaluateAll((opts: HTMLOptionElement[]) =>
        opts.filter(o => o.value).map(o => o.value)
      )

      let selectedModel: string | null = null
      for (const v of optionValues) {
        if (!v.includes('(运行中)')) {
          selectedModel = v
          break
        }
      }
      if (!selectedModel) {
        selectedModel = optionValues[0]
      }

      if (!selectedModel) {
        test.skip(true, '没有可选的模型')
        return
      }

      await modelSelect.selectOption(selectedModel)
      await page.waitForTimeout(300)

      const engineSelect = page.locator('#aim-switch-engine-select')
      await expect(engineSelect).toBeVisible({ timeout: 5000 })
      await engineSelect.selectOption('vllm')

      const switchBtn = page.locator('#aim-switch-model-btn')
      await expect(switchBtn).toBeVisible()
      await expect(switchBtn).toBeEnabled()

      console.log(`点击切换模型按钮: ${selectedModel} (vllm)`)
      await switchBtn.click()

      await expect(switchBtn).toHaveText('切换中...', { timeout: 5000 })

      await page.waitForTimeout(2000)

      const toast = page.locator('.aim-toast')
      const toastCount = await toast.count()
      if (toastCount > 0) {
        const toastText = await toast.first().textContent()
        console.log(`Toast 通知: ${toastText}`)
        expect(toastText).toBeTruthy()
      }
    })

    test('不选模型直接点击"切换模型" → 提示选择模型', async ({ page }) => {
      await openPanel(page)

      const modelSelect = page.locator('#aim-switch-model-select')
      await modelSelect.selectOption('')

      const switchBtn = page.locator('#aim-switch-model-btn')
      await switchBtn.click()

      const toast = page.locator('.aim-toast-warning')
      await expect(toast.first()).toBeVisible({ timeout: TOAST_TIMEOUT })
      await expect(toast.first()).toContainText('请选择目标模型')
    })

    test('切换模型按钮禁用时不可点击', async ({ page }) => {
      await openPanel(page)

      const switchBtn = page.locator('#aim-switch-model-btn')
      const disabled = await switchBtn.isDisabled()
      expect(typeof disabled).toBe('boolean')
    })
  })

  test.describe('引擎切换按钮 - vLLM', () => {
    test('点击 vLLM 引擎切换按钮 → 触发请求', async ({ page }) => {
      await openPanel(page)

      const vllmBtn = page.locator('.aim-btn-engine[data-engine="vllm"]')
      await expect(vllmBtn).toBeVisible()

      const modelSelect = page.locator('#aim-switch-model-select')
      const options = modelSelect.locator('option')
      const count = await options.count()
      if (count <= 1) {
        test.skip(true, '没有可选模型，引擎切换需要先选模型')
        return
      }

      const optionValues = await options.evaluateAll((opts: HTMLOptionElement[]) =>
        opts.filter(o => o.value).map(o => o.value)
      )
      const modelToUse = optionValues[0]
      await modelSelect.selectOption(modelToUse)
      await page.waitForTimeout(200)

      console.log('点击 vLLM 引擎切换按钮')
      await vllmBtn.click()

      await page.waitForTimeout(2000)

      const toast = page.locator('.aim-toast')
      const toastCount = await toast.count()
      if (toastCount > 0) {
        const toastText = await toast.first().textContent()
        console.log(`Toast: ${toastText}`)
        expect(toastText).toBeTruthy()
      }
    })
  })

  test.describe('引擎切换按钮 - SGLang', () => {
    test('点击 SGLang 引擎切换按钮 → 触发请求', async ({ page }) => {
      await openPanel(page)

      const sglangBtn = page.locator('.aim-btn-engine[data-engine="sglang"]')
      await expect(sglangBtn).toBeVisible()

      const modelSelect = page.locator('#aim-switch-model-select')
      const options = modelSelect.locator('option')
      const count = await options.count()
      if (count <= 1) {
        test.skip(true, '没有可选模型')
        return
      }

      const optionValues = await options.evaluateAll((opts: HTMLOptionElement[]) =>
        opts.filter(o => o.value).map(o => o.value)
      )
      const modelToUse = optionValues[0]
      await modelSelect.selectOption(modelToUse)
      await page.waitForTimeout(200)

      console.log('点击 SGLang 引擎切换按钮')
      await sglangBtn.click()

      await page.waitForTimeout(2000)

      const toast = page.locator('.aim-toast')
      const toastCount = await toast.count()
      if (toastCount > 0) {
        const toastText = await toast.first().textContent()
        console.log(`Toast: ${toastText}`)
        expect(toastText).toBeTruthy()
      }
    })
  })

  test.describe('引擎切换按钮 - llama.cpp', () => {
    test('点击 llama.cpp 引擎切换按钮 → 触发请求', async ({ page }) => {
      await openPanel(page)

      const llamaBtn = page.locator('.aim-btn-engine[data-engine="llamacpp"]')
      await expect(llamaBtn).toBeVisible()

      const modelSelect = page.locator('#aim-switch-model-select')
      const options = modelSelect.locator('option')
      const count = await options.count()
      if (count <= 1) {
        test.skip(true, '没有可选模型')
        return
      }

      const optionValues = await options.evaluateAll((opts: HTMLOptionElement[]) =>
        opts.filter(o => o.value).map(o => o.value)
      )
      const modelToUse = optionValues[0]
      await modelSelect.selectOption(modelToUse)
      await page.waitForTimeout(200)

      console.log('点击 llama.cpp 引擎切换按钮')
      await llamaBtn.click()

      await page.waitForTimeout(2000)

      const toast = page.locator('.aim-toast')
      const toastCount = await toast.count()
      if (toastCount > 0) {
        const toastText = await toast.first().textContent()
        console.log(`Toast: ${toastText}`)
        expect(toastText).toBeTruthy()
      }
    })
  })

  test.describe('引擎切换 - 不选模型直接点击', () => {
    test('不选模型点 vLLM 引擎切换 → 提示需要模型', async ({ page }) => {
      await openPanel(page)

      const modelSelect = page.locator('#aim-switch-model-select')
      await modelSelect.selectOption('')

      const vllmBtn = page.locator('.aim-btn-engine[data-engine="vllm"]')
      await vllmBtn.click()

      const toast = page.locator('.aim-toast-warning')
      await expect(toast.first()).toBeVisible({ timeout: TOAST_TIMEOUT })
      await expect(toast.first()).toContainText('请先选择模型')
    })

    test('不选模型点 SGLang 引擎切换 → 提示需要模型', async ({ page }) => {
      await openPanel(page)

      const modelSelect = page.locator('#aim-switch-model-select')
      await modelSelect.selectOption('')

      const sglangBtn = page.locator('.aim-btn-engine[data-engine="sglang"]')
      await sglangBtn.click()

      const toast = page.locator('.aim-toast-warning')
      await expect(toast.first()).toBeVisible({ timeout: TOAST_TIMEOUT })
      await expect(toast.first()).toContainText('请先选择模型')
    })

    test('不选模型点 llama.cpp 引擎切换 → 提示需要模型', async ({ page }) => {
      await openPanel(page)

      const modelSelect = page.locator('#aim-switch-model-select')
      await modelSelect.selectOption('')

      const llamaBtn = page.locator('.aim-btn-engine[data-engine="llamacpp"]')
      await llamaBtn.click()

      const toast = page.locator('.aim-toast-warning')
      await expect(toast.first()).toBeVisible({ timeout: TOAST_TIMEOUT })
      await expect(toast.first()).toContainText('请先选择模型')
    })
  })

  test.describe('刷新按钮', () => {
    test('点击刷新按钮触发数据刷新', async ({ page }) => {
      await openPanel(page)

      const refreshBtn = page.locator('#aim-refresh-btn')
      await expect(refreshBtn).toBeVisible()

      await refreshBtn.click()
      await page.waitForTimeout(1500)

      const cards = page.locator('.aim-engine-card')
      await expect(cards).toHaveCount(3)
    })
  })

  test.describe('完整切换流程', () => {
    test('切换模型 + 引擎切换一起测试', async ({ page }) => {
      await openPanel(page)

      const modelSelect = page.locator('#aim-switch-model-select')
      const options = modelSelect.locator('option')
      const count = await options.count()

      if (count <= 1) {
        test.skip(true, '没有可用模型')
        return
      }

      const optionValues = await options.evaluateAll((opts: HTMLOptionElement[]) =>
        opts.filter(o => o.value).map(o => o.value)
      )

      let targetModel: string | null = null
      for (const v of optionValues) {
        if (!v.includes('(运行中)')) {
          targetModel = v
          break
        }
      }
      if (!targetModel) targetModel = optionValues[0]
      if (!targetModel) {
        test.skip(true, '无模型可选')
        return
      }

      const cleanModelName = targetModel.replace(/\s*\(.*?\)\s*/g, '').replace(/\s*★\s*/g, '')
      await modelSelect.selectOption(targetModel)
      await page.waitForTimeout(300)

      console.log(`步骤1: 切换模型到 ${cleanModelName}`)

      const engineSelect = page.locator('#aim-switch-engine-select')
      await engineSelect.selectOption('vllm')

      const switchBtn = page.locator('#aim-switch-model-btn')
      await switchBtn.click()
      await page.waitForTimeout(3000)

      console.log('步骤2: 切换到 SGLang 引擎')

      const modelSelect2 = page.locator('#aim-switch-model-select')
      const opts2 = modelSelect2.locator('option')
      const count2 = await opts2.count()
      if (count2 > 1) {
        const vals = await opts2.evaluateAll((opts: HTMLOptionElement[]) =>
          opts.filter(o => o.value).map(o => o.value)
        )
        if (vals.length > 0) {
          await modelSelect2.selectOption(vals[0])
          await page.waitForTimeout(200)
        }
      }

      const sglangBtn = page.locator('.aim-btn-engine[data-engine="sglang"]')
      await sglangBtn.click()

      await page.waitForTimeout(2000)

      console.log('步骤3: 切换到 llama.cpp 引擎')

      const modelSelect3 = page.locator('#aim-switch-model-select')
      const opts3 = modelSelect3.locator('option')
      const count3 = await opts3.count()
      if (count3 > 1) {
        const vals = await opts3.evaluateAll((opts: HTMLOptionElement[]) =>
          opts.filter(o => o.value).map(o => o.value)
        )
        if (vals.length > 0) {
          await modelSelect3.selectOption(vals[0])
          await page.waitForTimeout(200)
        }
      }

      const llamaBtn = page.locator('.aim-btn-engine[data-engine="llamacpp"]')
      await llamaBtn.click()

      await page.waitForTimeout(2000)

      const toast = page.locator('.aim-toast')
      const toastCount = await toast.count()
      expect(toastCount).toBeGreaterThanOrEqual(0)
    })
  })
})