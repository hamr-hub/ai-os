import { test, expect, type Page } from '@playwright/test'

const FRONTEND_BASE = process.env.SERVER_FRONTEND_URL || 'http://127.0.0.1:30000'
const PLUGIN_BASE = process.env.SERVER_PLUGIN_URL || 'http://127.0.0.1:3000'
const CONTROLLER_BASE = process.env.CONTROLLER_BASE || 'http://127.0.0.1:35000'
const FRONTEND_TOKEN = process.env.AIOS_FRONTEND_TOKEN || 'admin123'
const AICLIENT_TOKEN = process.env.AICLIENT_API_KEY || 'sk-852e5a51c7c9b5e4b2b0a0518c426dfb'

type EngineType = 'vllm' | 'sglang' | 'llamacpp'

const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

async function getJson(url: string, init: RequestInit = {}) {
  const response = await fetch(url, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init.headers || {}),
    },
  })
  const text = await response.text()
  let data: any = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = { raw: text }
  }
  if (!response.ok) {
    throw new Error(`${response.status} ${url}: ${text.slice(0, 400)}`)
  }
  return data
}

function runningServices(payload: any) {
  const data = payload?.data || payload || {}
  return data.services || data.running_services || data.scheduler_status?.running_services || []
}

async function waitForEngine(model: string, engine: EngineType, timeoutMs: number) {
  const deadline = Date.now() + timeoutMs
  let lastPayload: any = null
  while (Date.now() < deadline) {
    lastPayload = await getJson(`${CONTROLLER_BASE}/manage/engines/status`)
    const service = runningServices(lastPayload).find((item: any) => {
      const itemModel = item.model || item.model_name || ''
      const itemEngine = item.engine_type || item.engine || ''
      return item.status === 'running' && itemEngine === engine && itemModel === model
    })
    if (service && ['healthy', 'ok', 'running'].includes(String(service.health || 'healthy').toLowerCase())) {
      return service
    }
    await sleep(3000)
  }
  throw new Error(`Timed out waiting for ${model} on ${engine}. Last payload: ${JSON.stringify(lastPayload).slice(0, 1200)}`)
}

async function assertChat(baseUrl: string, token: string, model: string) {
  const data = await getJson(`${baseUrl}/v1/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      model,
      messages: [{ role: 'user', content: '1+1=? 只回复2' }],
      temperature: 0,
      max_tokens: 4,
      stream: false,
    }),
  })
  const content = data?.choices?.[0]?.message?.content || ''
  expect(content).toContain('2')
  return content
}

async function loginFrontend(page: Page) {
  await page.goto(`${FRONTEND_BASE}/login`, { waitUntil: 'domcontentloaded' })
  await page.locator('.mode-btn').filter({ hasText: '密码登录' }).click()
  await page.locator('input[placeholder="输入管理密码"]').fill(FRONTEND_TOKEN)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await page.waitForURL(url => !url.pathname.includes('/login'), { timeout: 30000 })
}

test.describe.configure({ mode: 'serial' })

test('前端管控 UI 能切换模型并通过 /v1/chat/completions 对话', async ({ page }) => {
  test.setTimeout(8 * 60 * 1000)
  const model = 'Qwen2.5-0.5B-Instruct'

  await loginFrontend(page)
  await page.goto(`${FRONTEND_BASE}/systemops?tab=engine`, { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Engine Management' }).first()).toBeVisible({ timeout: 30000 })

  await page.locator('.tab-btn').filter({ hasText: '热切换' }).click()
  await page.locator('input[placeholder="输入模型名称或从列表选择"]').fill(model)
  await page.locator('.engine-option-btn').filter({ hasText: 'vLLM' }).click()
  await page.locator('input[type="number"]').fill('8000')
  await page.getByRole('button', { name: /执行切换/ }).click()
  await page.locator('.confirm-modal').getByRole('button', { name: /确认切换/ }).click()
  await expect(page.locator('.toast').filter({ hasText: /引擎切换已启动|切换/ })).toBeVisible({ timeout: 15000 })

  const service = await waitForEngine(model, 'vllm', 4 * 60 * 1000)
  await page.locator('.tab-btn').filter({ hasText: '状态概览' }).click()
  await expect(page.locator('.engine-card').filter({ hasText: model })).toBeVisible({ timeout: 30000 })
  const content = await assertChat(FRONTEND_BASE, FRONTEND_TOKEN, model)

  console.log(JSON.stringify({ surface: 'frontend', model, engine: 'vllm', port: service.port, chat: content }))
})

test('aiclient2api 插件 UI 能切换模型并通过 aiclient /v1/chat/completions 对话', async ({ page }) => {
  test.setTimeout(8 * 60 * 1000)
  const model = 'Qwen3.6-35B-A3B-Uncensored-GGUF-Q8'

  await page.addInitScript((token) => {
    localStorage.setItem('auth_token', token)
    localStorage.setItem('auth_user', 'admin')
    localStorage.setItem('aios_admin_token', token)
  }, AICLIENT_TOKEN)

  await page.goto(`${PLUGIN_BASE}/__panel_html__#aios-model`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('#section-aios-model', { timeout: 120000 })
  await page.locator('#nav-aios-model').click({ timeout: 30000 }).catch(() => undefined)
  await page.waitForSelector('#aios-switch-model', { timeout: 60000 })
  await expect.poll(async () => page.locator(`#aios-switch-model option[value="${model}"]`).count(), {
    timeout: 60000,
  }).toBeGreaterThan(0)

  await page.selectOption('#aios-switch-model', model)
  await page.selectOption('#aios-switch-engine', 'llamacpp')
  await page.locator('#aios-switch-port').fill('8200')
  await page.locator('[data-action="switch-model"]').click()
  await page.locator('.aios-p-modal').getByRole('button', { name: /^确认$/ }).click()
  await expect(page.locator('#aios-switch-status')).toContainText(/切换|引擎/, { timeout: 15000 })

  const service = await waitForEngine(model, 'llamacpp', 4 * 60 * 1000)
  await page.evaluate(() => (window as any).AiosManager?.model?.refresh?.())
  await expect(page.locator('#aios-model-banner')).toContainText(model, { timeout: 30000 })
  await expect(page.locator('#aios-model-banner')).toContainText(/llama\.cpp/i, { timeout: 30000 })
  const content = await assertChat(PLUGIN_BASE, AICLIENT_TOKEN, model)

  console.log(JSON.stringify({ surface: 'aiclient2api-plugin', model, engine: 'llamacpp', port: service.port, chat: content }))
})
