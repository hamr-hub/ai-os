import { test, expect } from '@playwright/test'

async function login(page: any) {
  await page.goto('/login')
  await page.waitForLoadState('domcontentloaded')
  await page.waitForTimeout(1000)
  await page.fill('input[placeholder="输入 API Key"]', 'test-api-key')
  await page.waitForTimeout(500)
  await page.locator('.btn-primary:has-text("登录")').click({ force: true })
  await page.waitForURL('**/', { timeout: 15000 })
  await page.waitForLoadState('domcontentloaded')
  await page.waitForTimeout(1000)
}

test.describe('AI Agent 聊天功能测试', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
    await page.goto('/agent')
    await page.waitForLoadState('domcontentloaded')
  })

  test('Agent页面加载和基础结构', async ({ page }) => {
    await expect(page.locator('.agent-view')).toBeVisible({ timeout: 15000 })
    await expect(page.locator('.agent-chat')).toBeVisible({ timeout: 10000 })
    
    const emptyState = page.locator('.empty-state')
    if (await emptyState.isVisible()) {
      console.log('当前为空状态，需要创建新会话')
      await expect(page.locator('.start-btn')).toBeVisible()
    }
  })

  test('创建新会话并发送消息', async ({ page }) => {
    await page.locator('.new-chat-btn').click()
    await page.waitForTimeout(1000)
    
    const chatWindow = page.locator('.agent-chat')
    await expect(chatWindow).toBeVisible({ timeout: 10000 })
    
    const connectionBanner = page.locator('.connection-banner')
    if (await connectionBanner.isVisible()) {
      const bannerText = await connectionBanner.textContent()
      console.log('连接状态:', bannerText)
    }
    
    const textarea = page.locator('.msg-input')
    await expect(textarea).toBeVisible({ timeout: 10000 })
    
    await textarea.fill('你好，请简单介绍一下自己')
    await page.waitForTimeout(500)
    
    const sendBtn = page.locator('.send-btn')
    await expect(sendBtn).toBeEnabled()
    await sendBtn.click()
    
    await page.waitForTimeout(15000)
    
    const errorMsg = page.locator('.msg-bubble:has-text("请求失败"), .msg-bubble:has-text("Error"), .msg-bubble:has-text("失败")')
    const errorCount = await errorMsg.count()
    if (errorCount > 0) {
      const errorText = await errorMsg.first().textContent()
      console.error('聊天报错:', errorText)
      throw new Error(`聊天功能报错: ${errorText}`)
    }
    
    const messages = page.locator('.msg-row')
    const messageCount = await messages.count()
    console.log('消息数量:', messageCount)
    
    if (messageCount >= 2) {
      const lastMessage = messages.last()
      const content = await lastMessage.locator('.msg-text').textContent()
      console.log('AI 回复内容:', content?.substring(0, 200))
      
      if (content && content.trim().length > 0) {
        console.log('✅ AI 回复成功')
      } else {
        console.warn('⚠️ AI 回复为空')
      }
    }
    
    expect(messageCount).toBeGreaterThanOrEqual(2)
  })

  test('检查网络请求和错误', async ({ page }) => {
    const failedRequests: string[] = []
    page.on('response', async (response) => {
      if (!response.ok()) {
        failedRequests.push(`${response.url()} - ${response.status()}`)
      }
    })

    const consoleErrors: string[] = []
    page.on('pageerror', (error) => {
      consoleErrors.push(error.message)
    })

    await page.locator('.new-chat-btn').click()
    await page.waitForTimeout(1000)
    
    const textarea = page.locator('.msg-input')
    await expect(textarea).toBeVisible({ timeout: 10000 })
    await textarea.fill('测试消息')
    
    const sendBtn = page.locator('.send-btn')
    await sendBtn.click()
    
    await page.waitForTimeout(8000)
    
    if (failedRequests.length > 0) {
      console.error('失败的网络请求:', failedRequests)
    }
    
    if (consoleErrors.length > 0) {
      console.error('控制台错误:', consoleErrors)
    }
  })
})
