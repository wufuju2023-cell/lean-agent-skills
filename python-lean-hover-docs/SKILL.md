---
name: python-lean-hover-docs
description: 「python-lean-悬停文档写法」——为 Python/Lean 源码加"零基础悬停文档"（nvim 悬停键 K）的完整方法论与工具链：本地 typings stubs 遮蔽（pyrightconfig.stubPath）+ 官方文档 backfill（防遮蔽丢官方内容）+ 中文讲解只追加不覆盖；覆盖 nvim+basedpyright 与 LmcStudy/.olean 两条悬停通道；附 hover 查询器、符号定位器、双坐标计算与 stub 注入构建器（scripts/）及实测坑位清单。当任务涉及"给源码写悬停讲解/零基础 docstring/教学版源码"、"stubPath/typings/basedpyright 悬停"、"python-lean-悬停"时使用。触发词：悬停文档、hover 文档、零基础 docstring、教学版源码、typings、stubPath、basedpyright、nvim K、python-lean-悬停、lmc-study-edition。
---

# python-lean-悬停文档写法（python-lean-hover-docs）

给"读代码的人"提供**零基础、可悬停（nvim 按 `K`）**的中文讲解。两条悬停通道：

- **Python**：nvim + basedpyright；`K` = `vim.lsp.buf.hover()`；机制 = `typings/` 教学存根遮蔽 + 源码 docstring 追加。
- **Lean**：doc comment `/-- … -/` 随定义编译进 `.olean`，悬停/跳转跨文件生效（§7）。

适用于"零基础教学版源码"（例：`lmc-study-edition`、`python-learning`）——**不改逻辑，只加讲解**；官方内容只追加、不覆盖。

## 0. 仓库骨架（第一步就搭好）

```
仓库根/
├─ .git                        ← nvim 认根必需（用户的 root_markers 里有 .git）
├─ pyrightconfig.json          ← {"stubPath": "typings", "typeCheckingMode": "basic"}
├─ typings/                    ← 教学存根（构建产物，提交进 git，可幂等重建）
├─ study-tools/
│   ├─ hover_texts.py          ← 教学文案注册表（(模块, 符号) → 文本）
│   ├─ find_symbols.py         ← 先定位：符号真身在哪个 .pyi / 类 / 重载数（注册键按它写）
│   ├─ build_typings.py        ← 生成 typings/：完整复制 typeshed + backfill + 追加
│   ├─ hover_client.py         ← 命令行复现 K（直接问 LSP 要 hover 文本）
│   ├─ hover_positions.py      ← 一次算两套坐标（hover_client=字符列、nvim=字节列）
│   ├─ check_nvim_hover.sh     ← headless nvim 实测 K 的浮窗内容
│   └─ nvim_hover_check.lua
└─ 源码（docstring 追加式增强）
```

## 1. 已验证的机制事实（2026-10；basedpyright 1.40.2 / nvim 0.12.6 / Python 3.14；this machine）

1. `stubPath` 下的本地 stub **能遮蔽标准库与第三方模块**（实测：伪造签名出现在 hover 里）。
2. **basedpyright 默认会给标准库补"运行时文档"**（例：`os.getenv` 的英文文档来自运行时 `os.py`）。
   ⇒ 遮蔽一个模块后，stub 里没有的内容会消失 ⇒ **必须 backfill**：对 stub 里缺 docstring 的
   函数/类，从 Python 运行时取 `inspect.cleandoc(obj.__doc__)` 补回。
3. **追加式**：官方文档保留原文，中文写在其下方（`官方 + "\n\n" + 我们的`）。这是硬性要求。
4. `typeshedPaths`（整体替换 typeshed）**在 basedpyright 里是未知配置项**——此路不通，别试。
5. **常量没有 docstring 通道**（`subprocess.PIPE`、`os.O_NONBLOCK`、`fcntl.F_GETFL`…）：stub 里
   变量挂不上文档。讲解就近写在使用处的函数/类 docstring，或主题课程模块。
6. nvim 的 LSP 认根靠用户 init.lua 的 `root_markers`（LmcStudy 机器上为
   `{ 'pyproject.toml', '.git' }`）——**`pyrightconfig.json` 本身不在其中**。仓库有 `.git`
   （或 `pyproject.toml`）即可；文件必须在仓库内打开。
