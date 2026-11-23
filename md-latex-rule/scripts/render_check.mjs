#!/usr/bin/env node
// Reader-side render check: renders each .md in the *actual* Markdown Editor
// webview (Vditor + KaTeX, same assets/CSS as the installed extension) with
// headless Chromium, then inspects the produced DOM.
//
// Catches what the static checker cannot:
//   - KaTeX errors (formula rendered red / failed)
//   - raw LaTeX delimiters left visible (\(...\), \[...\], stray $)
//   - cross-line $...$ left visible as raw source (MULTILINE-INLINE; Vditor does not
//     red-error this, it just shows the source — the DOM walk alone missed it)
//   - math present in source but nothing rendered
//   - display formulas spilling out of the pane (horizontal overflow)
//   - leading --- parsed as YAML front matter (intro renders as a raw box)
//   - KaTeX/Vditor console warnings
//
// usage: node render_check.mjs <file.md> [more.md ...] [--width 800] [--shot]
// exit code: 0 = all PASS, 1 = at least one FAIL
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { createRequire } from 'node:module';

const HOME = os.homedir();

function findExtension() {
  const base = path.join(HOME, '.vscode-server/extensions');
  if (!fs.existsSync(base)) throw new Error('no ~/.vscode-server/extensions');
  const dirs = fs.readdirSync(base).filter(d => d.startsWith('zaaack.markdown-editor-')).sort();
  if (!dirs.length) throw new Error('zaaack.markdown-editor extension not installed');
  return path.join(base, dirs[dirs.length - 1]);
}

function findPlaywright() {
  const p = path.join(HOME, '.config/opencode/skills-disabled/playwright-web-headless-search/scripts/node_modules/playwright-core');
  if (!fs.existsSync(p)) throw new Error('playwright-core not found at ' + p);
  return p;
}

function findChromium() {
  const base = path.join(HOME, '.cache/ms-playwright');
  if (!fs.existsSync(base)) throw new Error('no ~/.cache/ms-playwright');
  const full = fs.readdirSync(base).filter(d => /^chromium-\d+$/.test(d)).sort((a, b) => parseInt(b.slice(9)) - parseInt(a.slice(9)));
  for (const d of full) {
    for (const sub of ['chrome-linux64/chrome', 'chrome-linux/chrome']) {
      const exe = path.join(base, d, sub);
      if (fs.existsSync(exe)) return exe;
    }
  }
  const shell = fs.readdirSync(base).filter(d => d.startsWith('chromium_headless_shell-')).sort().pop();
  if (shell) {
    for (const sub of ['chrome-linux/headless_shell', 'chrome-linux64/headless_shell']) {
      const exe = path.join(base, shell, sub);
      if (fs.existsSync(exe)) return exe;
    }
  }
  throw new Error('chromium executable not found under ~/.cache/ms-playwright');
}

function findCustomCss() {
  const base = process.env.USERPROFILE || '/data/c/Users';
  try {
    for (const u of fs.readdirSync(base)) {
      const s = path.join(base, u, 'AppData/Roaming/Code/User/settings.json');
      if (!fs.existsSync(s)) continue;
      try {
        const j = JSON.parse(fs.readFileSync(s, 'utf8'));
        if (j['markdown-editor.customCss']) return j['markdown-editor.customCss'];
      } catch { /* ignore malformed settings */ }
    }
  } catch { /* not WSL or no Windows drive */ }
  return '';
}

// ---------- static pre-checks ----------
function staticChecks(src) {
  const issues = [];
  const lines = src.split('\n');
  let inFence = false;
  let mathCount = 0;
  let displayOpen = false;
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i];
    if (l.trim().startsWith('```')) { inFence = !inFence; continue; }
    if (inFence) continue;
    if (/(?<!\\)\\\(/.test(l)) issues.push({ level: 'FAIL', code: 'PAREN-DELIMITER', line: i + 1, msg: '\\( ... \\) is not rendered by KaTeX/Vditor; convert to $ ... $' });
    if (/(?<!\\)\\\[/.test(l)) issues.push({ level: 'FAIL', code: 'BRACKET-DELIMITER', line: i + 1, msg: '\\[ ... \\] is not rendered by KaTeX/Vditor; convert to $$ ... $$' });
    // odd single $ on one line = an inline formula opened/left across lines.
    // Vditor does NOT show a KaTeX error for this: it leaves the raw $ ... $ source
    // visible (wrapped in a <pre>), so the DOM walk below is unreliable here.
    const singles = (l.replace(/\$\$[\s\S]*?\$\$/g, '').match(/(?<!\$)\$(?!\$)/g) || []).length;
    if (singles % 2 === 1) issues.push({ level: 'FAIL', code: 'MULTILINE-INLINE', line: i + 1, msg: 'odd single $ on this line: a cross-line $...$ is shown as raw source in Vditor (no KaTeX error); keep inline math on one line or promote it to $$...$$' });
    mathCount += (l.match(/\$(?!\$)[^$\n]+\$(?!\$)/g) || []).length;
    if (/^\s*\$\$.*\$\$\s*$/.test(l)) mathCount++;
    if (/^\s*\$\$\s*$/.test(l)) { displayOpen = !displayOpen; if (!displayOpen) mathCount++; }
  }
  if (lines[0] !== undefined && lines[0].trim() === '---') {
    issues.push({ level: 'WARN', code: 'FRONTMATTER', line: 1, msg: 'document starts with --- ; Vditor parses it as YAML front matter and renders the intro as a raw box (remove the leading --- or add a title above it)' });
  }
  return { issues, mathCount };
}

