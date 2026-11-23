---
name: local-lean-source-code-explain
description: 用本地环境 6 个本地 Lean 4 教学语料库回答任意 Lean 关键词或整句提问：先在语料里定位，再用「绝对路径:行号」引用原文讲解。覆盖 Lean 元编程/elaboration（Command.lean、Elab/ 20 个子工程）、tactic、kernel、Expr/mvar、LmcStudy 笔记与 lmc preamble 实验、List/String 入门、Leinster strict n-category 形式化。触发词：local-Lean-source-code-explain、Lean 源码讲解、逐行讲解、lean4 元编程、Command.lean、elab、tactic、kernel、metavar、LmcStudy、lmc preamble、Lean-basic、strict n-category、数学形式化、Leinster、这个词在哪、源码第几行。
---

# 本地 Lean 源码讲解（local-lean-source-code-explain）

## 0. 一句话规则

用户丢来**一个关键词或一句话**（例："evalTactic 到底做了什么"、"为什么 apply 后目标没变"、
"Command.State 有哪些字段"、"heartbeats 怎么算"）：

1. **只在这 6 个根里找答案**（§1）；
2. 回答正文必须能追溯到**绝对路径 + 行号**（§5 模板）；
3. 引用的行号必须是**本次真正读过的行**，不许凭记忆写；
4. 语料没写的，直接说"这 6 个根里没有"，给最近邻，**不编造**。

不联网。不把模型自带的 Lean 知识冒充成"语料里的内容"——需要补充时必须显式标注
「以下是语料外补充」。

---

## 1. 语料根（唯一事实来源）

| # | 绝对路径 | 是什么 | 目标版本 |
|---|---|---|---|
| 1 | `~/lean-4.28-reap/runtime/LmcStudy/` | 学习笔记 + lmc preamble 配套实验（IO/单子/open/心跳/异步/流/会话协议） | 工程自带 |
| 2 | `~/Lean-source-code-learning-to-know-reap/` | `LL-01..LL-12` 长文：Lean 内部机制（repo/Expr/kernel/mvar/单子/tactic/lctx/声明/pp/options/补全/widget） | `v4.28.0-rc1` |
| 3 | `~/lean-4.28-reap/command-walkthrough/` | `Lean/Elab/Command.lean` 884 行逐行讲解（Ch00–Ch15 + 附录 A/B） | `v4.29.1` |
| 4 | `~/lean-4.28-reap/elab-walkthrough/` | `Lean/Elab/` 20 个子工程、158 章、约 11476 行源码的逐行讲解 + 可跑实验 | `v4.29.1` |
| 5 | `~/lean-4.28-reap/Lean-basic/` | `List`/`String`/`Array`/数据结构入门 8 章 + 上游行号地图 | `v4.29.1` |
| 6 | `~/lean-4.28-reap/Lean-math-formalization/leinster-n-cat/lean/` | Leinster 有限 strict n-category 形式化：Kernel/Syntax/Math/Pipeline/Examples + `explain/` 中文长文 | `v4.29.1` |

每个根的"总入口"（回答前先看它，比 grep 快）：

- ① `LmcStudy/README.md`、`LmcStudy/Notes.lean`
- ② `Lean-source-code-learning-to-know-reap/LL-00-README-plan.md`
- ③ `command-walkthrough/Walkthrough/README.md`
- ④ `elab-walkthrough/README.md`、`elab-walkthrough/CURRICULUM-20.md`、`elab-walkthrough/MANIFEST.md`
- ⑤ `Lean-basic/README.md`、`Lean-basic/SOURCE-MAP.md`
- ⑥ `leinster-n-cat/lean/README.md`、`ARCHITECTURE.md`、`SPEC.md`、`explain/1-strict-n-category-composition.md`

### 1.1 版本与路径陷阱（很重要）

- 根 ③④⑤ 的讲义对着 **4.29.1** 写，上游源码在
  `~/lean-4.28-reap/elan/toolchains/leanprover--lean4---v4.29.1/src/lean/`。
- 根 ② 的 LL 系列对着 **4.28.0-rc1** 写，但它文内写的 `/home/<user>/project/...` 在本地环境**不存在**。
  引用上游源码时映射到：
  `~/lean-4.28-reap/elan/toolchains/leanprover--lean4---v4.28.0-rc1/src/lean/`