7. **悬停文本的形态 = 客户端能力声明 × 浮窗是否渲染 markdown**（2026-10-12 复核；nvim 0.12.6 /
   basedpyright 1.40.2；this machine）：
   - nvim 默认声明 hover 支持 markdown（`contentFormat = {"markdown","plaintext"}`）→ basedpyright
     返回 markdown 转义版（`_`→`\_`、缩进→`&nbsp;`、签名带代码围栏、行尾两空格硬换行）；
   - 用户 init.lua 若 `syntax off`（纯黑白配置的常见选择；等价条件 `vim.g.syntax_on == nil`），
     nvim 0.12 的 `open_floating_preview` 不走 markdown 渲染分支（不 conceal）→ 转义**原样显示**——
     即 §5.20 的坑与其一处 capabilities 修法；
   - 修好后（只声明 plaintext）：服务端直接给纯文本，裸写的 `_`、`\n`、缩进全部原样，
     `hover_client.py`（空 capabilities）的输出与真实 K **逐字一致**；
   - 风格结论不变（§3）：不包裹、不用 `**`、不用反引号——纯文本下它们会**字面**显示。
8. **re-export 可以穿两层**：`os.path.isdir / isfile` 的真身在 `genericpath.pyi`、`os.path.join`
   在 `posixpath.pyi`（`os/path.pyi` 只是转口）；`io.StringIO` 的真身在 `_io.pyi`。注册键要写在
   **真身模块**（§5.10 的 `_queue` 同理）——先 `find_symbols.py` 定位，别凭直觉。
9. **重载会产生多份注入**：`open` 有 7 个 `def`、`listdir`/`join` 各 3 个——build 对每个 def 注入
   同一段文案（可接受；命中任一重载都能看到）。另外遮蔽会触发**大规模 backfill**（实例：5 个模块
   共 279 处注入、`typings/` 约 1.3 万行，其中教学文案只有几十处）——选 MODULES 时对体积有预期
   （2026-10-12 追补：`multiprocessing` 一个包即 185 处注入、`typings/` +160KB；加新 MODULES 前先
   跑 `build_typings.py --dry-run` 看注入数）。

## 2. Python 侧标准流程

1. **建仓库**：快照源码 → `git init` → `git commit` 基线（让后续 diff 都是"纯增量"）。
   只 stage 自己动的路径（别 `git add -A` 卷进用户的 WIP，见 §5.17）。
2. **搭骨架**：`pyrightconfig.json` + `study-tools/` 七件套（§0）。
3. **定位符号真身**：`python3 study-tools/find_symbols.py <符号…>` —— 拿到建议注册键与重载数，
   别凭直觉写键（写错是静默跳过，见 §5.12）。
4. **写教学文案**：在 `hover_texts.py` 注册 `(模块, 符号) → 文本`（四段式，见 §3）。
5. **改源码 docstring**：已存在的**保留并追加**；没有的补上（只动 docstring，逻辑零改动）。
   改完 `diff` 审计：只允许新增行，不允许动代码/注释行。
6. **构建存根**：`python3 study-tools/build_typings.py`（幂等；自带写盘前语法自检 + 重叠检测）。
   把 "注册了但 stub 里没找到符号" 的 warning 当 error 处理。
7. **验证**：
   - `hover_positions.py` 生成两套坐标（字符列给 hover_client、字节列给 nvim，见 §5.13）；
   - `hover_client.py` 抽查（官方文本仍在 + 中文追加可见）；
   - `check_nvim_hover.sh` 实测浮窗（= 用户按 K 的真实效果）；
   - `basedpyright` 对源码跑一遍（对比改造前后诊断，确保 0 新增）。

## 3. 写作规范（悬停可读性）

- **四段式**：【一句话】是什么 →【从零】原理/背景 →【本项目】在代码里用在哪 →（按需）【延伸】。
- **不加任何包裹**（2026-10 起）：标识符、代码片段直接裸写（如 `class`、`self.proc`、`os.listdir`）；按 §5.20 声明 plaintext 后文本按字面显示（`_`、`\n` 恒不转义，§1.7），包裹只会干扰阅读。
- **不要用 `**加粗**`**：悬停是纯文本（§1.7），`*` 会原样显示成噪声；强调用「」或句子本身。
- **中文文案**，但 API 名/参数保持英文原样。
- **就近原则**：常量讲解放在使用它的函数 docstring（如 `session.py` 的 `__init__` 讲
  `O_NONBLOCK` 的用途）。
- 长文不进悬停：悬停里给 TL;DR + 跳转（`lmc/study/` 主题模块 / md 文档）。
- **绝不编造**：不确定的行为先 `python3 -m pydoc`、`man`、真源码核对再写。

## 4. 工具脚本（skill scripts/ 与仓库 study-tools/ 同源）

```bash
# 定位符号真身（写 hover_texts 注册键前必跑；输出含建议注册键与重载数）
python3 study-tools/find_symbols.py listdir isdir StringIO.readline

# 生成 typings/（完整复制 typeshed + 官方 backfill + 中文追加；幂等）
python3 study-tools/build_typings.py [--dry-run]

# 两套坐标一次算好：hover_client 用字符列、nvim K 用字节列
python3 study-tools/hover_positions.py lmc/session.py "sorted(os.listdir(path))" --token listdir

# 命令行复现 K（行/列从 0 起；root 决定读哪个 pyrightconfig.json）
python3 study-tools/hover_client.py basedpyright-langserver lmc/session.py 76 25 .

# 真实 nvim 浮窗实测（行/列从 1 起、列是字节列；用用户自己的 nvim 配置）
bash study-tools/check_nvim_hover.sh lmc/session.py 77 26
```