// ---------- webview harness ----------
const MIME = { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.png': 'image/png', '.svg': 'image/svg+xml', '.woff': 'font/woff', '.woff2': 'font/woff2', '.ttf': 'font/ttf', '.json': 'application/json', '.map': 'application/json', '.wasm': 'application/wasm' };

async function main() {
  const argv = process.argv.slice(2);
  const widthIdx = argv.indexOf('--width');
  const width = widthIdx >= 0 ? parseInt(argv[widthIdx + 1]) : 800;
  const shot = argv.includes('--shot');
  const files = argv.filter((a, i) => !a.startsWith('--') && !(widthIdx >= 0 && i === widthIdx + 1));
  if (!files.length) {
    console.error('usage: node render_check.mjs <file.md> [more.md ...] [--width 800] [--shot]');
    process.exit(2);
  }

  const EXT = findExtension();
  const customCss = findCustomCss();
  let injectedScripts = '';
  if (!argv.includes('--no-scripts')) {
    try {
      const extJs = fs.readFileSync(path.join(EXT, 'out/extension.js'), 'utf8');
      const grab = (name) => { const m = extJs.match(new RegExp('EditorPanel\\.' + name + ' = `([\\s\\S]*?)`;')); return m ? m[1] : ''; };
      injectedScripts = grab('lineNumberScript') + grab('focusModeScript');
    } catch { /* scripts optional */ }
  }
  const require = createRequire(import.meta.url);
  const { chromium } = require(findPlaywright());
  const exe = findChromium();

  const PORT = 3223 + (process.pid % 200);
  const TEST_HTML = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<base href="http://127.0.0.1:${PORT}/test/">
<style>#app{opacity:0}body[data-vmd-ready="1"][data-vmd-css-loaded="1"] #app{opacity:1}</style>
<link href="/media/dist/main.css" rel="stylesheet" onload="document.body.setAttribute('data-vmd-css-loaded','1')" onerror="document.body.setAttribute('data-vmd-css-loaded','1')">
<style>${customCss}</style>
<title>markdown editor</title>
</head>
<body>
<div id="app"></div>
<script>
window.__msgs = [];
window.acquireVsCodeApi = function () {
  return { postMessage: function (m) { window.__msgs.push(m); }, getState: function () {}, setState: function () {} };
};
</script>
<script src="/media/dist/main.js"></script>
${injectedScripts}
</body>
</html>`;

  const server = http.createServer((req, res) => {
    const urlPath = decodeURIComponent(req.url.split('?')[0]);
    if (urlPath === '/test/index.html' || urlPath === '/') {
      res.writeHead(200, { 'Content-Type': 'text/html' }); res.end(TEST_HTML); return;
    }
    const file = path.join(EXT, urlPath);
    if (!file.startsWith(EXT) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
      res.writeHead(404); res.end('not found'); return;
    }
    res.writeHead(200, { 'Content-Type': MIME[path.extname(file)] || 'application/octet-stream' });
    fs.createReadStream(file).pipe(res);
  });
  await new Promise(r => server.listen(PORT, '127.0.0.1', r));

  const browser = await chromium.launch({ executablePath: exe, headless: true });
  let failed = 0;

  for (const file of files) {
    const src = fs.readFileSync(file, 'utf8');
    const st = staticChecks(src);
    const issues = [...st.issues];

    const page = await browser.newPage({ viewport: { width, height: 900 } });
    const logs = [];
    page.on('console', m => { if (m.type() !== 'log') logs.push(m.type() + ': ' + m.text().slice(0, 200)); });
    page.on('pageerror', e => logs.push('pageerror: ' + e.message.slice(0, 200)));
    await page.goto('http://127.0.0.1:' + PORT + '/test/index.html', { waitUntil: 'load' });
    await page.waitForFunction(() => window.__msgs.some(m => m.command === 'ready'), null, { timeout: 15000 });
    const t0 = Date.now();
    await page.evaluate(c => {
      window.postMessage({ command: 'update', type: 'init', content: c, options: { useVscodeThemeColor: true, showLineNumbers: true, outline: { enable: false } }, theme: 'light' }, '*');
    }, src);
    let prev = -1, stable = 0, renderSec = null;
    while (Date.now() - t0 < 60000) {
      let n;
      try {
        n = await Promise.race([
          page.evaluate(() => document.querySelectorAll('.katex').length),
          new Promise((_, rej) => setTimeout(() => rej(new Error('blocked')), 8000))
        ]);
      } catch { n = -2; }
      if (n >= 0 && n === prev) { stable++; if (stable >= 2) { renderSec = (Date.now() - t0) / 1000; break; } }
      else stable = 0;
      prev = n;
      await page.waitForTimeout(500);
    }

    const r = await page.evaluate(() => {
      const reset = document.querySelector('.vditor-ir .vditor-reset');
      const errors = [
        ...[...document.querySelectorAll('.katex-error')].map(e => (e.getAttribute('title') || e.textContent).replace(/\s+/g, ' ').slice(0, 140)),
        ...[...document.querySelectorAll('.vditor-reset--error')].filter(e => e.textContent.trim().length > 0).map(e => (e.textContent.replace(/\s+/g, ' ').trim().slice(0, 140) + ' [math: ' + (e.getAttribute('data-math') || '').replace(/\s+/g, ' ').slice(0, 60) + ']'))
      ];
      const raw = [];
      if (reset) {
        const w = document.createTreeWalker(reset, NodeFilter.SHOW_TEXT);
        let n;
        while ((n = w.nextNode())) {
          const t = n.textContent;
          if (!/[$]|\\\(|\\\[/.test(t)) continue;
          const p = n.parentElement;
          if (!p) continue;
          // NOTE: do NOT skip a generic <pre> here. Vditor wraps *unparsed* paragraph
          // text (e.g. a cross-line $...$ that failed to parse) in a <pre>, and that is
          // exactly the failure we want to report. Real fenced code always has a
          // <code> ancestor (either the hidden marker pre or the .vditor-ir__preview one).
          if (p.closest('.katex') || p.closest('.vditor-ir__marker') || p.closest('[data-type$="-open-marker"]') || p.closest('code')) continue;
          const rr = p.getBoundingClientRect();
          if (rr.width === 0 && rr.height === 0) continue;
          raw.push(t.replace(/\s+/g, ' ').trim().slice(0, 90));
        }
      }
      const spills = [];
      document.querySelectorAll('.katex-display, pre, .vditor-ir__preview').forEach(el => {
        const cs = getComputedStyle(el);
        if (el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 1 && cs.overflowX === 'visible') {
          spills.push({ tag: el.tagName, cw: el.clientWidth, sw: el.scrollWidth, text: el.textContent.replace(/\s+/g, ' ').slice(0, 60) });
        }
      });
      const firstBlock = reset && reset.firstElementChild ? reset.firstElementChild.textContent.replace(/\s+/g, ' ').trim().slice(0, 60) : '';
      return {
        katex: document.querySelectorAll('.katex').length,
        displays: document.querySelectorAll('.katex-display').length,
        errors, raw, spills, firstBlock
      };
    });
    if (shot) {
      const shotDir = path.join(os.tmpdir(), 'md-render-check');
      fs.mkdirSync(shotDir, { recursive: true });
      const shotPath = path.join(shotDir, path.basename(file).replace(/\.md$/, '') + '.render.png');
      await page.screenshot({ path: shotPath, clip: { x: 0, y: 0, width, height: 700 } });
      console.log('  shot: ' + shotPath);
    }
    await page.close();

    for (const e of r.errors) issues.push({ level: 'FAIL', code: 'KATEX-ERROR', msg: e });
    for (const t of r.raw) issues.push({ level: 'FAIL', code: 'RAW-DELIMITER', msg: 'rendered as plain text: ' + t });
    for (const s of r.spills) issues.push({ level: 'FAIL', code: 'OVERFLOW', msg: `${s.tag} scrolls outside its box (${s.sw} > ${s.cw}): ${s.text}` });
    if (st.mathCount > 0 && r.katex === 0) issues.push({ level: 'FAIL', code: 'NO-MATH', msg: `source has ${st.mathCount} math span(s) but 0 KaTeX nodes rendered` });
    if (r.firstBlock.startsWith('---')) issues.push({ level: 'FAIL', code: 'FRONTMATTER-RENDERED', msg: 'first rendered block starts with --- (front matter box): ' + r.firstBlock });
    for (const l of logs) if (!l.includes('404')) issues.push({ level: 'WARN', code: 'CONSOLE', msg: l });

    if (renderSec === null) issues.push({ level: 'FAIL', code: 'SLOW-RENDER', msg: 'render did not stabilize within 60s (renderer blocked/too slow)' });
    const fails = issues.filter(i => i.level === 'FAIL');
    if (fails.length) failed++;
    const status = fails.length ? 'FAIL' : 'PASS';
    console.log(`${status}  ${file}  (katex=${r.katex}, displays=${r.displays}, math-in-source=${st.mathCount}, render=${renderSec === null ? 'TIMEOUT' : renderSec.toFixed(1) + 's'})`);
    for (const i of issues) console.log(`  - ${i.level} ${i.code}${i.line ? ' L' + i.line : ''}: ${i.msg}`);
  }

  await browser.close();
  server.close();
  console.log(failed ? `\nREADER CHECK FAILED: ${failed}/${files.length} file(s)` : `\nREADER CHECK OK: all ${files.length} file(s) rendered cleanly.`);
  process.exit(failed ? 1 : 0);
}

main().catch(e => { console.error('render_check error:', e.message); process.exit(2); });
