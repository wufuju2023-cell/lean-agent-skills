---
name: wx-article-to-md
description: 'Convert a WeChat 公众号 article (mp.weixin.qq.com/s/...) into a Markdown file with complete LaTeX formulas (inline $...$, display $$...$$) using a fixed headless-Chromium + MathML-rebuild + pandoc pipeline. Use when the user posts a WeChat article link and wants it copied out as Markdown / saved to a file / 转 md / with formulas preserved. Triggers: mp.weixin.qq.com, 公众号链接, 微信文章, 转Markdown, 公式源码, 保留公式.'
---

# wx-article-to-md（微信公众号 → Markdown，含公式源码）

## 一键命令（首选）

```bash
bash ~/.config/opencode/skills/wx-article-to-md/scripts/wx2md.sh "<url>" ["/path/out.md"]
```

- 输入：任意 `https://mp.weixin.qq.com/s/...` 公开文章链接（无需登录态）。
- 不传输出路径时写到 `$PWD/<文章标题>.md`；**建议显式指定路径**（例如用户常用 `~/wx-articles/`）。
- 单篇耗时约 10–40s，< 240s，可直接同步执行；批量时逐条循环跑。
- 成功后脚本输出 `OK <path>` 与公式统计。agent 收尾：向用户报告文件路径、行内/行间公式数，并提醒公式是 `$...$` / `$$...$$` 源码，可直接在 Obsidian/Typora/KaTeX/MathJax 渲染。

批量示例：

```bash
for u in "URL1" "URL2"; do bash .../wx2md.sh "$u" ~/wx-articles/; done
```

（第二条参数若是目录会报错——批量时逐个传目标文件路径，或先 `cd` 到目标目录再跑。）

## 固定流程（已全部脚本化，不要手写替代流程）

1. `scripts/fetch_page.js`：Playwright headless Chromium 打开文章，等 `#js_content`，轮询 `[data-owc-math]`，页内注入 `scripts/convert.js`；
2. `scripts/convert.js`：把每个 MathJax v3 公式 SVG（`g[data-mml-node]` 树 + `data-c` 字形码点）重建成标准 MathML；同时清理 DOM（懒加载图 `data-src`→`src`、剥属性、span 解包、去脚本/广告）；结果 base64 回传；
3. `pandoc -f html -t markdown --wrap=none --lua-filter=scripts/unwrap.lua`：MathML 自动转 LaTeX，Div 解包不留 `:::` 围栏；
4. `scripts/postprocess.py`：清残余（空 `\operatorname{}`、图片属性块、孤立 `\` 行、多余空行），写入 YAML frontmatter（title/account/date/source）+ `# 标题`；
5. `wx2md.sh` 末尾自动验收：pandoc 重新解析，统计 `math inline/display`，检查无降级块 `]{.math`。

## 验收标准

- 输出含 `formulas: N inline / M display` 且无 `[WARN: fallback blocks present]`；
- 文件以 YAML frontmatter 开头，正文含 `# 标题`；
- 公式均为 `$...$` / `$$...$$`。

## 依赖

- 系统：`node`、`pandoc`、`python3`（本地环境已具备）。
- Playwright 解析顺序：`$WX2MD_PLAYWRIGHT` → 本 skill `scripts/node_modules/playwright` → `~/.config/opencode/skills-disabled/playwright-web-headless-search/scripts/node_modules/playwright`。
- 浏览器缺失（报 browser launch error）时：
  `cd ~/.config/opencode/skills-disabled/playwright-web-headless-search/scripts && npx playwright install chromium`（可重复运行续传）。

## Firefox + BiDi 通道（风控时的备选）

headless Chromium 被微信判定为“环境异常”（退出码 3、标题`微信公众平台`）时，用本地环境真实 Firefox + WebDriver BiDi：

```bash
bash scripts/wx2md_ff.sh "<url>" "/path/out.md"
```

- 复用 agentgui 已启动的 Firefox（`ws://127.0.0.1:9222`，profile `~/agentgui-workspace/ffprofile`）；
  端点不通时先 `$B web launch`（见 `ai-agent-gui` skill）。
- `scripts/fetch_firefox.py`：建页 → 等 `#js_content` → 注入 `convert_formula.js` → 取 base64 HTML + 公式表。
- `convert_formula.js`：在 `convert.js` 基础上**额外读取 mdnice 公式的 `data-formula` 原始 LaTeX**（这类文章没有 `data-owc-math`）；
  公式先换占位符 `WXMATHTOKEN<i>END`，避免被 DOM 清理破坏。
- `formula_fix.py`：pandoc 之后把占位符回填成 `$...$` / `$$...$$`。
- 注意：`data-formula` 是作者原文 LaTeX，比 SVG 反推更准；个别文章本身带编辑器残留（`=""`），需人工按上下文修。

## 故障排查

- **退出码 3**（拿不到 `#js_content`）：文章被删除 / 风控 / 要求验证。改用上面的 Firefox + BiDi 通道，或 `ai-agent-gui` 手工打开页面后页内注入 `convert.js`，再走同一条 pandoc + postprocess 管道。
- **公式数为 0 但正文有公式**：该文来自 mdnice，公式在 `span[data-formula]` 里（不是 `data-owc-math`），用 `wx2md_ff.sh`。
- **公式数为 0**：该文章本来没有公式（纯文字），正常。
- **公式还原差异**（原文不存 TeX，属等价重建，非 bug）：`\mathbf/\mathrm` 等字形变体可能丢失；公式编号保留为矩阵末列 `\text{(1)}`；stretchy 花括号近似为 `\underbrace/\overbrace`；`\lbrack\rbrack` 属正常输出。
- **文章结构变更**（不再有 `data-owc-math`/`data-mml-node`）：更新 `scripts/convert.js` 的核心（`tokenText` 与 `mml()`），并用下方基线文章回归。

## 回归基线

样例文章：`https://mp.weixin.qq.com/s/jDoO4jfm1tZNqbtoffgyOw`
（TRPO 长文）→ 预期 `403 inline / 136 display`、0 fallback、与 Edge 路径产物 md5 一致。
