---
name: v2.0.0-alpha-proof
description: '从 AlphaProof v1.0.0/v1.1.0 升级到 v2.0.0 的完整路线：把 LLM 放进 OpenCode v2 作为 agentic 动作执行器，在 Lean 4 题目序列上做 MCTS + CE。包含节点/动作/commit 协议、opencode v2 插件与 agent 配置、三层写权限、提案通道与执行通道、训练数据 span、分阶段验收与防作弊。当用户要做 agentic Lean 证明、把 opencode 接进 MCTS、设计 v1-1/v2 协议、跑多题 Lean 训练、或问“工具调用要不要进树”时使用。触发词：v2.0.0-alpha-proof, alpha-proof-v1-1-agentic, opencode v2 证明, agentic MCTS, Lean 4 多题训练, commit 协议, lean_submit_step, 提案通道, MCTS+CE, 工具调用不是边, env_id, write_spans, 防作弊。'
---

# v2.0.0-alpha-proof

一句话：**v1.0.0 是 tactic 级 GPU 训练，v1.1.0 是 CPU 侧 Lean 会话 + MCTS；v2.0.0 把“写 tactic”换成一个 OpenCode v2 agent episode，但树只认内核接受的 commit。**

先读两个前置 skill：
- `v1.0.0-alpha-proof-gpu-training`：`/eval`、CE、值头、pool；
- `v1.1.0-lean-mcts-cpu-server`：会话、状态句柄、`apply/focus/verify`、store。

## 0. 版本定义

| 版本 | 搜索 | 动作 | 训练 |
| --- | --- | --- | --- |
| v1.0.0 | GPU 侧只提供 policy/value | 一条 tactic | CE（tactic token） |
| v1.1.0 | CPU 侧 Python MCTS | 一条 tactic，可分支/回滚 | 导出 Transition |
| **v2.0.0** | 同一个 MCTS | **一个 agent episode 的 commit**（可含多 tactic / 文件操作） | CE 只对 commit 的 tactic span |

v2.0.0 不是重写，而是在两者之间加一层 **AgenticEnv / commit 协议**。

## 1. 四条铁律

1. **工具调用不是边。** `read/grep/bash/websearch/edit` 都是动作内部计算（带副作用的思维链），不改变树。
2. **只有内核接受的 proof-state delta 才是边。** 一次 commit = 一个 `(env_id, goals)` → `(env_id', goals')` 的转变。
3. **节点 = `(env_id, goals, path, to_play)`。** 不是文件路径、不是行号、不是 session id。
4. **动作失败 ≠ 最终失败。** 动作内部可以反复 submit 被拒、看错误、再修；只有预算耗尽才记 `action_failed`，不建边。

三个时钟：

| 时钟 | 单位 | 是否进树 |
| --- | --- | --- |
| 证明时钟 | commit（内核接受） | 是，一条边 |
| 计划时钟 | plan（agent 心里的 3–5 步） | 否，作为 prior/intent |
| 工具时钟 | tool call | 否，动作内部 |
| 训练时钟 | tactic span | 只对 span 算 CE |

## 2. 目标架构

```text
CPU: MCTS（复用 alphaproof/mcts）
  └─ AgenticEnv.apply(node, commit)
       ├─ LeanSession / apply_block / focus / verify（v1.1.0）
       └─ AgentExecutor
            ├─ OpenCode v2 session（prover）
            ├─ 工具：read/grep/glob/bash/websearch/edit(scratch)
            │        + lean_state / lean_submit_step / lean_env_delta / lean_search
            └─ 返回一个 commit + trace
GPU: /eval（proposal：K 个 action sketch + logprob + d_hat）
     train offline（CE on commit spans + 64 桶 value）
```

**提案便宜、执行昂贵**：

- MCTS 扩展时先走 `/eval`（无工具、单次调用）拿 K 个候选 sketch；
- 选中的一个才开 OpenCode session 执行；
- 这样 logprob 有定义，成本可控，也不会把多轮 episode 的 logprob 硬凑成一个数。

