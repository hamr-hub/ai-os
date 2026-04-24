import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const pwPath = '/Users/hyx/codespace/ai-os/frontend/node_modules/.pnpm/@playwright+test@1.59.1/node_modules/@playwright/test';
const pw = require(pwPath);
const chromium = pw.devices ? undefined : pw.chromium;
if (!chromium) {
  // Try alternative approach
  const pwCore = require('/Users/hyx/codespace/ai-os/frontend/node_modules/.pnpm/playwright@1.59.1/node_modules/playwright');
  const { chromium: ch } = pwCore;
  globalThis.chromium = ch;
}

const BASE_URL = 'http://localhost:30000';

async function sleep(ms) {
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
      } else {
        const iconBtns = p.locator('.header-btn');
        if (await iconBtns.first().isVisible()) {
          console.log('  Clicking: refresh icon button');
          await iconBtns.first().click();
          await sleep(2000);
        }
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
      const refreshBtn = p.locator('.header-btn');
      if (await refreshBtn.isVisible()) {
        console.log('  Clicking: refresh button');
        await refreshBtn.click();
        await sleep(2000);
      }
    },
    async (p) => {
      const rangeBtns = p.locator('.range-btn');
      const count = await rangeBtns.count();
      if (count > 0) {
        console.log(`  Found ${count} range buttons, clicking each`);
        for (let i = 0; i < count; i++) {
          const text = await rangeBtns.nth(i).textContent();
          console.log(`    Clicking: ${text}`);
          await rangeBtns.nth(i).click();
          await sleep(1000);
        }
      }
    }
  ]));
  
  // 3. Models
  allErrors.push(...await testPage(page, 'Models', BASE_URL + '/models', [
    async (p) => {
      const refreshBtn = p.locator('.page-header button, .header-btn, button.icon-btn').first();
      if (await refreshBtn.isVisible()) {
        console.log('  Clicking: refresh button');
        await refreshBtn.click();
        await sleep(2000);
      }
    },
    async (p) => {
      const testBtn = p.locator('.test-btn, button').filter({ hasText: '开始检测' });
      if (await testBtn.isVisible()) {
        console.log('  Clicking: 开始检测');
        await testBtn.click();
        await sleep(3000);
      }
    },
    async (p) => {
      const modelSelect = p.locator('.model-select, select');
      if (await modelSelect.isVisible()) {
        console.log('  Interacting: model select');
        await modelSelect.click();
        await sleep(500);
      }
    }
  ]));
  
  // 4. Agent
  allErrors.push(...await testPage(page, 'Agent', BASE_URL + '/agent', [
    async (p) => {
      const newChatBtn = p.locator('.new-chat-btn, button').filter({ hasText: '新会话' });
      if (await newChatBtn.isVisible()) {
        console.log('  Clicking: 新会话');
        await newChatBtn.click();
        await sleep(1000);
      }
    },
    async (p) => {
      const sidebarToggle = p.locator('.sidebar-toggle, button.close-btn').first();
      if (await sidebarToggle.isVisible()) {
        console.log('  Clicking: sidebar toggle');
        await sidebarToggle.click();
        await sleep(500);
      }
    },
    async (p) => {
      const modelPicker = p.locator('.model-picker, button').filter({ hasText: /model/i });
      if (await modelPicker.isVisible()) {
        console.log('  Clicking: model picker');
        await modelPicker.click();
        await sleep(500);
      }
    },
    async (p) => {
      const toggleSidebarBtn = p.locator('.sidebar-toggle');
      if (await toggleSidebarBtn.isVisible()) {
        console.log('  Clicking: sidebar toggle to expand');
        await toggleSidebarBtn.click();
        await sleep(500);
      }
    }
  ]));
  
  // 5. Benchmarks
  allErrors.push(...await testPage(page, 'Benchmarks', BASE_URL + '/benchmarks', [
    async (p) => {
      const refreshBtn = p.locator('.header-btn, button').filter({ hasText: '刷新' });
      if (await refreshBtn.isVisible()) {
        console.log('  Clicking: refresh button');
        await refreshBtn.click();
        await sleep(2000);
      }
    },
    async (p) => {
      const searchBox = p.locator('.search-box, input[type="text"]').first();
      if (await searchBox.isVisible()) {
        console.log('  Typing in search box');
        await searchBox.fill('test');
        await sleep(1000);
        await searchBox.clear();
      }
    }
  ]));
  
  // 6. Docs
  allErrors.push(...await testPage(page, 'Docs', BASE_URL + '/docs', [
    async (p) => {
      const groupToggle = p.locator('.group-toggle, button').first();
      if (await groupToggle.isVisible()) {
        console.log('  Clicking: group toggle');
        await groupToggle.click();
        await sleep(500);
      }
    },
    async (p) => {
      const docBtn = p.locator('.doc-btn, button').first();
      if (await docBtn.isVisible()) {
        console.log('  Clicking: first doc button');
        await docBtn.click();
        await sleep(2000);
      }
    }
  ]));
  
  // 7. TopBar - connection test
  allErrors.push(...await testPage(page, 'TopBar-Connection', BASE_URL + '/', [
    async (p) => {
      const switchBtn = p.locator('button').filter({ hasText: '切换服务' });
      if (await switchBtn.isVisible()) {
        console.log('  Clicking: 切换服务');
        await switchBtn.click();
        await sleep(1000);
        // Close dropdown by clicking elsewhere
        await p.click('body');
        await sleep(500);
      }
    },
    async (p) => {
      const refreshConnBtn = p.locator('.topbar button').first();
      if (await refreshConnBtn.isVisible()) {
        console.log('  Clicking: refresh connection');
        await refreshConnBtn.click();
        await sleep(2000);
      }
    }
  ]));
  
  // 8. Sidebar - theme toggle
  allErrors.push(...await testPage(page, 'Sidebar-Theme', BASE_URL + '/', [
    async (p) => {
      const sidebar = p.locator('.sidebar');
      if (await sidebar.isVisible()) {
        const themeBtn = sidebar.locator('.action-btn').first();
        if (await themeBtn.isVisible()) {
          console.log('  Clicking: theme toggle');
          await themeBtn.click();
          await sleep(500);
          await themeBtn.click();
          await sleep(500);
        }
      }
    },
    async (p) => {
      const sidebar = p.locator('.sidebar');
      if (await sidebar.isVisible()) {
        const collapseBtn = sidebar.locator('.action-btn').nth(1);
        if (await collapseBtn.isVisible()) {
          console.log('  Clicking: sidebar collapse');
          await collapseBtn.click();
          await sleep(500);
          await collapseBtn.click();
          await sleep(500);
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
