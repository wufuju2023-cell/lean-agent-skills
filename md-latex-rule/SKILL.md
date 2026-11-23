---
name: md-latex-rule
description: 编写 Markdown 文档时选择数学公式写法并避免渲染失败：**首选纯文本公式**（Unicode 符号 + 代码段，任何渲染器原样显示），仅当纯文本无法表达（大分式/矩阵/对齐推导/cases 等）才用 LaTeX（GitHub GFM/KaTeX $..$ 与 $$..$$ 规则、本地 VSCode/Typora 兼容）。当写 md/README/spec/文档中的公式时使用；当发现网页与本地渲染不一致时使用。
---

# MD + LaTeX 数学渲染规则

权威规则集。**先读下节"纯文本公式优先"策略**，再按需查阅渲染规则；凡最终用到 `$...$`/`$$...$$` 的 Markdown，提交前用两个脚本校验：静态 [scripts/check_md_math.mjs](scripts/check_md_math.mjs) + 读者侧 [scripts/render_check.mjs](scripts/render_check.mjs)（真实 Vditor/KaTeX webview 渲染）。

## ★★ 首选策略：纯文本公式优先（2026-10-05 修订）

在需要"正规排版"的 .md 里，**默认写纯文本公式**（Unicode 符号 + 代码段/行内代码），
**只有纯文本表达不了的才用 LaTeX**；用 LaTeX 时也尽量保持朴素、与纯文本写法一一对应。

### 写法（块级用 text 代码围栏，行内用反引号）

```text
L_pol = -(1/T) Σₜ log πθ(a*ₜ | s, a*₋ₜ)
∇L    = (-r + 2βΔ) · ∇log πθ(a | s)
θ     ← θ + η·(r - 2βΔ) · ∇log πθ(a | s)
```

