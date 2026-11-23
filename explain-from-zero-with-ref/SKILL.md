---
name: explain-from-zero-with-ref
description: 当用户贴一段 Lean 源码（或点名一个符号/文件）并要求「逐行逐块、从零讲、做真实验、写一套 .lean + .md、中文、自包含、放到某个路径」时使用：先判重与定位，再按「原文→拆块→排章→讲义→实验→引用→验收」产出可编译的教学工程，已有材料只引用不重写，引用必须是 nvim gF 可跳的绝对路径:行号。触发词：Explain-from-zero-with-ref、从零讲、逐行讲解、逐块拆、写一套教程、系列 md、配套实验、self contained、自包含、引用已有材料、gF 能跳、evalOmega、builtin_tactic、strict n-category、数学形式化。
---

# 从零讲解 + 引用已有材料（explain-from-zero-with-ref）

## 0. 这个技能解决什么

用户给两样东西：

1. **一段源码**（一个函数、一个命令、一个 attribute、一个文件），或一个明确符号；
2. **一套要求**：逐行 / 逐块、从零、做真实验、写 `.lean` + `.md` 系列、中文、自包含、放在某路径。

这时**不要只用聊天回答**。产出是一个**新的教学工程目录**：能编译、能复现、能从零读到原片段。

本技能是"生产"流程；只想问"这个词什么意思"时，用 `local-lean-source-code-explain`。

**语言硬约束：讲义、注释、回答正文一律中文；代码、类型签名、专有名词保留英文。**

---

## 1. 十条硬约束（从请求里抽出来，逐条验收）

| # | 约束 | 验收方式 |
|---|---|---|
| 1 | 中文 | 随机抽 3 个 `.md`，正文无成段英文 |
| 2 | 从零 | 每章开头假设读者只知道"函数/类型/命令行" |
| 3 | 逐行 / 逐块 | `PIECES.md` 覆盖原片段每一行，无遗漏 |
| 4 | 真实验 | 每个实验 `lake env lean` 退出码 0，输出写进 `out/` |
| 5 | `.lean` + `.md` 成对 | 每个 `ChNN_*.lean` 有同名 `ChNN.md` |
| 6 | 自包含 | 只读一章能懂"为什么 + 怎么跑 + 每个名字是什么"（§8） |
| 7 | 放指定路径 | 目录树符合 §10；不在 6 个参考根里乱写 |
| 8 | 不重复已有材料 | 已有内容用引用块 + 一句话桥接（§7） |
| 9 | 引用可 `gF` | 每条引用是独立一行的绝对路径:行号，`check-refs.sh` 全过 |
| 10 | 可中断续写 | `README.md` 有进度表，每章独立可编译 |

---

## 2. 第 0 步：判重（先看有没有现成的）

**永远先查，再动手。** 已有系列可能只要补几章。

```bash
# 1) 已有的 *-explain 工程
ls -la ~/lean-4.28-reap/*-explain/

# 2) 6 个参考根里是否已讲过这个主题
bash ~/.config/opencode/skills/local-lean-source-code-explain/scripts/lean-search.sh -F "<符号>"
```

6 个参考根（完整说明见 `local-lean-source-code-explain` 的 §1）：

1. `~/lean-4.28-reap/runtime/LmcStudy/`
2. `~/Lean-source-code-learning-to-know-reap/`
3. `~/lean-4.28-reap/command-walkthrough/`
4. `~/lean-4.28-reap/elab-walkthrough/`
5. `~/lean-4.28-reap/Lean-basic/`
6. `~/lean-4.28-reap/Lean-math-formalization/leinster-n-cat/lean/`

决策树：

| 情况 | 做法 |
|---|---|
| 已有完整系列，覆盖 ≥ 80% | **不新建**；补缺失章，README 里标明"增补" |
| 已有目录但为空（例：`Tactic-Omega-explain/`） | 直接用它，不要另起名字 |
| 已有系列但"不够自包含" | 在原目录加"从零"前置章，不复制旧章 |
| 完全没有 | 新建 `~/lean-4.28-reap/<Topic>-explain/` |

路径规则：

- **用户指定了路径 → 用用户的**（相对路径按当前工作目录解析）。
- 没指定 → `~/lean-4.28-reap/<Topic>-explain/`，`<Topic>` 用 ASCII（`Tactic-Omega-explain`、`Structure-explain`）。
- **不要**把新工程写进这 6 个参考根（它们是只读语料）；用户坚持时，先说明再建子目录。
- 目录名不要用中文、空格；章文件名 `ChNN_AsciiName.lean`。

