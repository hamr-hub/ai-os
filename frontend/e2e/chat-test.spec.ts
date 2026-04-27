import { test, expect } from '@playwright/test'

test.describe('AI Agent 聊天功能测试', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/agent')
    await page.waitForLoadState('networkidle')
  })

  test('Agent页面加载和基础结构', async ({ page }) => {
    await expect(page.locator('.agent-view')).toBeVisible({ timeout: 15000 })
    await expect(page.locator('.agent-chat')).toBeVisible({ timeout: 10000 })
    
    // 检查是否有空状态
    const emptyState = page.locator('.empty-state')
    if (await emptyState.isVisible()) {
      console.log('当前为空状态，需要创建新会话')
      await expect(page.locator('.start-btn')).toBeVisible()
    }
  })

  test('创建新会话并发送消息', async ({ page }) => {
    // 点击新会话按钮
    await page.locator('.new-chat-btn').click()
    await page.waitForTimeout(1000)
    
    // 等待聊天窗口加载
    const chatWindow = page.locator('.agent-chat')
    await expect(chatWindow).toBeVisible({ timeout: 10000 })
    
    // 检查连接状态
    const connectionBanner = page.locator('.connection-banner')
    if (await connectionBanner.isVisible()) {
      const bannerText = await connectionBanner.textContent()
      console.log('连接状态:', bannerText)
    }
    
    // 查找输入框
    const textarea = page.locator('.msg-input')
    await expect(textarea).toBeVisible({ timeout: 10000 })
    
    // 输入测试消息
    await textarea.fill('你好，请简单介绍一下自己')
    await page.waitForTimeout(500)
    
    // 截图保存发送前的状态
    await page.screenshot({ path: 'test-results/chat-before-send.png' })
    
    // 点击发送按钮
    const sendBtn = page.locator('.send-btn')
    await expect(sendBtn).toBeEnabled()
    await sendBtn.click()
    
    // 等待流式响应完成（等待加载指示器消失）
    await page.waitForTimeout(15000)
    
    // 截图保存发送后的状态
    await page.screenshot({ path: 'test-results/chat-after-send.png' })
    
    // 检查是否有错误消息
    const errorMsg = page.locator('.msg-bubble:has-text("请求失败"), .msg-bubble:has-text("Error"), .msg-bubble:has-text("失败")')
    const errorCount = await errorMsg.count()
    if (errorCount > 0) {
      const errorText = await errorMsg.first().textContent()
      console.error('聊天报错:', errorText)
      throw new Error(`聊天功能报错: ${errorText}`)
    }
    
    // 检查是否有回复消息
    const messages = page.locator('.msg-row')
    const messageCount = await messages.count()
    console.log('消息数量:', messageCount)
    
    if (messageCount >= 2) {
      const lastMessage = messages.last()
      const content = await lastMessage.locator('.msg-text').textContent()
      console.log('AI 回复内容:', content?.substring(0, 200))
      
      // 验证 AI 确实回复了（不是空内容）
      if (content && content.trim().length > 0) {
        console.log('✅ AI 回复成功')
      } else {
        console.warn('⚠️ AI 回复为空')
      }
    }
    
    // 最终验证：确保没有错误
    expect(messageCount).toBeGreaterThanOrEqual(2)
  })

  test('检查网络请求和错误', async ({ page }) => {
    // 监听网络请求
    const failedRequests: string[] = []
    page.on('response', async (response) => {
      if (!response.ok()) {
        failedRequests.push(`${response.url()} - ${response.status()}`)
      }
    })

    // 监听控制台错误
    const consoleErrors: string[] = []
    page.on('pageerror', (error) => {
      consoleErrors.push(error.message)
    })

    // 创建会话并发送消息
    await page.locator('.new-chat-btn').click()
    await page.waitForTimeout(1000)
    
    const textarea = page.locator('.msg-input')
    await expect(textarea).toBeVisible({ timeout: 10000 })
    await textarea.fill('测试消息')
    
    const sendBtn = page.locator('.send-btn')
    await sendBtn.click()
    
    // 等待网络请求完成
    await page.waitForTimeout(8000)
    
    // 截图
    await page.screenshot({ path: 'test-results/chat-network-test.png' })
    
    // 输出失败请求
    if (failedRequests.length > 0) {
      console.error('失败的网络请求:', failedRequests)
    }
    
    // 输出控制台错误
    if (consoleErrors.length > 0) {
      console.error('控制台错误:', consoleErrors)
    }
  })
})
