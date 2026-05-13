import { test, expect } from '@playwright/test'

const AICLIENT_URL = 'http://localhost:3000'

test('调试：检查 AI Monitor 插件是否加载', async ({ page }) => {
  page.on('console', (msg) => {
    console.log(`[PAGE CONSOLE ${msg.type()}] ${msg.text()}`)
  })

  page.on('pageerror', (err) => {
    console.log(`[PAGE ERROR] ${err.message}`)
  })

  await page.goto(AICLIENT_URL)
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(3000)

  const title = await page.title()
  console.log(`页面标题: ${title}`)

  const body = await page.evaluate(() => document.body.innerHTML.substring(0, 500))
  console.log(`页面 Body 前500字符: ${body}`)

  const hasToggle = await page.evaluate(() => !!document.getElementById('ai-monitor-toggle'))
  console.log(`#ai-monitor-toggle 存在: ${hasToggle}`)

  const hasPanel = await page.evaluate(() => !!document.getElementById('ai-monitor-panel'))
  console.log(`#ai-monitor-panel 存在: ${hasPanel}`)

  const allScripts = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('script')).map(s => ({
      src: s.src,
      type: s.type,
      defer: s.defer,
      async: s.async
    }))
  })
  console.log('脚本列表:', JSON.stringify(allScripts, null, 2))

  const lsKeys = await page.evaluate(() => {
    const keys: Record<string, string | null> = {}
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i)!
      keys[k] = localStorage.getItem(k)
    }
    return keys
  })
  console.log('localStorage:', JSON.stringify(lsKeys, null, 2))

  await page.screenshot({ path: 'test-results/debug-page.png', fullPage: true })
})