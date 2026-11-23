---
name: prove2me-question-bench-train
description: 把本地 prove2me/formalpedia 快照（516k Lean 文件、0 个 olean）零编译抽成 T1–T5 分级题库，既能当 benchmark 也能当训练题；并给出让 OpenCode v2 agent 自动领题、编译、拆子任务、导出 /verify 提交包的整套环境（vLLM + OpenCode + lean-lsp + prove2me-agent 插件）。Use when extracting or sampling prove2me problems, building a Lean benchmark/train set, choosing a tier, wiring an autonomous Lean prover agent, exporting a solution to https://prove2.me/api/v1/verify, or debugging why a bank record cannot be compiled locally. Triggers: prove2me, formalpedia, 题库, T1-T5, bench_blind, bank_local, theorem_id, /verify, prove2me-agent, p2m_next, p2m_check, p2m_export, Lean 4.33.1, 0df444a, 零编译抽取, 分级难度, agentic Lean 训练.
---

# prove2me 题库：抽取、分级、训练与评测

快照：**2026-11-14**。所有产物在 `.`，语料在 `~`（只读）。
数字来自 `data/stats.json`，不要背，现算。

## 0. 三十秒

| 需求 | 用这个 |
| --- | --- |
| 语料（只读） | `~/lean-4.28-reap/formalpedia/envs/0df444a` |
| 可本地编译的题库 | `./data/bank_local/T{1..5}.jsonl`（35,894 条） |
| 全量题库（含需平台 Definitions 的题） | `data/bank/T{1..5}.jsonl`（231,995 条） |
| 盲测集（无 proof/url/fq_name） | `data/bench_blind/T{1..5}.jsonl` |
| 编译验证项目（4.33.1） | `~/lean-4.28-reap/env-0df444a` |
| FATE 项目（4.28.0） | `/data/WSP/lean/proj` |
| 抽取流水线 | `data/scripts/run_all.sh`（~3 min，热缓存） |
| Agent 插件 | `~/.opencode2/plugins/prove2me-agent`（源码在 `p2m/plugin/prove2me-agent`） |

## 1. 语料与版本

| 项 | 值 |
| --- | --- |
| toolchain | `leanprover/lean4:v4.33.1` |
| Mathlib | rev `0df444a360ea...`（8,322 个 olean，已编译） |
| `Theorems/` | 231,995（每条 `:= by sorry`） |
| `Solutions/` | 208,388（自包含：header + import + 陈述 + 证明） |
| `Definitions/` | 75,869 |
| `index-*.jsonl` | 307,864 行（theorem + definition），**含平台 UUID** |
| `graph-*.jsonl` | 1,783,895 条边，`{parent, child, via}`，`via ∈ {statement, solution}` |

状态直方图：`Proved 199,633 · Open 31,410 · Disproved 952 · Definition 75,869`。

**语料本身没有任何 olean**（516,252 个 `.lean`，0 个 `.olean`）。`lake env lean` 冷启动
实测 **35 s/文件**，全量约 5,000 核·小时 → **不要试图全量编译**，只做文本抽取 + 抽样验证。

本地快照比官方 `prove2me/formalpedia` 落后约 10 天（2026-11-04 vs 2026-11-14）；
`frenzymath` 是另一个组织（FATE），不是 prove2me 的发布方。

## 2. 题库：schema 与分级

### 2.1 记录