---

## 3. 第 1 步：钉住原文（`SOURCE.md`）

先回答："这段代码到底来自哪个文件、哪个版本、哪几行？"

```bash
# 用片段里最独特的一行去搜工具链
rg -n -F 'Meta.withReducibleAndInstances (evalAssumption tk)' \
  ~/lean-4.28-reap/elan/toolchains/*/src/lean/
```

要点：

1. **多版本比对**：同一段代码在不同 toolchain 里行号不同（例：`evalOmega` 的属性行在
   4.28.0-rc1 是 699、4.29.1 是 702、4.33.0 是 703）。选**与讲义其他材料一致**的版本，
   写进 `lean-toolchain`，并在 `SOURCE.md` 里注明"另外两个版本只差行号，内容相同"。
2. **逐字核对**：`sed -n '702,709p'` 与用户贴的代码比对；不一致就问清楚，不要擅自"修好"。
3. **改写要标注**：用户贴的是删减版/伪代码时，`SOURCE.md` 写"教学改写，非原文"。
4. **不要修改目标源码**；只读。

`SOURCE.md` 模板：

````markdown
# SOURCE — 本系列讲解的原文

工具链：leanprover/lean4:v4.29.1

> 源码坐标：
> ~/lean-4.28-reap/elan/toolchains/leanprover--lean4---v4.29.1/src/lean/Lean/Elab/Tactic/Omega/Frontend.lean:702

```lean
（逐字原文，702–709 行）
```

## 版本差异
- 4.28.0-rc1：同文件 699–706，内容相同
- 4.33.0：同文件 703–710，内容相同
````

> 注意：`SOURCE.md` 里的围栏要写成四个反引号包住内层三个反引号，或用缩进块，
> 避免嵌套围栏把后面的内容吞掉。

---

## 4. 第 2 步：拆块（`PIECES.md`）——逐行逐块的核心

把片段切成"**能独立观察的一个行为**"一块。每块做**三层拆解**：

| 层 | 要回答的问题 |
|---|---|
| 语法层 | 这一串 token 分别是什么？哪个是关键字、哪个是宏、哪个是绑定？ |
| 语义层 | Lean 执行到这里时发生了什么？谁调用谁？状态怎么变？ |
| 实验层 | 用什么最小实验能看到它？删掉它会发生什么？ |

粒度规则：

- 一个 `|` 分支、一个 `do` 语句、一个 attribute 各算一块；
- 纯注释/空行并入相邻块，但在 `PIECES.md` 里仍标出行号；
- 一行里有两个独立机制（例：`` `(tactic| ...) `` + `%$tk`）可拆成两块，注明"同一行"；
- 每块必须能回答"**删掉它会怎样**"。

`PIECES.md` 模板：

```markdown
# PIECES — 片段 → 块 → 章 → 实验

| # | 源码行 | 这一块做什么 | 新概念 | 章 | 实验 |
|---:|---|---|---|---|---|
| 1 | 702 | 把 omega 语法注册到 evaluator 表 | `builtin_tactic` | Ch03 | `Ch03_Registration.lean` |
| 2 | 703 | 声明 tactic 入口 | `Tactic` 类型 | Ch02 | `Ch02_TacticType.lean` |
| 3 | 704 | 匹配 omega 语法、捕获 token 与可选配置 | quotation / `%$tk` / `optConfig` | Ch04 | `Ch04_SyntaxMatch.lean` |
...
```

`PIECES.md` 是后续所有章节的施工图；它没覆盖的行，讲义里也不许漏。

---

## 5. 第 3 步：排章（一章一个概念）

固定骨架：

```
Ch00  跑起来：装工具链、跑通第一个 #eval、看懂输出           （必需）
Ch01  这段代码解决的问题（用户视角：没有它会怎样）            （必需）
Ch02… 概念章：按依赖顺序，一块或一组块一章
ChN-1 回到原片段：逐块对齐（每块指向前面某一章）
ChN   全链路复盘：从源码到运行时的调用链 + 术语表
```

排章规则：

- **依赖先行**：`Tactic` 类型没讲，不要先讲 `builtin_tactic` 注册表；
- **一章一概念**：一章里出现两个新机制就拆；
- 概念章可以"欠账"：先说"这里先当黑盒，Ch07 打开"，但要在 Ch07 收回；
- 小片段（<10 行）通常 6–10 章；整文件 12–20 章；
- 每章预估 150–400 行 `.md` + 30–120 行 `.lean`，写不完就是概念太大，继续拆。

---

## 6. 第 4 步：写讲义（`ChNN.md`）

写作规范**沿用** `~/lean-4.28-reap/elab-walkthrough/AUTHORING.md` 的 §3–§5
（中文、每概念一个实验、不伪造输出、引用格式、行覆盖）。**不要在本技能里重抄一遍**。

本技能只补它没写的三件事：

### 6.1 从零四问（每章开头必须回答）

1. 没有这个概念时，用户会看到什么错误/现象？
2. 它依赖的上一个概念是什么？（给出上一章链接）
3. 最小可观察实验是什么？（本章 `.lean` 的第一段）
4. 它在原片段里负责哪一块？（`PIECES.md` 的 #）

### 6.2 章模板

```markdown
# ChNN — 一句话标题