## 3. 形式定义

### Node

```text
Node = (env_id, goals[], path, to_play)
env_id = hash(lean_version, mathlib_rev, imports, helper decls, git tree)
goals  = 当前剩余 goal（每个存 pp + 局部上下文）
path   = 根到这里的 commit 序列（零 LLM 重放）
state_key = hash(env_id + canonical(goals_pp))
```

- 一个 goal：OR；commit 分裂出 k 个 goal：AND + k 个 focus 子节点（沿用 `focus_goal i`）。
- 同一 goal 文本在不同 env 下是不同节点；没有 `env_id` 的去重是错的。

### Action

```text
Action = 一次 agent episode（有预算）+ 唯一出口 commit
commit.kind ∈ {prove, build, ask}
  prove: 在聚焦 goal 的 sorry 位置写 tactic block，内核通过
  build: 新增/修改 def/lemma/import → 新 env_id（不是证明边）
  ask:   向外部要定义/形式化来源 → 只记录，不改环境
```

粒度：

- 一次只聚焦一个 goal（先 `focus`）；
- block ≤8 条 tactic；超过就拆成多次 commit；
- `step_cost = 实际 tactic 数`；`d(s)` 仍以 tactic 为单位，旧价值头不用重训口径。

### 失败语义

- 动作内 `lean_submit_step` 返回 `{ok:false, errors}`：agent 继续改，**不建边、不扣搜索预算**；
- 预算耗尽仍未 accepted：记 `action_failed` attempt，不建子节点；
- accepted 后**冻结节点**，同一节点不能再提交第二次（原子性）。

## 4. 标准件（5 种 JSONL）

```text
node.v1        node_id, parent_id, env_id, goals[], path, to_play
action.v1      action_id, node_id, kind, plan_id, model, session_id,
               budget, tool_calls[], started/ended, tokens, cost
commit.v1      file, goal_path, tactics[], byte_span, claimed_goals[],
               kernel{ok, axioms}, step_cost
transition.v1  action_id, accepted, reject_reason, child_ids[],
               attempts[]（每次被拒的 submit + 错误）
training.v1    prompt, action_text, logprob, write_spans[], value_target,
               trace_ref（大 trace 不内联）
```

训练件示例：

```json
{"schema":"alphaproof.agentic.training.v1",
 "problem_id":"pell-01","node_id":"n7","env_id":"9f2c...",
 "prompt":{"state_pp":"x y : N, h : step x y |- x^2 = 2*y^2 + 1",
           "goal_path":[0],"tools":["read","grep","bash","lean_submit_step"]},
 "action":{"text":"simp only [step]; nlinarith [h]","kind":"prove","tactics":2},
 "logprob":{"sum":-2.71,"source":"proposal","model":"qwen3.5-4b"},
 "write_spans":[{"file":"Problems/Pell.lean","start":412,"end":449,"kind":"tactic"}],
 "value_target":-2.0,
 "outcome":{"accepted":true,"axioms":["propext","Classical.choice","Quot.sound"]},
 "trace_ref":"actions/000123.json"}
```

两条硬规则：

1. **大 trace 与训练件分离**；`training.v1` 只留 `trace_ref`。
2. **只对 `write_spans` 算 CE**；bash/grep 的 token 全部 `-100`，否则在教模型“聊天”。

## 5. OpenCode v2 接入

### 5.1 插件（`alphaproof-agentic`）

位置二选一：

- 项目：`<repo>/.opencode/plugins/alphaproof-agentic/index.ts`
- 全局：`~/.opencode2/config/opencode/plugins/alphaproof-agentic/`

骨架：