```json
{
  "id": "ABC.sum_triples_finite_iff_bddAbove",
  "theorem_id": "5e056e65-4eda-485d-a74d-9fe066e15584",
  "fq_name": "ABC.sum_triples_finite_iff_bddAbove",
  "tier": "T2",
  "status": "Proved",
  "url": "https://prove2.me/theorems/5e056e65-...",
  "env": {"dir": "0df444a", "mathlib_rev": "0df444a360ea...",
          "toolchain": "leanprover/lean4:v4.33.1", "is_default": true},
  "statement_nl": "自然语言陈述",
  "statement_formal": "theorem <name> ... : <type>",
  "context_pre": "陈述前必须保留的 def/open/namespace 行",
  "imports": ["Mathlib"],
  "n_solutions": 1,
  "best_solution": {"solution_id": "...", "path": "envs/0df444a/Solutions/Sol_....lean",
                    "status": "ACCEPTED", "sha256": "...", "proof": " by\n  ...",
                    "lines": 12},
  "graph_degree": {"total": 4, "in": 1, "out": 3, "by_via": {"statement": [1,3]}},
  "features": {"score": 4, "points": {...}, "tactics": {"induction": 0, "obtain": 1}},
  "local_compilable": true
}
```

关键：`theorem_id` 是**平台 UUID**，提交 `/verify` 必需；`id == fq_name`；
`best_solution.proof` 是 `:=` 之后的证明体（缩进已去掉首行）。

### 2.2 难度规则（可复算）

`S = proof_size + imports + graph_degree + defs_referenced + structural_tactics + statement_size`

| 分量 | 0 分 | 1 分 | 2 分 | 3 分 | 4 分 |
| --- | --- | --- | --- | --- | --- |
| `proof_size`（行） | ≤2 | 3–10 | 11–40 | 41–120 | >120 或无证明 |
| `imports`（去重数） | ≤1 | 2–4 | 5–10 | >10 | — |
| `graph_degree`（入+出） | ≤2 | 3–8 | 9–25 | >25 | — |
| `defs_referenced` | 0 | 1 | ≥2 | — | — |
| `structural_tactics` | 每个 `induction/obtain/calc/<;>` +1 | | | | |
| `statement_size`（字符） | <200 | 200–600 | >600 | — | — |

```text
T1: S ≤ 2      T2: 3–4      T3: 5–6      T4: 7–9
T5: S ≥ 10 或 没有参考证明（30,125 条 unsolved 全在这里）
```

### 2.3 规模

| tier | bank | bank 有参考证明 | bank_local（可本地编译） | bench | bench_blind |
| --- | --- | --- | --- | --- | --- |
| T1 | 39,520 | 39,520 | 23,310 | 39,486 | 39,486 |
| T2 | 57,845 | 57,845 | 6,109 | 57,544 | 57,544 |
| T3 | 50,564 | 50,564 | 3,544 | 50,517 | 50,517 |
| T4 | 40,009 | 40,009 | 1,846 | 39,988 | 39,988 |
| T5 | 44,057 | 13,932 | 1,085 | 13,930 | 13,930 |
| **合计** | **231,995** | 201,870 | **35,894** | 201,465 | 201,465 |

**`local_compilable`** = `imports` 里没有 `Definitions.*` / `Theorems.*`。
T1 有 59% 可编译，T2 起骤降（大量题依赖平台 Definitions，本地没有编译产物）。

### 2.4 三种用法

| 用途 | 用哪个 | 注意 |
| --- | --- | --- |
| 本地编译训练/评测 | `bank_local/*.jsonl` | 35,894 条，`lake env lean` 可直接跑 |
| no-compile 评测 | `bench_blind/*.jsonl` | 已去 `theorem_id/url/fq_name/id`，防查答案 |
| 真提交 | `bank/*.jsonl` + `p2m_export` | 需要 `theorem_id`，且提交环境必须是 4.33.1 |

`bench_blind` 里保留 `bench_id`、`tier`、`statement_formal`、`imports`，足以做题但不泄漏身份。

## 3. 平台模型与提交

| 词 | 含义 |
| --- | --- |
| `theorem` | 不可变陈述卡，状态 `Open/Proved/Disproved` |
| `solution` | 上传的 Lean 文件：**顶层 `theorem solution`**，类型与 `formal_statement` 完全一致 |
| `submission` | 一次 `/verify` 的记录，有自己的 UUID 与状态 |
| `mission` / `milestone` | 论文级形式化项目，有 captain |
| `proof-sketch` | import 其他平台定理的 solution，通过后成为 reduction |
| `program` | **平台不用这个词** |