> 本章实验：
> /abs/path/ChNN_Xxx.lean
>
> 实验输出：
> /abs/path/out/ChNN_Xxx.txt
>
> 源码坐标：
> /abs/path/.../Frontend.lean:704

## 0. 本章要解决什么（从零）
（现象 → 问题 → 本章只解决哪一件）

## 1. 最小例子
（可运行代码 + 真实输出）

## 2. 逐项解释
（每个标识符：是什么、从哪来、去掉会怎样）

## 3. 回到原片段：第 N 块
（贴原文这一块，逐 token 对齐到 §2）

## 4. 边界与常见误解
（至少 2 条：容易混淆的概念、错误写法）

## 5. 与已有材料的关系
> 已有笔记坐标：
> /abs/path/LL-06-tactic-framework.md:88

一句话说它讲了什么；一句话说本章补了什么。

## 6. 小结 + 练习
（3 条以内，练习要能跑）
```

### 6.3 讲义里的代码块

- 讲义贴的源码必须与 `SOURCE.md` 逐字一致；只贴当前块，别整段复制；
- 输出块标 `text`，代码块标 `lean`；
- 不写"输出大概是…"——只贴 `out/` 里的真实内容。

---

## 7. 第 5 步：写实验（`ChNN_*.lean`）

硬规则：

1. 每个实验**独立可编译**：`lake env lean <file>` 退出码 0；
2. `import` 尽量小；每章一个 `namespace`，避免跨章重名；
3. 每段代码都要有**可见结果**：`#check` / `#eval` / `#print` / `#guard_msgs` / `set_option trace...`；
4. **禁止 `sorry` / `admit`**（讲 `sorryAx` 时用 `axiom` 或只读源码）；
5. 输出要**确定性**：不打印地址、hash、`_uniq.123`；必须打印时在正文注明"本次运行"；
6. 失败也是实验：用 `#guard_msgs` 固定预期错误，或在注释里写"这行应当报错：…"；
7. 不依赖未配置的包（mathlib 等）；只用工具链自带 + 本工程；
8. 每章实验末尾加 `#check`/注释指回讲义与 `PIECES.md` 编号。

针对 tactic/elaborator 类片段（如 `evalOmega`），可用的观察手段：

| 想看什么 | 手段 |
|---|---|
| 语法长什么样 | `` #eval `` / `repr` 一个 `Syntax`，或 `set_option trace.Elab.step true` |
| 走没走到这个分支 | 临时 `dbg_trace "hit"`（只放在实验副本里，不改源码） |
| 失败路径 | `#guard_msgs in example : False := by omega` |
| 配置项效果 | `omega (config := { ... })`，对比 `#guard_msgs` |
| 生成的证明项 | `#print` 定理，或 `set_option pp.all true` |
| 是否用了 assumption 快路径 | 构造"假设里已有目标"的例子，对比耗时/`trace` |

运行与存盘：

```bash
cd <project-dir>
<toolchain>/bin/lake env lean Ch01_Xxx.lean > out/Ch01_Xxx.txt 2>&1
```

`out/` 里的文件必须是**这次真实运行**的结果。

---

## 8. 第 6 步：引用协议（不重复 + `gF` 可跳）

### 8.1 引用格式（硬性）

```markdown
> 源码坐标：
> ~/lean-4.28-reap/elan/toolchains/leanprover--lean4---v4.29.1/src/lean/Lean/Elab/Tactic/Omega/Frontend.lean:704
```

```markdown
> 已有笔记坐标：
> ~/Lean-source-code-learning-to-know-reap/LL-06-tactic-framework.md:88
```

规则：