输出即悬停浮窗里的原始文本（形态取决于 §1.7 的能力声明；按 §5.20 声明 plaintext 后与真实 K 逐字一致）；用它做"官方还在 + 中文追加"的断言（可写进 CI/回归脚本）。

## 5. 坑位清单（全部实测踩过；1–11 首轮，12–19 为 2026-10-11 增补，20 为 2026-10-12 增补）

1. **误以为 typeshed 无文档**：basedpyright 会补运行时文档——不 backfill 就是"覆盖"。
2. **多行签名收尾行 `) -> T: ...`**：注入只能拼接行尾的 `: ...`，**不能整行替换**（否则
   `) -> T:` 被删、文件损坏）。写盘前必须 `ast.parse` 自检。
3. **单文件模块运行时名**：`subprocess.pyi → subprocess`（写成 `subprocess.subprocess` 会
   静默 backfill 失败）；目录模块：`os/__init__.pyi → os`、`json/decoder.pyi → json.decoder`。
4. **编辑范围重叠**：外层类"插在首条语句之前"会与首条语句自身的编辑踩同一行（Event 类事故：
   两层文字互相穿插）。修法：外层插入改为**头部行之后**；再加**重叠检测**兜底（重叠则回滚报错）。
5. **反斜杠字面量**：官方文档含 `\n`、`\uXXXX` 等 → 写入时 `replace("\\", "\\\\")`，
   否则触发转义解析破坏语法。
6. **CRLF 行尾**：bundled typeshed 是 CRLF → 读时 `replace("\r\n","\n")` 归一化，
   写时 `write_text(..., newline=eol)` 保留原样（否则全文件 diff 噪音）。
7. **四连引号**：doc 以 `"` 结尾时单行形式 `"""…""""` 出歧义 → 只对"短 + 无换行 +
   不以 `"` 结尾"的 doc 用单行形式。
8. **nvim 完全不认根**：根因是 `root_markers` 不含 `pyrightconfig.json`；`git init` 立刻解决。
9. **常量无通道**（§1.5）：别在 stub 里硬塞。
10. **`queue.Empty` 这类 re-export**：真身在 `_queue`——教学注册到真身模块
    （`("_queue","Empty")`），hover 穿透 import 显示它。
11. **类悬停优先显示 `__init__` 的 docstring**（实测 Popen/Thread：类文档里写了却不出）。
    修法：类教学**派生作用于 `__init__`**（源码文档或 backfill 出来的运行时文档，处理逻辑
    要基于"注入后"的文档而不是源码原文）；`__init__` 两边都没有官方文档就不动
    （避免把它"加出文档"后挤掉类文档、反而丢官方内容）。Queue 走类文档、Popen/Thread
    走 `__init__` 文档——两条路都要覆盖。
12. **注册键的"户籍"陷阱**（§1.8 实测细节）：`os.path.isdir/isfile` → `genericpath.pyi`；
    `os.path.join` → `posixpath.pyi`；`io.StringIO` → `_io.pyi`。写错键不报错、只在 build 输出里
    留一条 "注册了但 stub 里没找到符号" 的 warning——**把它当 error 处理**；先跑 `find_symbols.py`。
13. **两套坐标**：LSP（hover_client）列 = 字符数（UTF-16 码元）；nvim 光标列 = **字节数**。
    行首有中文时差异巨大（实测同一位置 35 vs 55），用错会"未找到浮窗"或点到隔壁符号
    （实测点到 `raw` 而不是 `strip`）。用 `hover_positions.py` 一次生成两套坐标。
14. **`_io` 里 `readline` 有 4 个定义点**（`_IOBase`×2、`_TextIOBase`、`TextIOWrapper`）：
    真实文件对象注册 `("_io","TextIOWrapper.readline")`，内存流（StringIO）注册
    `("_io","_TextIOBase.readline")`（继承链命中；两处共用一个文案变量即可）。
15. **重载与 backfill 的体量**（§1.9）：`open`×7 等会重复注入；backfill 使注入总数远大于教学条目
    （5 模块实例：279 处、约 1.3 万行生成物）。这是机制代价、不是故障；选 MODULES 时接受它。
16. **配套 tag 体系仓库**（stacks-project 风格，如 `python-learning`）：`validate_tags.py` 要求每个
    `.py` **恰好一个** `【源代码｜F-…】` 标签——文件头"相关"引用要写成 `【F-…】`（不带 `源代码｜`
    前缀），否则被判 "multiple file tags"；新增 `.py/.sh` 先登记 filekey、再在文件头加标签。