- LL 文内的 `:74` 一类坐标是写作时坐标，实测可能差 1–3 行（例：`getGoals` 文档写 `:74`，
  实际在 `Basic.lean:73`）。**引用前必须 `grep -n` 复核**。
- 根 ④ 的每章开头都写了两套坐标：**讲义正文**在 `ChNN.md`，**目标源码行**在
  `ChNN.md` 头部引用块 + 同目录 `INDEX.md`。别把两者混为一谈。
- 根 ⑥ 固定 `v4.29.1`；它的 `explain/*.md` 里有些链接写成 `/D:/projects/...`（Windows 路径，
  本地环境不存在），**不要引用这些链接**，只引本地环境真实存在的 `.lean`/`.md` 和 `README/ARCHITECTURE/SPEC`。

---

## 2. 30 秒路由表（先查这里，再 grep）

### 2.1 根 ③ `command-walkthrough` — 一条命令的一生

目录 `~/lean-4.28-reap/command-walkthrough/Walkthrough/`，讲义 `ChNN.md` 与实验
`ChNN_*.lean` 同名配对。

| 主题 | 章 | 源码行 |
|---|---|---|
| 跑起来、`#check`/`#eval` | `Ch00.md` | — |
| 类型/函数/结构/归纳类型 | `Ch01.md` | — |
| 单子、`do`、`IO`、`ReaderT`/`StateRefT` | `Ch02.md` | — |
| `Syntax`、解析、宏、命令 elaborator | `Ch03.md` | — |
| `Environment`、声明、内核检查 | `Ch04.md` | — |
| `CoreM`/`MetaM`/`TermElabM`/`CommandElabM` | `Ch05.md` | — |
| 文件头 + `Command.State` | `Ch06.md` | 1–31 |
| `Command.Context` | `Ch07.md` | 33–59 |
| `CommandElabM` 与能力实例 | `Ch08.md` | 61–160 |
| `runCore`/`liftCoreM`/`liftIO` | `Ch09.md` | 162–217 |
| 日志、linter、异步、隔离流 | `Ch10.md` | 219–360 |
| 命令注册表、信息树、宏展开上下文 | `Ch11.md` | 361–451 |
| `elabCommand` 主循环 | `Ch12.md` | 452–539 |
| `elabCommandTopLevel` | `Ch13.md` | 541–630 |
| term 桥、适配器、作用域 | `Ch14.md` | 632–804 |
| `liftCommandElabM`、`set_option ... in` | `Ch15.md` | 806–884 |
| 术语 / 任意行 → 章 | `Appendix-A-术语表.md` / `Appendix-B-行号索引.md` | 1–884 |

### 2.2 根 ④ `elab-walkthrough` — `Elab/` 的 20 个文件

每个子目录结构固定：`README.md`（路线）、`INDEX.md`（**行号覆盖表 + 关键定义索引**）、
`ChNN.md`（讲义）、`ChNN_*.lean`（实验）、`out/`（真实输出）。