```ts
import { Plugin } from "@opencode/plugin"

export default Plugin.define({
  id: "alphaproof.agentic",
  async setup(ctx) {
    await ctx.tool.transform((editor) => {
      editor.add({
        name: "lean_submit_step",
        description: "提交一个 proof step；内核接受后结束本动作",
        input: {
          type: "object",
          properties: {
            file: { type: "string" },
            goal_path: { type: "array", items: { type: "number" } },
            tactics: { type: "array", items: { type: "string" } },
          },
          required: ["file", "goal_path", "tactics"],
          additionalProperties: false,
        },
        execute: async (input, context) => {
          const res = await fetch("http://127.0.0.1:PORT/commit", {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ session: context.sessionID, ...input }),
            signal: context.signal,
          })
          return { content: await res.text() }
        },
      })
    })

    await ctx.session.hook("context", (event) => {
      event.system.push({ type: "text", text: PROTOCOL })
      delete event.tools.write   // 默认只允许 scratch 写；prover 不开全量写
      event.options.temperature = 0.2
    })
  },
})
```

工具清单：

| 工具 | 作用 |
| --- | --- |
| `lean_state` | 读当前 node 的 goals/context（只读） |
| `lean_submit_step` | **唯一证明出口**：提交 tactic block → 内核 elaborate → 返回新 goals 或错误；accepted 后冻结节点 |
| `lean_env_delta` | 提交 helper 定义/新文件 → 新 `env_id`（build 动作） |
| `lean_search` | mathlib grep + `exact?` / `apply?` / loogle，鼓励“查而不是背” |

### 5.2 三个 agent

```text
alphaproof-proposer : 无工具，只输出 K 个 action sketch（JSON + logprob）
alphaproof-prover   : read/grep/glob/bash/websearch/edit(scratch) + lean_*
alphaproof-builder  : 额外允许写 Problems/ 与 Contrib/，走 lean_env_delta
```

`opencode.json` 里用 `agents` 定义，`permissions` 按目录限制；`plugins` 加载插件。

### 5.3 三层写权限

| 区域 | 例子 | 规则 |
| --- | --- | --- |
| A 草稿区 | `scratch/`、`/tmp` | 随便写，不进 env |
| B 证明洞 | `Problems/X.lean` 的 `sorry --@node` | **只能**经 `lean_submit_step` |
| C 环境区 | `Problems/` 新文件、`Contrib/`、mathlib | 只能经 `lean_env_delta`，产生新 `env_id`；v2.0 默认 mathlib 只读 |

### 5.4 会话生命周期

- 一个搜索路径复用一个 session；分支时 `POST /api/session/{id}/fork`；
- 每次 prompt 由 orchestrator 注入：node 状态 + 预算 + 协议；
- 预算：`max_tactics_per_action=8`、`max_tool_calls`、`max_wall_s`、`max_submits=12`、`repair_rounds=3`；
- 超时用 `POST /api/session/{id}/interrupt`；
- 结束不靠“最后一段文本”，靠 `lean_submit_step` 的 accepted 事件。

### 5.5 提案通道与执行通道

```text
POST /eval           → K 个 sketch（tactic/自然语言意图 + logprob + d_hat）
POST /api/session    → 执行选中的 sketch
GET  /api/session/{id}/context → 审计 trace
```

- 提案可用本地 vLLM（Qwen3.5-4B）或云端；必须有 `logprobs`；
- 执行用 OpenCode v2（4B/9B）；
- 如果落稿与提案不一致，记 `intent_drift`，训练用落稿文本**重新打分**，不用提案 logprob。

## 6. 从 v1.0.0 / v1.1.0 迁移

| 项 | 现状 | v2.0.0 改动 |
| --- | --- | --- |
| `/eval` | 单条 tactic，64 token | 保留为 proposal；加 `action_kind`、更长输出、stop 序列；不要硬改旧语义 |
| `Transition` | prompt/action/value_target/... | 加 `extra.write_spans/trace_ref/commit_id/step_cost/model_id/enable_thinking` |
| `compute_value_target` | 每条边 `-1` | 改成 `-edge.step_cost`；`Edge.step_cost` 从 property 改成字段 |
| `lmc apply` | 一条 tactic | 加 `apply_block`（原子多 tactic，只返回最终状态） |
| `state_key` | 目标哈希 | 加 `env_id` |
| shell | 每题一进程 | 加 env 版本/重建；builder 模式另开会话 |
| learner | 原始 prompt/action | chat template + assistant-only labels + 真梯度累积 + `.float()` CE |
| LoRA | 7 个投影 | 加 GDN：`in_proj_qkv/z/a/b/out_proj` |
| HF loader | `AutoModelForCausalLM` | Qwen3.5 用 `Qwen3_5ForCausalLM` 或 key 映射 |
| pool join | `(search_id,state_hash,action)` | 加 `commit_id`（agentic 动作不是单 tactic） |
| 冻结规则 | CE 逻辑冻结 | v2 是主线版本升级，需显式拍板；不要偷偷改 |

