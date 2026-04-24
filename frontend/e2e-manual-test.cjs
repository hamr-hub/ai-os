const pwCore = require('/Users/hyx/codespace/ai-os/frontend/node_modules/.pnpm/playwright@1.59.1/node_modules/playwright');
const { chromium } = pwCore;

const BASE_URL = 'http://localhost:30000';

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

async function testPage(page, name, url, actions) {
  console.log(`\n=== Testing ${name} (${url}) ===`);
  await page.goto(url);
  await sleep(3000);
  
  const title = await page.title();
  console.log(`  Page title: ${title}`);
  
  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  page.on('pageerror', err => errors.push(err.message));
  
  for (const action of actions) {
    try {
      await action(page);
    } catch (e) {
      console.log(`  FAIL: ${e.message}`);
      errors.push(`Action failed: ${e.message}`);
    }
  }
  
  if (errors.length > 0) {
    console.log(`  Console/Page errors (${errors.length}):`);
    errors.slice(0, 10).forEach(e => console.log(`    - ${e.substring(0, 200)}`));
  } else {
    console.log(`  No errors detected`);
  }
  
  return errors;
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  
  const allErrors = [];
  
  // 1. Dashboard
  allErrors.push(...await testPage(page, 'Dashboard', BASE_URL + '/', [
    async (p) => {
      const refreshBtn = p.locator('button').filter({ hasText: '刷新全部' });
      if (await refreshBtn.isVisible()) {
        console.log('  Clicking: 刷新全部');
        await refreshBtn.click();
        await sleep(2000);
      }
    },
    async (p) => {
      const alertToggle = p.locator('.alert-toggle');
      if (await alertToggle.isVisible()) {
        console.log('  Clicking: alert toggle');
        await alertToggle.click();
        await sleep(500);
        await alertToggle.click();
      }
    }
  ]));
  
  // 2. Monitor
  allErrors.push(...await testPage(page, 'Monitor', BASE_URL + '/monitor', [
    async (p) => {
      const rangeBtns = p.locator('.range-btn');
      const count = await rangeBtns.count();
      if (count > 0) {
        console.log(`  Found ${count} range buttons`);
        for (let i = 0; i < count; i++) {
          const text = await rangeBtns.nth(i).textContent();
          console.log(`    Clicking: ${text.trim()}`);
          await rangeBtns.nth(i).click();
          await sleep(1000);
        }
      }
    }
  ]));
  
  // 3. Models
  allErrors.push(...await testPage(page, 'Models', BASE_URL + '/models', [
    async (p) => {
      const testBtn = p.locator('button').filter({ hasText: '开始检测' });
      if (await testBtn.isVisible()) {
        console.log('  Clicking: 开始检测');
        await testBtn.click();
        await sleep(3000);
      }
    }
  ]));
  
  // 4. Agent
  allErrors.push(...await testPage(page, 'Agent', BASE_URL + '/agent', [
    async (p) => {
      const newChatBtn = p.locator('button').filter({ hasText: '新会话' });
      if (await newChatBtn.isVisible()) {
        console.log('  Clicking: 新会话');
        await newChatBtn.click();
        await sleep(1000);
      }
    }
  ]));
  
  // 5. Benchmarks
  allErrors.push(...await testPage(page, 'Benchmarks', BASE_URL + '/benchmarks', [
    async (p) => {
      const searchBox = p.locator('input[type="text"]').first();
      if (await searchBox.isVisible()) {
        console.log('  Typing in search box');
        await searchBox.fill('Qwen');
        await sleep(1000);
      }
    }
  ]));
  
  // 6. Docs
  allErrors.push(...await testPage(page, 'Docs', BASE_URL + '/docs', [
    async (p) => {
      const sidebarBtns = p.locator('.docs-sidebar button');
      const count = await sidebarBtns.count();
      console.log(`  Found ${count} sidebar buttons`);
      if (count > 0) {
        await sidebarBtns.first().click();
        await sleep(2000);
      }
    }
  ]));
  
  // 7. Sidebar nav - test all nav items
  allErrors.push(...await testPage(page, 'NavTest', BASE_URL + '/', [
    async (p) => {
      const navItems = p.locator('.nav-item');
      const count = await navItems.count();
      console.log(`  Found ${count} nav items`);
      const names = ['模型调度', '模型评测', 'AI Agent', '实时性能', '系统文档'];
      for (const name of names) {
        const item = navItems.filter({ hasText: name });
        if (await item.isVisible()) {
          console.log(`  Clicking nav: ${name}`);
          await item.click();
          await sleep(2000);
          const url = p.url();
          console.log(`  Navigated to: ${url}`);
        }
      }
    }
  ]));
  
  // Summary
  console.log('\n=== SUMMARY ===');
  if (allErrors.length === 0) {
    console.log('All tests passed! No errors detected.');
  } else {
    console.log(`Total errors found: ${allErrors.length}`);
    const uniqueErrors = [...new Set(allErrors)];
    uniqueErrors.forEach(e => console.log(`  - ${e.substring(0, 300)}`));
  }
  
  await browser.close();
})();