| 子目录 | 讲的上游文件 | 关键词 |
|---|---|---|
| `Frontend/` | `Elab/Frontend.lean` | 解析循环、`FrontendM`、快照、`runFrontend`、`.olean`/`.ilean` |
| `BuiltinCommand/` | `Elab/BuiltinCommand.lean` | `open`/`namespace`/`section`/`variable`/`universe`/`set_option`/`#check`/`#eval` |
| `Declaration/` | `Elab/Declaration.lean` | `def`/`theorem`/`axiom` 命令如何分派 |
| `PreDefinitionMain/` | `Elab/PreDefinition/Main.lean` | `PreDefinition`、SCC、递归、`addPreDefinitions`、内核门禁 |
| `TacticBasic/` | `Elab/Tactic/Basic.lean` | goal 列表、`TacticM`、`by`、`evalTactic`、`focus`/`done`、回溯 |
| `Import/` | `Elab/Import.lean` | `module`/`prelude`/`import` → `Environment` |
| `SetOption/` | `Elab/SetOption.lean` | `set_option` 全链路 |
| `GuardMsgs/` | `Elab/GuardMsgs.lean` | `#guard_msgs`、期望文本、错误断言 |
| `InfoTreeMain/` | `Elab/InfoTree/Main.lean` | `InfoTree`、`withInfoContext`、hover/goals、树遍历 |
| `Syntax/` | `Elab/Syntax.lean` | `syntax`、parser 描述、cat、alias/atom |
| `Quotation/` | `Elab/Quotation.lean` | `` `(term) ``、antiquotation、宏卫生 |
| `Binders/` | `Elab/Binders.lean` | `∀`/`fun`/`let`/`where`/match alt、`BinderView` |
| `SyntheticMVars/` | `Elab/SyntheticMVars.lean` | 延迟 elaboration、synthetic mvar 落地 |
| `BuiltinTerm/` | `Elab/BuiltinTerm.lean` | 内建 term elaborator（`Sort`/`fun`/`let`/投影…） |
| `Inductive/` | `Elab/Inductive.lean` | `inductive` 视图、构造子、参数重排、`mkInductiveElabDescr`、`addDecl`/recursor |
| `Structure/` | `Elab/Structure.lean` | `structure`/`class`、`extends`、字段、投影、继承表示 |
| `TacticExt/` | `Elab/Tactic/Ext.lean` | `@[ext]`、`ext` tactic |
| `MutualDef/` | `Elab/MutualDef.lean` | `mutual`/`elabHeaders`、`declVal`、section var、`?_` 洞与 `where ... finally`、闭包、`PreDefinition` 组装 |
| `TacticElabTerm/` | `Elab/Tactic/ElabTerm.lean` | tactic 里 elab term、`elabTermEnsuringType` |
| `TacticBuiltinTactic/` | `Elab/Tactic/BuiltinTactic.lean` | `run_tac`、内建 tactic 包装 |

### 2.3 根 ② `Lean-source-code-learning-to-know-reap` — 机制长文

| 文件 | 覆盖 |
|---|---|
| `LL-01-lean4-repo-and-pipeline.md` | 仓库布局、`Environment`、`.olean`、前端流水线 |
| `LL-02-expr-levels.md` | `Expr`、`Level`、proofs-as-terms |
| `LL-03-kernel-type-checker.md` | kernel 声明、`sorryAx`、`type_checker.cpp` |
| `LL-04-metavars-defeq.md` | `MetavarContext`、赋值、`isDefEq`、`whnf` |
| `LL-05-monads-tasks-heartbeats.md` | `CoreM`/`MetaM`/`TacticM`、`Context`、`Task`、心跳、IO |
| `LL-06-tactic-framework.md` | goal 列表、`saveState`/`restore`、消息、异常、`run_tac` |
| `LL-07-localcontexts.md` | `LocalContext`/`LocalDecl`、fvar、aux decl、section var |
| `LL-08-declarations-predefinitions.md` | `Declaration`、`PreDefinition`、`addPreDefinitions`、`checkWithKernel` |
| `LL-09-pp-messages-positions.md` | `ppGoal`/`ppExpr`、`FileMap`、位置、消息序列化 |
| `LL-10-options-json.md` | `register_option`、`Options`、`Json`、`ToJson`/`FromJson` |
| `LL-11-library-suggestions.md` | `Selector`、`Suggestion`、`select` |
| `LL-12-widgets-rpc-trythis.md` | `UserWidget`、`RpcEncodable`、`TryThis` |

### 2.4 根 ⑤ `Lean-basic` — `List`/`String`/`Array`

| 章 | 主题 |
|---|---|
| `LeanBasic/Ch01.md` | `List.foldl` 逐字拆、尾递归、`foldl_append` |
| `LeanBasic/Ch02.md` | `List` 归纳类型、`List.rec`、`MyList` |
| `LeanBasic/Ch03.md` | `map`/`filter`/`flatMap`/`++`/`reverse`/`zip`/`range`/`take`/`drop` |
| `LeanBasic/Ch04.md` | 插入排序、`mergeSort`、二分查找、`length_insert` |
| `LeanBasic/Ch05.md` | 栈、队列、二叉树、BST、DFS |
| `LeanBasic/Ch06.md` | `String` = UTF-8 `ByteArray` + `List Char` 视图、Slice |
| `LeanBasic/Ch07.md` | 回文、游程编码、词频、凯撒、子串查找 |
| `LeanBasic/Ch08.md` | `Array` 与 `List` 分工、RPN 计算器 |
| `SOURCE-MAP.md` | 上游 `Init/...` 的**精确行号**地图（`gF` 用） |

### 2.5 根 ① `LmcStudy` — 笔记与 lmc preamble

| 位置 | 覆盖 |
|---|---|
| `Notes/IO.lean` | IO/`Unit`/`do`、悬停与跳转机制 |
| `Notes/PreambleOpen.lean` | `open`、命名空间解析、`Tactic.SavedState` |
| `Notes/ElabAsync.lean` | `Elab.async` 异步 elaboration |
| `Notes/Heartbeats.lean` | `maxHeartbeats` 心跳预算与 Reap 分工 |
| `Notes/Streams.lean` | check 模式 IO 隔离流（stdin/stdout、`/proc`、FIFO） |
| `Notes/SessionProtocol.lean` | JSON-Lines 协议、SavedState 句柄、收尾路径 |
| `Notes.lean` | 笔记索引 + 跨文件跳转表 |
| `Notes/meta-programming-and-whole-lmc-server-style.md` | LMC 整体架构长文（Python 侧 ↔ Lean 侧） |
| `Experiments/Preamble/README.md` | e1–e8 实验与笔记的对照表 |
| `LmcPreamble.lean` | `lmc_preamble.lean` 的 IDE 可编译阅读版 |
| `Functional-programming-in-lean/cha2/*.lean` | 读书练习（2.1 running a program） |

检索根 ① 时**只搜这些主路径**，别把 2GB 的 `FP-MP-source/` 抖进来（见 §3.2）。

### 2.6 根 ⑥ `leinster-n-cat/lean` — strict n-category 形式化

工程根：`~/lean-4.28-reap/Lean-math-formalization/leinster-n-cat/lean/`

| 主题 | 去哪 |
|---|---|
| 工程总览、模块依赖图、构建方式 | `README.md`、`ARCHITECTURE.md`、`SPEC.md` |
| 中文长文：沿 p-胞的复合 `∘_p`、球状集合、边界 | `explain/1-strict-n-category-composition.md` |
| 维度/截断 `Level`、粘贴图输入 | `StrictNCategory/Syntax/Dimension.lean`、`StrictNCategory/Syntax/Pasting.lean` |
| 有限球状载体、边界算子 | `StrictNCategory/Kernel/GlobularData.lean`、`StrictNCategory/Kernel/Boundary.lean` |
| 球状恒等式、签名/操作、Leinster 六条边界公理 | `StrictNCategory/Math/GlobularSet.lean`、`Signature.lean`、`AdjacentLaws.lean` |
| 严格 n-范畴的数学契约（各 law 分结构） | `StrictNCategory/Math/Strict.lean`、`Laws.lean` |
| 纯边界计算（不依赖复合） | `StrictNCategory/Math/BoundaryCalculus.lean` |
| 导出 unit/assoc/interchange、cast-free API、按 cut 取普通范畴 | `StrictNCategory/Pipeline/Derived.lean`、`Facade.lean`、`CategoryAt.lean` |
| 函子 | `StrictNCategory/Math/Functor.lean` |
| 例子：terminal / discrete / one-object / 低维 | `StrictNCategory/Examples/*.lean` |
| 验收测试 | `Tests/Main.lean` |
| SNL 导出/校验工具 | `SNL/README.md`、`SNL/Generator.lean` |

版本：固定 `v4.29.1`。注意 `explain/*.md` 里指向 `/D:/projects/...` 的链接在本地环境无效（见 §1.1）。

---

## 3. 检索流程（每次照做）

### 3.1 先归一化关键词

**整句提问先拆成 2–4 个概念**，再分别定位。例：

> "为什么 `apply` 之后目标数没变？"
> → 概念：`apply` / goal 列表 / `Tactic.State` / `setGoals`；
> → 先查 `elab-walkthrough/TacticBasic/`（goal 操作），再查 `command-walkthrough/Ch12`（谁在循环跑 tactic）。

中文词先展开成"中文词 + 英文标识符"两组，再搜：

| 用户可能说 | 同时搜 |
|---|---|
| 目标 / 目标列表 / 子目标 | `goal`, `goals`, `MVarId`, `getGoals`, `setGoals` |
| 策略 / 证明状态 | `tactic`, `TacticM`, `evalTactic`, `SavedState`, `proof state` |
| 环境 / 常量 | `Environment`, `env`, `ConstantInfo`, `addDecl`, `getConstInfo` |
| 内核 / 检查 | `kernel`, `check`, `type_checker`, `checkWithKernel` |
| 定义相等 | `isDefEq`, `defeq`, `whnf`, `reduce` |
| 元变量 / 洞 | `mvar`, `metavar`, `MVarId`, `instantiateMVars`, `sorry` |
| 绑定变量 / 局部上下文 | `binder`, `fvar`, `LocalDecl`, `LocalContext`, `lctx` |
| 心跳 / 超时 | `heartbeats`, `maxHeartbeats`, `withHeartbeats` |
| 异步 / 任务 | `async`, `Elab.async`, `Task`, `asTask` |
| 宏 / 语法 | `macro`, `syntax`, `quotation`, `Syntax`, `ParserDescr` |
| 声明 / 定义 | `declaration`, `PreDefinition`, `addPreDefinitions`, `axiom` |
| 信息树 / 悬停 | `InfoTree`, `withInfoContext`, `Info`, `hover` |
| 作用域 / 命名空间 | `scope`, `namespace`, `open`, `section`, `variable` |
| 打印 / 消息 / 位置 | `ppGoal`, `ppExpr`, `Message`, `FileMap`, `Position` |
| 选项 / JSON | `register_option`, `Options`, `Json`, `ToJson` |
| 补全 / 搜索建议 | `LibrarySuggestions`, `Selector`, `Suggestion` |
| 组件 / RPC | `Widget`, `Rpc`, `TryThis`, `savePanelWidgetInfo` |

### 3.2 用脚本搜（统一排除构建产物）

```bash
# 默认：内容模式，每个文件最多 3 条，按 6 个根的优先级输出
bash scripts/lean-search.sh evalTactic

# 只看命中文件清单（先看全貌，再挑着读）
bash scripts/lean-search.sh --files "SavedState"

# 符号里有 . ( ) 等字符时，用 -F 当字面量搜
bash scripts/lean-search.sh -F "Tactic.State"

# 限定讲义 / 限定实验
bash scripts/lean-search.sh --md   "heartbeats"
bash scripts/lean-search.sh --lean "maxHeartbeats"

# 只在某一个根里搜
bash scripts/lean-search.sh --root 4 "elabTerm"
```

脚本默认排除 `.lake/`、`_out/`、`**/out/`、`__pycache__/`、`node_modules/`、`.git/`；
需要看实验真实输出时加 `--with-out`。

等价的手工命令（脚本不可用时）：

```bash
rg -n --max-count 3 \
  --glob '!.lake/**' --glob '!_out/**' --glob '!**/out/**' \
  --glob '!**/__pycache__/**' --glob '!**/node_modules/**' \
  'evalTactic' \
  ~/lean-4.28-reap/runtime/LmcStudy \
  ~/Lean-source-code-learning-to-know-reap \
  ~/lean-4.28-reap/command-walkthrough \
  ~/lean-4.28-reap/elab-walkthrough \
  ~/lean-4.28-reap/Lean-basic \
  ~/lean-4.28-reap/Lean-math-formalization/leinster-n-cat/lean