## 7. 分阶段（每阶段可独立验收）

### B0 · 基线修复（不碰 agent）

- 修 `docs/10-25-分析/1` 的 6 个问题：真梯度累积、bf16 CE、value 符号断言、SFT 去重、`λ` vs `value_lr`、`N_v`；
- 用 Qwen3.5-4B 跑通 `gpu-serve smoke` + 1 次 offline；
- 记录 baseline：tactic CE、value MAE、生成合法率。

验收：`loss` 有限、`missing/unexpected=[]`、显存与预期一致。

### B1 · 协议 + mock parity

- 新建 `alphaproof/agentic/`：`protocol.py`（dataclass + JSON schema）、`executor.py`（fake agent）、`env.py`（`LeanEnv` 包装）；
- 用 `PellMockEnv` 做端到端：每个 episode 只 commit 一 tactic；
- 与现有 `MCTS` 逐节点对比。

验收：树完全一致；被拒后重试只产生 1 条边、2 条 attempt；`len(edges)==len(accepted commits)`。

### B2 · 真 Lean + 脚本化 agent

- 给 `lmc` 加 `apply_block`；`AgenticEnv` 走真实会话；
- agent 用脚本（不接 LLM）提交 Pell 的 3 步；
- 产出 `node/action/commit/transition` + `strict_receipt`。

验收：Pell solved；从干净 checkout 只用 commits 重放通过；`sorry` 负例 FAIL。

### B3 · 真 OpenCode + 本地 4B

- 插件 + 3 个 agent + orchestrator；
- 跑 1 道小题：提案 4B，执行 4B；
- 记录 token/工具调用/墙钟/修复率。

验收：一次完整 episode 有 accepted commit；`training.v1` 的 `write_spans` 与文件字节一致；`trace_ref` 可回放。

### B4 · CE 训练 + 多题序列

- 按 wave 收集 `training.v1`，只对 tactic span 算 CE；
- value target 用 `step_cost` 口径；
- 先在 5–10 道题上跑 1 步 offline，再扩到课程。

验收：CE 下降且生成合法率不降；`value MAE` 可比；每解题 token 成本有记录。

### B5 · 规模化（可选）

- 9B-AWQ 教师/执行；builder mode；并行扩展（每候选一个 session + worktree）；
- 失败修复对：`(error, bad_tactic) → good_tactic` 作为额外 SFT。

## 8. 训练路径（v2 的 CE 到底学什么）

```text
prompt = chat_template(system + state_pp + goal_path, enable_thinking=False)
action = commit 的 tactic block 文本（不含 tool call、不含 thinking）
labels = prompt 段 -100；只对 action token 算 CE
value  = -d(s)，d 以 tactic 为单位；step_cost = len(tactics)
```

三个必须：

1. **不要训练 tool-call token**；
2. **不要带 thinking 历史**（多轮只保留最终输出）；
3. **修复对是额外数据**：第一次被拒的错误 + 修正后的 tactic，是 v2 相对 v1 的核心增量。

logprob 两条路：

- 提案通道直接返回 `logprobs`（推荐）；
- 没有 logprob 时，对 `prompt+action_text` 做 teacher-forcing rescoring 回填。

## 9. 正确性与防作弊

agent 能写文件，就必须有闸门：