- 符号面：希腊字母 `π θ β Δ η γ Σ ∇ ∂`、关系 `≤ ≥ ≠ ≈ → ← ∈ ∀ ∃`、
  上下标 `ₜ ₙ ₀ ₁ ₂ ᵀ ⁻¹ ²
  ⁿ`(少用x_1这样子来表示上下标）、小分式 `a/b`、求和 `Σₜ`；
- 公式放代码里 → 原样显示、不依赖渲染器、可直接复制进代码、**永不渲染失败**；
- 表格 / 列表 / 引用里同样用行内代码，天然支持。

### 决策表：什么时候必须用 LaTeX

| 表达式 | 纯文本 | LaTeX 兜底 |
| --- | --- | --- |
| 行内变量、上下标 | ✅ `πθ(a\|s)`、`xₜ` | — |
| 简单关系 / 集合 | ✅ `x ≤ y`、`a → b`、`A ∈ B` | — |
| 小分式 | ✅ `a/b` | — |
| 简单求和 / 连乘 | ✅ `Σₜ xₜ`、`∏ᵢ xᵢ` | 上下限需要堆叠时 |
| 大分式堆叠 / 连分数 | ❌ | ✅ `\frac{}{}` |
| 带上下限的 ∑/∏/∫（上下标堆叠） | ❌ | ✅ |
| 矩阵 / 方程组 | ❌ | ✅ `\begin{pmatrix}` / `\begin{cases}` |
| 多行对齐推导 | ❌ | ✅ `\begin{aligned}` |
| 大括号分组、大型结构 | ❌ | ✅ `\left\{ ... \right.` |

仅当出现大分式/矩阵/对齐这类结构才值得动用 LaTeX，例如：

$$
\frac{\partial L}{\partial \theta}
  = -\frac{1}{T}\sum_{t=1}^{T}\nabla_\theta \log \pi_\theta(a_t \mid s)
$$

其余场景一律回到纯文本（`L = -(1/T) Σₜ ∇log πθ(aₜ | s)`）。

### 规则

1. **能用纯文本就用纯文本**；不要为了"好看"把小公式写成 `$...$`；
2. LaTeX 兜底时，§1–§6 的渲染规则全部照旧（空行、独占行、KaTeX 子集、行内单行…）；
3. **LaTeX 内部也尽量朴素**：行内小分式写 `a/b` 而不是 `\frac{a}{b}`；关系用 `\le \ge \in \to`；
   不引入纯文本版没有的结构；
4. 校验脚本（§5）只覆盖 LaTeX 公式；纯文本公式不适用（但要保证 Unicode 符号与上下标正确）；
5. 既有文档迁移：简单公式逐步从 `$...$` 降级为纯文本，复杂公式保留 LaTeX。

## 0. 一句话破坏矩阵

GitHub/KaTeX 渲染失败 = 公式被原样显示为 `$ ... $` 源码。六大死因：

1. **块级未隔离段落**：`$$` 前后缺空行
2. **块级缩进**：公式行任何行首空格
3. **行内跨行**：`... $x =` 换行 `y$ ...` —— 在 Vditor/zaaack 插件里**不报 KaTeX 红错**：Vditor 把整段当无法解析的源码塞进 `<pre>` 原样显示 `$ … $`（公式 0 渲染、无任何报错），六个死因里最隐蔽；拼接后 KaTeX 静态解析反而通过，必须靠"单行 odd `$`"检查拦截（`UNCLOSED-DOLLAR` / `MULTILINE-INLINE`）
4. **`$` 紧贴 ASCII 字母/数字**
5. **KaTeX 语法错**：`\text{}` 内裸 `_`、`\text{}` 内 `\}`、Unicode 数学符号、行内公式里用 `\tag{}`（`\tag` 只能出现在 `$$` 块级公式，行内会报 "\\tag works only in display equations"）
6. **分隔符用错**：写成 `\(...\)` / `\[...\]`（LLM 生成文档常见）→ KaTeX/Vditor/GFM 一律不渲染；且文档首行 `---` 会被 Vditor 当 YAML front matter，把引言渲染成生源码框

## 1. 行内公式 `$...$`

合法写法：

```markdown
均值记为 $\bar{x}$，方差 $\sigma^2$，注意 $n$ 与 $N$ 区别。
公式 $V_\phi(s)=\mathrm{MLP}(h(s))$ 见 §2。  ← 中文+标点紧邻 OK
"用量 $\approx$ 1B 参数"                        ← $ 后加空格再数字
```

**禁止**：

```markdown
错误: 参数量 $\approx$1B 与目标匹配          ← $ 后紧跟 1（ASCII 数字）→ 不渲染
错误: 前值 $x$next 继续                       ← $ 后紧跟 n（英文）→ 不渲染
错误:  开行 $x =                                        ← 跨行：下一行接内容 → Vditor 里原样显示为源码
       e^{y}$ 闭合
错误: 引号内 `$x$`（反引号代码段）没有公式效果  ← 代码段里写 $ 是文字，别在里面放公式
```

规则：关闭的 `$` 后一个字符若满足 `[0-9A-Za-z]` → 加空格；打开的 `$` 前一个字符若为 `[0-9A-Za-z]` → 加空格。公式永远单行（长公式改块级）。

## 2. 块级公式 `$$...$$`

**唯一合法形式**（空行 + 独占行 + 顶格）：

```markdown
正文解释……

$$
\mathcal{L} = -\mathbb{E}\log\pi_\theta(a\mid s)
$$

继续正文……
```

规则：
- 前后各 **1 个空行**（紧贴文字 = 不渲染）
- `$$` 独占一行（行内容只有 `$$` 或整行 `$$expr$$`），**整行零缩进**（列表项内的块要先结束列表，或改用 row 内 `$...$`）
- 跨行放公式体时用三行式（如上）；单小公式可 `$$expr$$` 独行，但前后仍须空行
- 禁止：列表 bullet 内直接嵌块公式（先空行终止列表，公式独立段后，再继续 bullet 或移出）。实测：缩进的 `$$` 在本插件**能**渲染，但 GitHub/GitLab GFM 不渲染，所以禁的是跨平台一致性，不是插件

## 3. KaTeX 兼容子集（GFM=GitHub 渲染器，支持 KaTeX 语法）

### ✓ 允许
- 常见环境：`\frac \sqrt \sum \prod \int`、`\begin{cases}\end{cases}`（仅块级）
- 大括号/字号：`\left( \right) \big[ \big] \{ \}`
- 关系：`\le \ge \ne \sim \approx \equiv \mid \Vert \propto \in \subset \subseteq \cup \cap \setminus \emptyset \mathbb{R}`
- 函数：`\mathrm{} \mathbf{} \mathbb{} \mathcal{} \operatorname{} \text{} \hat{} \bar{} \vec{}`
- 希腊/逻辑：`\alpha\beta\theta\pi \nabla \mathrm{KL} \log \exp \max \min \underbrace \text{...}`
- 模板（务必复制固定模板）：文本/提示词出现在 `\text{}` 内时，**仅限** 英文单词+空格。

### ✗ 禁区
| 写法 | 修复 |
|---|---|
| `\text{state_tactic_pairs}`（下划线） | `\text{state\_tactic\_pairs}` 或移出 text |
| `\text{proof found\}}`（text 内 `\}`） | `\{\, \text{proof found} \,\}` |
| `≤ ≥ ∈ × → ¬ ∧ ∴` 等 Unicode 符号在公式内 | `\le \ge \in \times \to \neg \wedge \therefore` |
| `<` 在公式内（可能被当 HTML 标签） | 用 `\lt` 或改文字 |
| 行内公式含 `&`、`##`、空行 | 不会渲染 |
| `\diamond \square \blacksquare` 等非 KaTeX 宏 | 不用 |
| 行内公式内 `\tag{n}`（编号） | `\tag` 仅支持 `$$` 块级（Vditor 会把整条公式渲染成红色 "KaTeX parse error: \tag works only in display equations"）；改为 `$$...\tag{n}$$` 独立块，或删掉 tag 用 `\quad\text{(n)}` |
| `\(...\)` / `\[...\]`（LaTeX 传统分隔符） | 改 `$...$` / `$$...$$`（Vditor/KaTeX/GFM 都不认前者） |
| 中文标点 `。` `）` `；` 留在数学模式内（`\text{}` 外） | 实测可渲染但触发 strict-mode `unicodeTextInMathMode` Console warn + 字体回退；移出公式，或整段包进 `\text{}`（块级公式结尾别在 `$$` 内写 `。`） |

### 中文与公式共存的写法
- `\text{输出}` 中文在 `\text{}` 内 KaTeX 支持；**更稳**做法：中文移出公式，只留英文 `\text{}`。实测：本插件 `\text{}` 内 CJK 正常渲染（英文更稳只是为跨渲染器）
- 公式紧邻中文标点（`，`、`（`）：允许，无需空格（中文非 ASCII 不触发破坏）
- 反例：中文标点在**数学模式内**（如 `$$ ... r_T = 0 \text{）}。$$` 的 `。`）→ 渲染成功但有 Console warn；把标点移出 `$...$`/`$$...$$` 即可清零

## 4. 表格 / 列表 / 引用内的公式

- **表格单元格**：只支持行内 `$...$`；块级 `$$` 必坏（改行内或把公式移到表格下方正文）
- **列表项**：行内 OK；块级公式先空行终止列表再独立段
- **引用块（`> `）**：行内 OK；块级 `$$` 不可靠 → 改行内
- **代码围栏（```）**：`$` 只是普通字符，不会有副作用，别期望渲染

## 5. 提交前校验（必须，两步都过）

**第 1 步：静态结构 + KaTeX 解析**

```bash
# 有 katex 最精确：
npm i katex --prefix /tmp/opencode/kx 2>/dev/null || true
node ~/.config/opencode/skills/md-latex-rule/scripts/check_md_math.mjs <file.md> [更多文件...]
# 无 katex 时脚本自动降级为“结构规则检查”（空行/缩进/跨行/紧贴/分隔符），同样能拦大部分真凶。
```

输出 `OK — all math parsed by KaTeX, 0 issues.`（或 `REAL REMAINING ISSUES: 0`）才算通过；`INDENTED`/`UNCLOSED`/`TOUCH`/`BLANK-PROBLEM`/`PAREN-DELIMITER`/`BRACKET-DELIMITER` 必须修后再提交。

**第 2 步：读者侧渲染校验（真实 webview，必跑）**

```bash
node ~/.config/opencode/skills/md-latex-rule/scripts/render_check.mjs <file.md> [更多文件...] [--width 800] [--shot]
```

输出 `READER CHECK OK` 才算通过。静态检查通过 ≠ 渲染正确（`\(...\)` 分隔符、front matter、溢出、跨行行内公式都拦不住）——详见 §6。
注意：render_check **内置**了一份静态检查（跨行 odd `$`、`\(...\)`、front matter），所以它现在也能独立拦到跨行行内公式（`MULTILINE-INLINE`），但 KaTeX 语法解析仍以第 1 步为准。

## 6. 读者侧渲染校验（render_check.mjs）

用无头 Chromium 打开与 VSCode 里 **zaaack Markdown Editor 完全相同的 webview**（同一份 Vditor/KaTeX 资源、同一 `markdown-editor.customCss`，并默认注入扩展自带的**行号脚本 + focus 模式脚本**，与真实打开一致），渲染完成后直接检查 DOM，把静态脚本看不见的问题现形：

- `KATEX-ERROR`：KaTeX 渲染失败（公式显示为红色错误）。同时捕获 `.katex-error` 与 Vditor 的 `.vditor-reset--error` 红字（后者曾漏检：行内 `\tag` 只产生 Vditor 错误 span，不产生 `.katex-error`）
- `MULTILINE-INLINE`：某行单 `$` 个数为奇数 = 行内公式跨行。Vditor 对此**不报 KaTeX 错**（源码原样显示，包在 `<pre>` 里），静态检查才能拦
- `RAW-DELIMITER`：`\(...\)`、`\[...\]`、漏渲染的 `$` 以纯文本出现（`\\[2pt]` 这类行距不算）。2026-09-20 修复：Vditor 给"解析失败的段落"套的 `<pre>` 不再被当成代码块跳过（真代码块必有 `<code>` 祖先）
- `NO-MATH`：源码里有公式但 0 个 KaTeX 节点（分隔符/结构错）
- `FRONTMATTER` / `FRONTMATTER-RENDERED`：首行 `---` 被当 YAML front matter，引言渲染成生源码框
- `OVERFLOW`：块级公式 `overflow-x: visible` 且超宽，横向溢出面板（可滚动的不算）
- `SLOW-RENDER`：60 秒内渲染未稳定——注入脚本死循环或渲染器被阻塞（曾用于定位行号脚本在 500+ 公式文档上把窗口卡死的问题）
- `CONSOLE`：KaTeX/Vditor 警告（如 Unicode 字符回退字体）

### 真实 webview 实测矩阵（2026-09-20 回归，探针 `scripts/render-regression-cases.md`）

| 写法 | 真实插件（zaaack + customCss）结果 | 处置 |
|---|---|---|
| 跨行行内 `$...$` | ❌ 原样显示 `$ … $`（Vditor 塞进 `<pre>`；KaTeX 节点 0；无红色报错） | 硬失败；保持单行或升为 `$$` |
| 列表项内缩进 `$$` | ⚠️ Vditor 能渲染；GitHub GFM 不渲染 | 仍禁止（跨平台） |
| `$$` 内中文标点 `。`/`）` | ⚠️ 渲染成功 + strict-mode Console warn | 标点移出或包 `\text{}` |
| `\text{}` 内 CJK | ✅ 正常 | 可用 |
| 行内公式紧邻中文标点 | ✅ 正常 | 可用 |
| 代码围栏内 `$` / `\(` | ✅ 字面量，不报 | 正常 |

前置条件（本地环境已满足，脚本自动探测，无需配置）：`~/.vscode-server/extensions/zaaack.markdown-editor-*`、`skills-disabled/playwright-web-headless-search` 里的 `playwright-core`、`~/.cache/ms-playwright/chromium-*`；VSCode `settings.json` 的 `customCss` 自动读取。

退出码：`0` 全部 PASS；`1` 至少一个 FAIL（明细逐条打印）。`--width` 默认 800（VS Code 常规面板宽）；`--shot` 把顶部截图存到 `/tmp/md-render-check/` 并打印路径；`--no-scripts` 跳过扩展脚本注入（纯 Vditor 渲染，用于区分文档问题 vs 扩展脚本问题）。

## 7. 渲染器上下文备忘

| 环境 | 支持 | 备注 |
|---|---|---|
| GitHub 网页（repo/README） | ✅ GFM Math (KaTeX) | 块级必须空行+顶格 |
| GitHub Pages（Jekyll 默认） | ⚠️ 需 mathjax 配置 | 建议在 README 注明或自行配置 |
| VSCode 预览默认 | ❌ | 装 "Markdown+Math" / "Markdown Preview Enhanced" |
| Typora | ✅ | `$$...$$` 独立段 |
| Jupyter Markdown | ✅ | 靠近 KaTeX 子集 |

遇到"我写的公式没渲染" → 先按 §0 六死因逐条对照，再依次跑 §5 的两个脚本。