17. **git 暂存纪律**：别图省事 `git add -A`——会把用户正在写的新文件卷进你的提交（实测：空文件
    `13.4-….py` 被误提交）。只 stage 自己动的路径；已提交错则 `git rm --cached <path>` +
    `git commit --amend`（`git restore --staged` 对"新文件已在 HEAD 里"的场景无效）。
18. **nvim K 实测起手约 27 秒**：`nvim_hover_check.lua` 先等 `HOVER_WAIT_MS`（默认 18s）再 hover、
    再等 9s 收浮窗；慢机器调 `HOVER_TIMEOUT`/`HOVER_WAIT_MS`。失败时先查坐标（§5.13），
    再查 LSP 是否认根（§5.8）。
19. **浮窗文本没有"固定形态"**（2026-10-12 修正旧结论）：是否出现 `\_`/`&nbsp;`/`\*\*` 取决于 §1.7 的
    「客户端能力声明 × 是否渲染 markdown」——按 §5.20 声明 plaintext 后一切按字面显示、不做任何转义。
    风格结论不变：什么都不包 + 「」强调 +【】分段；不要 `**`、不要反引号。
20. **`syntax off` × markdown 能力声明 = 转义泄漏**（2026-10-12 实测修复；症状：K 浮窗出现
    `os.\_exit`、`&nbsp;&nbsp;&nbsp;&nbsp;`、代码围栏与行尾空格等字面量）。根因链：
    ① nvim 默认向服务端声明 hover 支持 markdown（`contentFormat = {"markdown","plaintext"}`）；
    ② 用户 `syntax off`（纯黑白配置的常见选择）→ 浮窗不渲染 markdown、不 conceal（§1.7）；
    ③ basedpyright 按 markdown 转义返回（`_`→`\_`、缩进→`&nbsp;`、行尾两空格硬换行），原样露出。
    旁证：`hover_client.py`（空 capabilities）与真实 K 输出不一致，本身就指向"能力声明差异"。
    修法（用户 `init.lua`，一处 capabilities 增量；`vim.lsp.config` 解析与 `lsp.start` 均为深合并）：
        vim.lsp.config('basedpyright', {
          capabilities = { textDocument = { hover = { contentFormat = { 'plaintext' } } } },
        })
    验证：headless 内用 `vim.lsp.buf_request(0, 'textDocument/hover', vim.lsp.util.make_position_params(0, 'utf-16'), cb)`
    打印**原始 payload**（应无 `\_`/`&nbsp;`），再确认浮窗 buffer 与它逐字一致；随后 `check_nvim_hover.sh` 抽查。
    改前备份 `cp init.lua init.lua.bak-<日期>`；别用"客户端正则还原转义"或"全局 `syntax on` 去渲染"当修法（hack / 破坏纯黑白风格）。

## 6. 检查清单（每次交付前）

- [ ] `find_symbols.py` 定位过每个注册键；`build_typings.py` 输出 0 error、
      0 个 "注册了但 stub 里没找到符号"
- [ ] 生成物全量 `ast.parse` 通过；`file` 确认行尾与源一致
- [ ] 抽 3 个符号用 `hover_client.py`（**字符列**）：官方内容**逐字还在** + 中文在下方
- [ ] 抽 2 个不同模块的符号用 `check_nvim_hover.sh`（**字节列**）：真实浮窗里有中文
- [ ] 真实浮窗 / `check_nvim_hover.sh` 输出中**无** `\_`、`&nbsp;` 等 markdown 转义字面量（否则见 §5.20）
- [ ] `diff` 审计源码：只新增 docstring 行
- [ ] 运行项目自检（例：`python3 -m pytest`、`python3 -c "import lmc.session"`）
- [ ] 配套 tag 仓库：`validate_tags.py` 无新增 errors/warnings（既有跨仓重复除外，见库内规范 §5）

## 7. Lean 侧（LmcStudy / `.olean` 通道）

- 机制：`/-- … -/` 文档注释随定义编译进 `.olean`；别的文件 `import` 后，悬停/`F12` 都带着文档。
- 载体：**读书文件旁边放"Notes"模块**（例：`LmcStudy/Notes/*.lean`，每个概念一个带文档注释的
  `def`），或在源码文件里直接给每个 `def`/`structure` 写 `/-- … -/`（同样**追加式**）。
- Lean 源码文件里某行的普通注释不会进悬停；**只有 doc comment 会**。
- 生效前提：文件属于一个已 `lake build` 的模块（改了要重建，悬停读的是 `.olean`）。
- 验证：`lake build <模块>` 通过 + 在读书文件里悬停/`Shift+F12` 看效果。