1. **命题锁**：目标声明的 type + imports 的 hash，任何改动直接拒；
2. **公理审计**：`#print axioms` 只允许 `propext / Classical.choice / Quot.sound`，出现 `sorryAx` 即失败；
3. **独立重放**：解出后从干净 checkout 只用记录的 commits 重建，`lake build` 通过才算 solved；
4. **diff 范围**：`prove` 动作只允许改指定 proof hole；其他文件改动必须走 `build`；
5. **env 版本**：所有 helper/import 变更都进 `env_id`，旧状态句柄不可跨 env。

## 10. 本地环境 / 云端

本地环境 3080 20G 的硬约束：

| 组合 | 权重 | 可行性 |
| --- | --- | --- |
| 0.8B + 4B | 11.1 GB | ✅ 实测总占用 17.4 GB |
| 9B-AWQ 单独 | 8.6 GB | ✅ 262K 上下文 16.7 GB |
| 9B-AWQ + 4B | 17.9 GB | ❌ 权重已接近上限 |

推荐：

- 开发/调试：0.8B（冒烟）+ 4B（提案/执行）；
- 评测/教师：只起 9B-AWQ；
- 训练：4B bf16 LoRA 是 20G 上限（14–18GB），9B 走云端。

## 11. 反模式

- 把 `bash/read/write` 当成树的边 → 分支因子 1，MCTS 退化；
- 让一个动作证完整道题 → 树变成线性脚本；
- 对 tool-call token 算 CE → 学会聊天，不是写证明；
- 相信 agent 声称的 goals → 必须用内核返回的状态；
- 不加 `env_id` 去重 → 换环境后同 goal 被误合并；
- 用多轮 episode 的“总 logprob”当 policy 目标 → 没有定义，梯度有偏；
- 不设 `max_tactics_per_action` → 宏动作漂移，价值目标单位混乱。

## 12. 开发顺序（照着做）

```bash
# 0) 读前置 skill 与文档
#    v1.0.0 / v1.1.0 / docs/10-27-分析/1-v1-1-agentic.md

# 1) 基线
cd ~/repos/10-4-alpha-proof
python3 -m pytest tests -q
python3 -m gpu_serve smoke --tiny

# 2) 起 Lean 会话
cd ~/repos/lean-mcts-cpu-server
python3 -m lmc.cli mcts-smoke

# 3) 起本地环境 4B（提案/执行）
bash /data/qwen35-small-throughput/scripts/up.sh both   # 8001/8002

# 4) 起 OpenCode v2
#    插件放 .opencode/plugins/ 或 ~/.opencode2/config/opencode/plugins/
#    agents: proposer / prover / builder
#    opencode models | grep local

# 5) 先 mock parity，再真 Lean，再真 OpenCode
```

代码落点：

```text
alphaproof/agentic/
  protocol.py     node/action/commit/training dataclass + schema
  executor.py     OpenCode session 调用、预算、trace
  env.py          AgenticEnv：apply(commit) → StepResult
  lean_bridge.py  /commit HTTP → lmc apply_block/focus/verify
  record.py       JSONL 原子追加 + id
scripts/agentic_smoke.py
tests/test_agentic_protocol.py
tests/test_agentic_parity.py
```

## 13. Definition of Done

- [ ] 工具调用不出现在树里；`len(edges) == len(accepted commits)`；
- [ ] 任意节点可从 `(env_id, path)` 零 LLM 重放，内核结果一致；
- [ ] 被拒的 submit 不建边，且能在同一 episode 内修复；
- [ ] 解出题从干净 checkout 重放通过，公理审计无 `sorryAx`；
- [ ] `training.v1` 每条样本有 logprob + 精确 `write_spans`；CE 只覆盖 span；
- [ ] `d(s)` 仍以 tactic 为单位，旧价值头可复用；
- [ ] 5–10 道 Lean 题的 wave 能跑完并产出 CE 回执。

## 14. 一句话

**v2.0.0 的难点不是“让 agent 会写 Lean”，而是“让 agent 的自由度不破坏 MCTS 的语义”；守住 commit 边界，剩下的都是工程。**