```

> 根 ① 太大（2.0 GB，主要是 `FP-MP-source/` 的书仓库）。默认只搜
> `Notes/`、`Experiments/`、`Notes.lean`、`LmcPreamble.lean`、`README.md`、
> `Functional-programming-in-lean/`；确实要查 `FP-MP-source/` 时显式加
> `--with-fp-mp`，并在回答里说明这是"书仓库"而非本仓库笔记。

### 3.3 读命中，不要只信 grep 行

- 讲义（`.md`）：读命中行 **±40 行**，确认它讲的是"同一个东西"（同名符号在不同文件里可能指不同概念）。
- 实验（`.lean`）：读整个定义块，别只读一行。
- 用 `scripts/lean-locate.sh <file>:<line>` 一次性拿到"所属章节标题 + 上下文"。

### 3.4 排序：先讲义，后实验，再上游

同一关键词常常三处都有。默认按这个顺序给：

1. **逐行讲义**（`LL-*.md`、`Ch*.md`）—— 有解释，最适合作答；
2. **可跑实验**（`Ch*.lean`、`e*.lean`）—— 用户想"看最小例子/动手"时给；
3. **笔记模块**（`Notes/*.lean`）—— 跨文件悬停用；
4. **上游源码**（toolchain）—— 只有用户问"Lean 自己怎么实现"时才展开。

---

## 4. 按问法分派

| 用户问法 | 做法 |
|---|---|
| "X 是什么 / 怎么工作" | 查 §2 路由 → 读该章 → 用章节里的定义 + 原文块作答 |
| "X 在第几行 / 哪一行" | `command-walkthrough` 用 `Appendix-B-行号索引.md`；`elab-walkthrough` 用 `<子目录>/INDEX.md`；`Lean-basic` 用 `SOURCE-MAP.md` |
| "给我看代码 / 最小例子" | 找同名 `ChNN_*.lean` 或 `eN_*.lean`，给出**整个文件路径** + 关键行；说明怎么跑 |
| "跑一下 / 输出是什么" | `out/` 里有真实输出；命令见该子目录 `README.md`（多为 `lake env lean <Folder>/ChNN_*.lean`） |
| "这段话什么意思"（贴了原文） | 先 grep 原文片段定位出处，再解释；若语料里没有，明说 |
| "对比 A 和 B" | 先各自定位，再给"两处原文 + 差异表"，每行差异都带路径:行号 |
| "整个流程是怎样的" | 用 `command-walkthrough/Ch12`（命令主线）或 `elab-walkthrough/Frontend`（前端主线）+ `LL-01`（仓库/流水线）拼 |
| "为什么报错 / 为什么没效果" | 优先 `LmcStudy/Notes/*.lean` 与 `elab-walkthrough/GuardMsgs`；仍无则说明语料未覆盖 |

---

## 5. 回答模板（硬性）

````markdown
**结论**：一句话回答（不超过 3 行）。

**材料位置**

| 绝对路径:行号 | 这是什么 |
|---|---|
| `~/lean-4.28-reap/<系列>/<章>.md:123` | 讲义：给出定义/机制的那一段 |
| `~/lean-4.28-reap/<系列>/<实验>.lean:45` | 可跑的最小实验 |

**讲解**：按"是什么 → 为什么 → 在这套源码里落在哪"讲，2–5 段。

**原文**（`/abs/path:120-130`）：

```lean
...
```

**接着读**：给 1–3 个相邻章节或实验的绝对路径。
````

### 5.1 一个真实例子（"SavedState 里到底存了什么？"）

**结论**：`SavedState` 是 tactic 的"存档"，内容 = `Term.SavedState`（含 `MetavarContext` 等）
+ `Tactic.State`（goal 列表）；它**不包含** `Tactic.Context`，所以 `restore` 不会恢复
`elaborator`/`recover`。

**材料位置**

| 绝对路径:行号 | 这是什么 |
|---|---|
| `~/lean-4.28-reap/elab-walkthrough/TacticBasic/Ch02.md:276` | 讲义：`saveState`/`restore` 只存 `Term.SavedState` + `Tactic.State`，不存 `Context` |
| `~/lean-4.28-reap/elab-walkthrough/TacticBasic/INDEX.md:142` | 行号索引：对应上游 `Basic.lean:114-115` 的 `saveState` 定义 |
| `~/lean-4.28-reap/elab-walkthrough/TacticBasic/Ch07.md:40` | 实验章：`MonadBacktrack SavedState TacticM` 实例 |

**原文**（`.../TacticBasic/Ch02.md:276-277`）：

```markdown
- 它们在一次 tactic 执行期间**不需要被回溯**。`saveState`/`restore` 只保存
  `Term.SavedState` + `Tactic.State`（Ch03），不保存 `Context`。
```

**接着读**：`~/lean-4.28-reap/elab-walkthrough/TacticBasic/Ch03.md`（`saveState` 逐行）、
`~/Lean-source-code-learning-to-know-reap/LL-06-tactic-framework.md:88`（"Snapshot and restore" 一节）。

> 注意上表第二行：`INDEX.md` 的第一列是**上游源码行号**，不是 `INDEX.md` 自己的行号。
> 引用时写清"索引行 / 上游行"，别混。

要求：

- 表格里的每一行都必须是**真实存在的文件 + 真实行号**；回答前用 `read` 或
  `lean-locate.sh` 确认过。
- 行号区间用 `:120-168`，单行用 `:120`；不要写"大约第 120 行"。
- 引用块必须来自文件原文，**不改写、不省略号拼接**；要省略时写 `…（省略）` 并说明。
- 若一个关键词命中多章，先给"命中地图"（3–6 行表格），再展开最相关的一处，
  其余给路径让用户挑——不要把所有命中都展开成长文。

---

## 6. 引用与边界规则

1. **绝对路径**：从 `~/...` 写起，不写 `./Walkthrough/Ch05.md`。
2. **讲义行号 vs 源码行号**要分清：
   - `Ch05.md:120` = 讲义文件自己的第 120 行；
   - `Ch05.md` 开头引用块里的 `Basic.lean:114` = 上游源码坐标。
   两者都写时，标明哪个是哪个。
3. **上游源码只在需要时展开**，并写清工具链版本；不要把 `v4.29.1` 的行号套到
   `v4.28.0-rc1` 上。
4. **找不到时**：给出"已搜过的根 + 用过的同义词"，再给 1–3 个最近邻（明确标注
   "这里是相邻主题，不是直接答案"）。绝不虚构章节号。
5. **语料外补充**必须单独一段，标题写「语料外补充（非本 6 个根）」。

### 6.1 语料缺口与同级目录（默认不用）

这 6 个根**没有**系统覆盖：`simp`、`omega`、`norm_num`、`Init/System`、
`Prelude` 细节、习题集、以及**除 strict n-category 之外**的数学形式化。
若用户明确问这些，可以指到同级的兄弟目录，但必须标注"不在本次 6 个根内"：

```
~/lean-4.28-reap/simp-tactic-explain/
~/lean-4.28-reap/Tactic-Omega-explain/
~/lean-4.28-reap/Structure-explain/
~/lean-4.28-reap/Prelude-lean-explain/
~/lean-4.28-reap/Init-System-explain/
~/lean-4.28-reap/Lean-math-formalization/     # 根 ⑥ 只覆盖 leinster-n-cat
~/lean-4.28-reap/Lean-exercise/
```

---

## 7. 提交前自检

- [ ] 每个被引用的 `路径:行号` 都用 `read` 或 `lean-locate.sh` 验证过
- [ ] 至少一条**原文引用块**，且与文件逐字一致
- [ ] 讲义坐标与上游源码坐标没有混用
- [ ] 用户问的是中文 → 中文答；英文 → 英文答；术语保留英文原名
- [ ] 没有把 `FP-MP-source/` 的书内容说成本仓库笔记
- [ ] 找不到时明确说了"没覆盖"，并给了最近邻
- [ ] 回答末尾给了 1–3 个"接着读"的绝对路径

---

## 8. 附：脚本

技能目录：`~/.config/opencode/skills/local-lean-source-code-explain/`

| 脚本（绝对路径） | 用途 |
|---|---|
| `~/.config/opencode/skills/local-lean-source-code-explain/scripts/lean-search.sh` | 在 6 个根里搜关键词，统一排除构建产物；`--files`/`--md`/`--lean`/`--root N`/`--with-out`/`--with-fp-mp` |
| `~/.config/opencode/skills/local-lean-source-code-explain/scripts/lean-locate.sh` | 给 `file:line`，输出所属标题、前后文、行号标尺 |

两个脚本都只读，不修改语料。首次调用前 `chmod +x scripts/*.sh` 已完成；若权限丢失，
用 `bash <脚本> ...` 直接跑。