```text
POST https://prove2.me/api/v1/verify      Bearer <token>, multipart
  theorem_id <UUID>   file solution.lean   proof_type prove|disprove   explanation
→ {"submission_id": "...", "status": "PENDING"}
GET  /api/v1/verify?submission_id=...     轮询
```

状态：`PENDING → ACCEPTED | SKETCH_ACCEPTED | CE | WA | SORRY | FAILED | ERROR`。
无人工审稿（kernel + 公理白名单）。认证：30 天 API key → `/api/v1/agent/refresh` 换 1 小时 token；
最多 100 个 PENDING。

**提交前必须自检四条**：顶层 `theorem solution`、无 `namespace`、类型逐字等于
`formal_statement`、无 `sorry`、不自 import 目标（`import Theorems.Thm_<target>`）。

## 4. 本地编译验证

两个项目，版本不通用，按 `record.env.dir` 选：

| env | 项目根 | toolchain |
| --- | --- | --- |
| `0df444a`（prove2me） | `~/lean-4.28-reap/env-0df444a` | 4.33.1 |
| FATE | `/data/WSP/lean/proj` | 4.28.0 |

```sh
cd <项目根> && PATH=$HOME/.elan/bin:$PATH MATHLIB_CACHE_DIR=... lake env lean <绝对路径>
```

候选文件可以放在项目外（`./state/...`），`lake env` 会带上 `LEAN_PATH`。
判据：无输出 = 通过；有输出 = 报错，原样回灌给模型。

## 5. Agent 环境

沿用 `fate-opencode-freeform-agent` 的三条硬规则：
`--tool-call-parser qwen3_xml`、`--standalone`、`env PWD=<task dir>`。

```sh
bash .../fate-opencode-freeform-agent/scripts/start_model.sh 0.8B
bash .../fate-opencode-freeform-agent/scripts/smoke.sh
```

强模型可以直接跑完整 agent 循环（上面的 e2e 就是用 `teamorouter/claude-sonnet-5` 跑通的）。
0.8B 实测：能正确调用 `p2m_next` 并拿到 mission，但随后会去调 `opencode_worktree_move`、
编辑 `/Optical_output.py` 之类的无关动作 → 不要用 0.8B 跑自由形式 p2m agent，
它只适合受限 tactic 循环（见 `13`/`RESULTS.md`）。

## 6. prove2me-agent 插件

**已安装**：源码 `./plugin/prove2me-agent`，部署到
`~/.opencode2/plugins/prove2me-agent`，注册在 `opencode.json → plugins`。
配套 agent `p2m`（tools 白名单：read/write/edit/shell/glob/grep + `lean-*` + `p2m_*`）。

端到端已验证（2026-11-14，run `p2m_203909`）：领到 `AMPUniversality.Universal.lemma_12`
（T1，theorem_id `fff22dcb-…`），取参考证明 → `p2m_check` 在 4.33.1 编译通过（3.8 s）
→ `p2m_export` 产出 `solution.lean / meta.json / explanation.md / curl.sh`；
导出的 `solution.lean` 单独再编译一次也通过。

`tier` 参数用 `T1..T5`（不是 FATE 的 m/h/x）。

| 工具 | 语义 |
| --- | --- |
| `p2m_next({tier?,run_id?,bank_dir?})` | 原子领题；从 `bank_local` 流式取；返回 mission + 要执行的 `goal set` |
| `p2m_get({problem_id,with_reference?})` | 记录；参考证明需显式 `with_reference:true` |
| `p2m_check({mission_id,proof})` | 规则 A/B 检查 → 按 env 选项目 → `lake env lean` → `{solved,code,platform_status,errors,goals}` |
| `p2m_submit({mission_id,proof,worker?})` | 跑 check 并记入 mission log；成功则接受 |
| `p2m_split({mission_id,subtasks})` | 写子 mission，返回 `team_send` 的 `{to:"children",mode:"queue",text}` 负载 |
| `p2m_status({run_id?})` | 按状态/tier/worker 统计 |
| `p2m_export({mission_id,explanation?})` | 写 `/verify` 包：`solution.lean`、`meta.json`、`explanation.md`、`curl.sh`（不联网） |

