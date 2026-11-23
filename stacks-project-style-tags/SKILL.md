---
name: stacks-project-style-tags
description: 'Apply or validate Stacks-Project-style tagged, numbered items（每个定义/定理/证明/代码/notebook cell 都有唯一 Tag，可交叉引用、不重复）to Markdown docs, source files, and Jupyter notebooks. Use when restyling notes/docs into tagged environments, adding F-/N- tags to code files and notebook cells, building a registry, or validating tag uniqueness / numbering / references. Triggers: stacks project 风格, tag 化, 风格改造, style tags, 编号条目, 交叉引用, 定义定理证明编号, code tags, notebook tags, validate tags, tag 校验.'
---

# Stacks-Project 风格 Tag 化规范

把文档、代码、notebook 改造成「条目 + 编号 + Tag」结构，便于精确交叉引用、避免重复书写同一内容。本 skill 是通用规范；**具体项目的 doccode、F-/N- 登记表放在项目自己的规范文件里**（如 `00-风格与编号规范.md`）。

## 1. 核心原则

1. 每个可引用对象都有**唯一 Tag**：文档条目、代码文件与顶层符号、notebook 及其 cell。
2. **编号给人读，Tag 给机器检索**。引用一律写编号；需要精确定位（跨文件、编号可能变动）时附 Tag。
3. **不重复原则**：同一内容的完整陈述与证明只出现在它的归宿条目，其他位置引用编号，最多复述一句必要结论。
4. Tag 一经发布视为稳定 ID；编号可随重排变化。改动 Tag 必须全局替换所有引用。
5. 只做「分块、编号、加 Tag、加引用」；不得改动数学内容、代码语义与叙述本意。

## 2. 文档条目（Markdown）

条目格式（单行，独立成段）：

```
**【<环境名> <编号>｜<Tag>】（短标题）**
```

- 编号 = `<doccode>.<sec>.<item>`：
  - `doccode`：文件级代码，登记在项目规范文件（基础章可用章号如 `1`，专题文档用如 `PT`、`LORA`）；
  - `sec`：文件内小节序号，按出现顺序 1,2,3…；
  - `item`：**每节内跨类型连续编号**（Stacks Project 风格），从 1 开始。
- Tag = `<TYPE>-<doccode>.<sec>.<item>`，示例：`P-1.2.9`、`T-PT.3.1`。
- 证明格式：`**【证明｜Pf-<doccode>.<sec>.<item>】**`，编号与被证条目相同。

类型前缀表：

| 前缀 | 含义 | 前缀 | 含义 |
| --- | --- | --- | --- |
| D | 定义 | E | 例 |
| T | 定理 | R | 注 |
| P | 命题 | A | 算法 |
| L | 引理 | Cd | 代码（文档中的代码块条目） |
| C | 推论 | Ex | 练习 |
| Pf | 证明 | | |

引用写法：

- 同文件：`见【命题 1.2.9】`；跨文件：`见《05-LoRA原理》【命题 LORA.3.1】`；
- 需要精确检索时附 Tag：``[P-1.2.9]``；
- 文档里的**示例编号**（非真实引用）必须放进反引号，如 `` `【命题 X.1.2】` ``，否则校验脚本会当成悬空引用。

文件头（每个 md）加一行元信息，声明 doccode：

```
> **文档｜DOC-<KEY>**（doccode = `<doccode>`）｜编号与 Tag 规范见《00-风格与编号规范》。
```

## 3. 代码文件（.py / .sh）

- 文件级 Tag：`F-<filekey>`，filekey 登记在项目规范文件中（稳定、ASCII、路径推导，如 `F-b01-model`）。
- 文件头注释块（紧接 shebang/import 之前或之后，保持可执行）：

```python
# 【源代码｜F-b01-model】v1.0/01-基础/code/from_scratch/model.py — 一句话说明
# 相关文档：【定义 1.1.3｜D-1.1.3】、【代码 1.1.4｜Cd-1.1.4】
```

脚本用 `# 【脚本｜F-tools-xxx】…`（校验脚本两种前缀都认）。

- 顶层 `class` / `def` 定义前一行加注释：`# 【F-b01-model.MLP｜类】一句话`。
- **只加注释，零语义改动**；完成后必须通过 `python3 -m py_compile`（.py）或 `bash -n`（.sh）。

## 4. Jupyter Notebook（.ipynb）

- 文件级 Tag：`N-<NN>`（来自文件名 N01…N17 等，登记在规范文件）。
- 首个 markdown cell 置顶 header：

```markdown
# 【notebook｜N-01】（标题）
> 对应文档：【…】；相关代码：`F-…`
```

- 每个 code cell 首行注释：`# 【N-01.c<k>】`，k = 该 notebook 中 code cell 的序号（1 起）；主要小节 markdown cell 可用 `**【N-01.m<j>】**`（j = markdown cell 序号）。
- JSON 保真：用 Python `json.load`/`json.dump`（`ensure_ascii=False, indent=1`，文件末尾换行）；除 header 与注释外**不改任何 cell**，outputs 原样保留。
- 完成后必须通过 JSON 解析，且所有 code cell 均带首行 Tag。

## 5. 登记表（Registry）

项目必须在 `00-风格与编号规范.md`（Tag：`DOC-STYLE`）中登记：

- 每个 md 的 doccode 与文件级 Tag；
- 每个代码文件的 `F-` filekey（含无法加注释的 JSON 配置文件——只登记，不修改文件）；
- 每个 notebook 的 `N-` code；
- 明确例外与豁免（如空目录、生成物）。

新增可引用对象：**先登记，再打 Tag**。

## 6. 校验（提交前必跑）

```bash
python3 ~/.config/opencode/skills/stacks-project-style-tags/scripts/validate_tags.py <root>
```

检查：① Tag 全局唯一；② 每文件每节 item 编号连续；③ 引用可解析（反引号内示例豁免）；④ notebook header/code cell Tag 完整；⑤ 代码文件级 Tag 存在且唯一。
输出 `errors: 0` 才算通过；`warnings` 需逐条确认。

Markdown 公式另按 `md-latex-rule` 检查（`$...$` 单行、`$$` 前后空行顶格、中文标点不进数学模式）。

## 7. 改造流程（迁移现存文档）

1. 通读文件，标出可条目化对象（定义/定理/命题/引理/推论/例/注/算法/代码块/练习）。
2. 按「先术语、后结论、再例子」重排为条目；编号按节内出现顺序分配。
3. 找出全文重复内容：保留一处完整版（归宿条目），其余改为引用。
4. 补文件头 doccode 行；必要时登记 registry。
5. 跑校验脚本 + md-latex 检查，修到零错误。

## 8. 反模式

- 不要为「形式完整」伪造引用目标，或把引用目标写成不存在编号。
- 不要借 tag 化重写内容、压缩讲解（除非用户明确要求骨架化）。
- 不要在代码里做注释以外的任何改动。
- 不要跳过 registry 直接发明 doccode / filekey / N-code。
- 不要在 `$$` 数学模式里放中文标点，或把行内公式跨行。
