#!/usr/bin/env node
// fetch_page.js <url> <out.html> [out-meta.json]
// Headless Chromium: load WeChat article, rebuild MathJax-SVG formulas into
// standard MathML in-page, then write the cleaned article HTML (with <math>).

const fs = require('fs');
const path = require('path');

function loadPlaywright() {
  const candidates = [
    process.env.WX2MD_PLAYWRIGHT,
    path.join(__dirname, 'node_modules', 'playwright'),
    path.join(process.env.HOME || '', '.config/opencode/skills-disabled/playwright-web-headless-search/scripts/node_modules/playwright'),
    path.join(process.env.HOME || '', '.config/opencode/skills/playwright-web-headless-search/scripts/node_modules/playwright'),
  ].filter(Boolean);
  for (const c of candidates) {
    try { return require(c); } catch (e) { /* try next */ }
  }
  try { return require('playwright'); } catch (e) { /* fallthrough */ }
  throw new Error(
    'playwright not found. Set WX2MD_PLAYWRIGHT=/path/to/playwright or install it:\n' +
    '  cd ~/.config/opencode/skills-disabled/playwright-web-headless-search/scripts && npm install playwright && npx playwright install chromium'
  );
}

const { chromium } = loadPlaywright();

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0';

(async () => {
  const [, , url, outHtml, outMeta] = process.argv;
  if (!url || !outHtml) {
    console.error('usage: fetch_page.js <url> <out.html> [out-meta.json]');
    process.exit(2);
  }
  const convert = fs.readFileSync(path.join(__dirname, 'convert.js'), 'utf8');
  const browser = await chromium.launch({ headless: true });
  try {
    const ctx = await browser.newContext({
      userAgent: UA,
      locale: 'zh-CN',
      viewport: { width: 1280, height: 900 },
    });
    const page = await ctx.newPage();
    const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
    const status = resp ? resp.status() : 0;
    await page.waitForSelector('#js_content', { timeout: 20000 }).catch(() => {});
    const has = await page.evaluate(() => !!document.getElementById('js_content'));
    if (!has) {
      const title = await page.title().catch(() => '');
      console.error(`ERROR: #js_content not found (status=${status}, title="${title}").`);
      console.error('可能原因：文章被删除/需验证/风控拦截。可改用 ai-agent-gui 的 Firefox 登录态流程（skill: ai-agent-gui）。');
      process.exit(3);
    }
    let containers = 0;
    for (let i = 0; i < 30; i++) {
      containers = await page.evaluate(() => document.querySelectorAll('[data-owc-math]').length);
      if (containers > 0) break;
      await page.waitForTimeout(500);
    }
    const res = await page.evaluate(convert);
    const b64 = await page.evaluate('window.__wx.b64');
    fs.writeFileSync(outHtml, Buffer.from(b64, 'base64'));
    if (outMeta) fs.writeFileSync(outMeta, JSON.stringify(res.meta, null, 2));
    console.log(JSON.stringify({ status, containers, converted: res.converted, htmlBytes: fs.statSync(outHtml).size }));
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error('ERROR:', e.message);
  process.exit(1);
});