存储：`state/runs/<run>/{missions.jsonl,cursors/,claims/,attempts/,exports/}`；
claim 用硬链接保证并发唯一。

**DAG 规则**（写进插件注入的 system 指令）：若目标证明需要一条**本身在题库里**的引理，
不要 inline 硬证，先 `p2m_split` 再 `team_send` 给子智能体；父 mission 变 `split`。

本地状态 → 平台状态：`OK→ACCEPTED`、`TYPE_MISMATCH→WA`、`SORRY→SORRY`、
`COMPILE_ERROR→CE`、`TARGET_IMPORT→FAILED`、`LOCAL_IMPORTS_UNSUPPORTED→（不提交）`。

## 7. 端到端

```text
1  p2m_next tier=T1            → mission_id + statement + workspace
2  goal set "prove <fq_name>"  （插件会提示）
3  lean-goal / lean-multi_attempt / lean_local_search
4  p2m_check mission proof     → 编译错误回灌，迭代
5  需要子引理 → p2m_split → team_send 给 children
6  p2m_submit → p2m_export     → solution.lean + meta.json + curl.sh
7  真提交（可选）：
   curl -sS -X POST https://prove2.me/api/v1/verify \
     -H "Authorization: Bearer $PROVE2ME_TOKEN" \
     -F theorem_id=<UUID> -F proof_type=prove \
     -F file=@state/runs/<run>/exports/<mission_id>/solution.lean \
     -F explanation=@.../explanation.md
```

导出包缺 `theorem_id` 时 `ready:false`，插件不会伪造 UUID。

## 8. 训练/评测建议

| 阶段 | 数据 | 规模 |
| --- | --- | --- |
| 冷启动 | `bank_local/T1` | 23,310 |
| 课程 | T1→T2→T3（只用有证明且可编译） | 23.3k / 6.1k / 3.5k |
| 难例 | `bank_local/T4–T5` | 1,846 / 1,085 |
| 盲测 | `bench_blind/T1..T5` | 201,465（去身份） |
| 真提交 | `bank/T*` 有 `theorem_id` 的题 | 231,995 |

T5 的 30,125 条 unsolved 只应出现在 benchmark（没有参考证明，不能当训练标签）。

## 9. 坑

1. **不要全量编译语料**：0 olean、35 s/文件。
2. **两个 toolchain 不通用**：4.33.1 的候选不能在 4.28.0 项目里编译。
3. **`Definitions.*` import 本地编不了**：用 `local_compilable` 过滤，或先把依赖定义编译进项目。
4. **bench 泄漏**：原始 `bench/` 带 `url`/`theorem_id`，会让人直接查到答案；盲测用 `bench_blind/`。
5. **`index.sqlite` 2.7 GB**：查询方便，但别复制、别塞进容器镜像。
6. **同一 `statement_formal` 重复**：405 条重复，bench 按 hash 去重（195,060 → 201,465 的差异来自 tier 过滤与去重）。
7. **T5 混入 unsolved**：`bank_without_proof` 必须单独统计。
8. **语料快照会过期**：官方每日 dump，重跑前先 `git -C formalpedia pull`。

## 10. 复现

```sh
cd ./data && bash scripts/run_all.sh     # ~3 min
python3 - <<'PY'                                            # 生成 bank_local / bench_blind
# 见 §2.3；规则：imports 不含 Definitions./Theorems. 即 local_compilable
PY
```

产物校验：`data/sanity.json`（每 tier 3 条 round-trip + 300 条括号平衡）、`data/REPORT.md`。