- **绝对路径**，行首 `> `，**单独一行**；
- 只写**起始行**（`:704`），范围写在正文（"704–709 行"）；`gF` 只认 `file:line`；
- 路径两侧不要紧跟中文标点、括号、反引号；一行只放一条路径；
- 引 `.md` 也用同样格式；
- 写完跑 `scripts/check-refs.sh <project-dir>`，全 OK 才算过。

### 8.2 什么时候引用、什么时候重写

| 已有材料的情况 | 做法 |
|---|---|
| 正好讲这个机制，且自包含 | **只引用**：1–3 条坐标 + 一句话总结 + 一句话"本章补什么" |
| 讲了但散在 3+ 章，读者要跳很多次 | 写**压缩版从零桥接**（≤ 15 行），再引用原文 |
| 只有一句话带过 | 引用 + 本章展开；不复制原句 |
| 完全没有 | 本章从头写 |

**允许复制的上限**：必要的代码/定义 ≤ 10 行，且必须带坐标；超过 10 行一律"引用 + 改写"。

### 8.3 引用后必须有的两句话

1. "那里讲了什么"（一句）；
2. "本章补了什么 / 落到哪一行"（一句）。

只有坐标、没有这两句 = 甩锅，不算引用。

---

## 9. 第 7 步：自包含验收（四问）

拿任意一章，只打开这一个文件，问：

1. **为什么**：知道这一章解决什么问题、没有它会怎样？
2. **怎么跑**：能复制本章第一段代码直接编译，不需要先读别的章？
3. **每个名字**：出现的标识符要么本章定义、要么一句话解释、要么给坐标？
4. **下一步**：知道读完去哪一章？

任何一问答"否" → 补一段"前置/桥接"，但**仍然引用**已有材料，不整段复制。

另加两条：

- 本章不出现"显然""众所周知""参见某书"；
- 本章的 `.lean` 单独跑能过（不依赖前一章未定义的东西）。

---

## 10. 目录与文件模板

```
~/lean-4.28-reap/<Topic>-explain/
├── README.md              # 讲什么、阅读路线、章表、进度、运行命令
├── SOURCE.md              # 原文逐字 + 版本 + 上游坐标
├── PIECES.md              # 片段 → 块 → 章 → 实验
├── SOURCE-MAP.md          # （可选）整条调用链的源码坐标地图
├── lean-toolchain         # 例：leanprover/lean4:v4.29.1
├── lakefile.toml
├── <Root>.lean            # 总入口，import 所有章
├── <Root>/
│   ├── Ch00_Run.lean
│   ├── Ch00.md
│   ├── Ch01_....lean
│   ├── Ch01.md
│   ├── ...
│   ├── Appendix-Glossary.md
│   └── out/
│       └── ChNN_*.txt
└── verify.sh              # 调技能里的 verify-chapters.sh
```

另一种合法布局：主题本身已经是一个 Lean 工程时，讲义可以放在工程内的 `explain/`
（与 `lean/` 并列或在其下）。先例：
`~/lean-4.28-reap/Lean-math-formalization/leinster-n-cat/lean/explain/1-strict-n-category-composition.md`。
这种情况下 `ChNN.md`/`ChNN_*.lean` 仍按 §10 的规则编号，只是不必另建顶层 `*-explain/`。

`README.md` 必须有的表：

```markdown
| 章 | 讲义 | 实验 | 对应片段 | 状态 |
|---|---|---|---|---|
| Ch01 | `Ch01.md` | `Ch01_Xxx.lean` | PIECES #2 | ✅ |
```

---

## 11. 已核对的例子：`evalOmega`（可直接照做）

用户给的片段是 Lean 4.29.1 的
`.../src/lean/Lean/Elab/Tactic/Omega/Frontend.lean:702-709`（4.28.0-rc1 是 699–706，
4.33.0 是 703–710，**内容相同，只差行号**）。

目标目录 `~/lean-4.28-reap/Tactic-Omega-explain/` 已存在（写这段时为空）→ 直接用；
若届时已有内容，按 §2 判重后再决定补章还是新建。

拆块示例：

| # | 行 | 内容 | 新概念 | 建议章 |
|---:|---|---|---|---|
| 0 | 700 | `omegaDefault : TacticM Unit := omegaTactic {}` | 默认配置入口 | Ch02 引子 |
| 1 | 702 | `@[builtin_tactic Lean.Parser.Tactic.omega]` | attribute → 注册表 | Ch03 |
| 2 | 703 | `def evalOmega : Tactic` | `Tactic = Syntax → TacticM Unit` | Ch02 |
| 3 | 704 | `` `(tactic\| omega%$tk $cfg:optConfig) => do `` | match / quotation / `%$tk` / `optConfig` | Ch04 |
| 4 | 705 | `-- Call assumption first ...`（原注释） | 设计意图（为什么先试 assumption） | Ch05 |
| 5 | 706 | `Meta.withReducibleAndInstances (evalAssumption tk) <\|> do` | 透明度 + `<\|>` 回溯 | Ch05 |
| 6 | 707 | `let cfg ← elabOmegaConfig cfg` | `declare_config_elab` 生成的 elaborator | Ch06 |
| 7 | 708 | `omegaTactic cfg` | 真正入口（Core 算法） | Ch07 |
| 8 | 709 | `\| _ => throwUnsupportedSyntax` | fallback / 错误约定 | Ch08 |

建议章序：Ch00 跑起来 → Ch01 没有 omega 时怎么办 → Ch02 `Tactic` 类型 →
Ch03 attribute 注册 → Ch04 语法匹配 → Ch05 assumption 快路径 → Ch06 配置 elaboration →
Ch07 omegaTactic 内部 → Ch08 失败路径 → Ch09 回到原片段逐块 → Ch10 调用链复盘。

每章先查已有材料：

- `builtin_tactic` / `Tactic` 类型 → `elab-walkthrough/TacticBasic/`（引用，不重写）；
- goal / `TacticM` / `evalTactic` → `command-walkthrough/Ch12`、`LL-06`；
- `withReducibleAndInstances` → 工具链 `Lean/Meta/Basic.lean:1272` + 本章实验；
- `evalAssumption` → 工具链 `Lean/Elab/Tactic/BuiltinTactic.lean:281` + 本章实验；
- `declare_config_elab` → 工具链 `Lean/Elab/Tactic/Config.lean:174` + 本章实验；
- `omegaTactic` → 同文件 679 行起（只读引用，拆到 Ch07 讲）。

---

## 12. 工作流（可中断，按批交付）

| 批 | 产出 | 验收 |
|---|---|---|
| A. 侦察 | 版本、坐标、已有材料清单 | `SOURCE.md` 写完，`sed` 核对通过 |
| B. 骨架 | README / PIECES / lakefile / lean-toolchain / Root | `lake env lean` 能跑 Ch00 |
| C. 概念章 1–3 | 每章 `.md` + `.lean` + `out/` | 三章单独编译通过 |
| D. 概念章 4–N | 同上 | 同上 |
| E. 收尾 | 原片段对齐章 + 复盘 + 术语表 + `verify.sh` | 全部脚本通过 |

每完成一章，就在 `README.md` 的进度表打勾——下次可以从断点继续，不用重读全文。

长任务按批跑；单条命令预计 > 4 分钟就拆开。

交付后（可选）：问用户要不要把这个新目录登记到
`local-lean-source-code-explain` 的 §2 路由表，方便以后检索。

---

## 13. 验收清单（交付前逐条打勾）

- [ ] `SOURCE.md` 的原文与工具链逐字一致；版本差异已注明
- [ ] `PIECES.md` 覆盖原片段每一行，没有"跳过的行"
- [ ] 每个概念章都有同名 `.lean`，单独 `lake env lean` 退出码 0
- [ ] `out/*.txt` 是本次真实输出，无伪造、无 hash/地址
- [ ] 所有 `.lean` 无 `sorry`/`admit`
- [ ] 每章通过 §9 自包含四问
- [ ] 引用全部是"独立一行的绝对路径:行号"，`check-refs.sh` 全 OK
- [ ] 引用都带"它讲了什么 + 本章补什么"两句话
- [ ] `.md` 代码围栏成对（`grep -c '^```'` 为偶数）
- [ ] `README.md` 的章表与实际文件一致，进度已更新
- [ ] 没有整段复制已有讲义（> 10 行的复制必须改成引用 + 桥接）
- [ ] 全文中文（代码/术语除外）

---

## 14. 脚本

技能目录：`~/.config/opencode/skills/explain-from-zero-with-ref/`

| 脚本 | 用途 |
|---|---|
| `scripts/check-refs.sh <dir>` | 扫所有 `.md` 里的 `路径:行号` 引用：文件存在？行号越界？是不是相对路径？ |
| `scripts/verify-chapters.sh <project-dir>` | 逐章编译、写 `out/`、检查围栏/`sorry`/退出码，输出汇总表 |

两个脚本都只读语料、只写目标工程的 `out/`。
