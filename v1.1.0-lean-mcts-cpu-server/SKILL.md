---
name: v1.1.0-lean-mcts-cpu-server
description: 'AlphaProof 10-4 的 CPU 侧 Lean 会话与 MCTS 服务（v1.1.0）：持久 Lean 进程、状态句柄、任意历史状态分叉、失败回滚、focus 单目标、严格复验、Python PUCT、轨迹 store/export。当用户要改 Lean 会话协议、MCTS 搜索、轨迹落盘/导出、并发与进程池、或把 agentic commit 接进 Lean 验证时使用。触发词：lean-mcts-cpu-server, lmc, LeanSession, apply/focus/verify, 状态句柄, Lean 4 会话, PUCT, AND/OR, focus_goal, strict_receipt, lmc export, waves, shards, Lean 4.28, Reap, checkProof, 并发 Lean, 60G 内存。'
---

# v1.1.0-lean-mcts-cpu-server

一句话：**让 Python 用“状态句柄”在常驻 Lean 进程上做增量 tactic 执行、任意分叉、失败回滚和最终严格复验**；MCTS 树、调度、轨迹都在 Python 侧。

## 0. 什么时候用

用：
- 改会话协议（`apply/focus/verify` 等）、Lean preamble、shell 生成；
- 改 Python PUCT / AND-OR / focus 逻辑；
- 改 store 布局、`Transition` 导出、strict receipt；
- 加并发、进程池、watchdog、LSP 后端；
- 把 v2 的 agentic `commit` 接进 Lean 验证。

不用：
- 改 GPU 训练 / `/eval` / 值头 → 用 `v1.0.0-alpha-proof-gpu-training`；
- 设计 opencode v2 的 agent 协议 → 用 `v2.0.0-alpha-proof`。

## 1. 规范路径

| 用途 | 路径 |
| --- | --- |
| 活跃仓库 | `~/repos/lean-mcts-cpu-server`（`b9622f7`，2026-10-13） |
| gloway 快照 | `~/repos/lean-mcts-cpu-server.archived-20261013`（`lmc/` 与发布版逐字节相同） |
| 设计规格 | `~/repos/10-4-alpha-proof/docs/new-python-version-mcts-plan/` |
| GPU 契约 | 同目录 `02-architecture.md` §5 |
| Lean 环境 | `/data/projects/lean-4.28-reap`（Lean 4.28.0-rc1 + Reap `0090d73c`） |
| 热状态 | `~/lmc-run`（shells/logs）、`~/lmc-store`（轨迹），都在 ext4 |
| 基准报告 | `docs/BENCH-2026-10-07.md` |

环境变量：

```bash
export LMC_REAP_ROOT=/data/projects/lean-4.28-reap
export LMC_RUN_DIR=$HOME/lmc-run
export LMC_STORE=$HOME/lmc-store
export PATH="$LMC_REAP_ROOT/elan/bin:$PATH"
```

## 2. 进程与协议（实现版，以此为准）

一个会话 = 一个 `lake env lean <shell>.lean` 进程；shell 由题目文件生成，把证明体替换成 `lmcSessionLoop`，注入 `lean/lmc_preamble.lean`。

| op | 请求 | 响应 |
| --- | --- | --- |
| `ping` | `{id}` | `{ok, kind:"pong", states}` |
| `goals` | `{id, state}` | `{ok, num_goals, goals:[txt]}` |
| `apply` | `{id, state, tactic}` | `{ok, state, num_goals, closed, goals, state_key, elapsed_ms}` 或 `{ok:false, kind:"tactic", error}` |
| `focus` | `{id, state, index}` | `{ok, state, num_goals:1, goals, state_key}` |
| `verify` | `{id, state, script:[...]}` | `{ok, verified, steps}` |
| `close` | `{id}` | `{ok, kind:"closing"}`（随后退出） |

关键语义：

- **状态句柄**是会话内整数，指向 `Tactic.SavedState` 快照；不是文件，也不是可跨进程的 ID。
- `apply` 在**指定状态的全部目标**上执行一条 tactic；成功返回新句柄；多目标 → Python 建 AND 节点 + `focus` 子节点。
- **分支**：同一历史状态可反复 `apply` 不同 tactic，互不影响；失败会恢复原状态。
- `focus(state, i)` 把多目标状态收窄到第 i 个 goal（单目标 OR 节点），这是 agentic 动作的正确落点。
- `verify` 从根状态重放整段 script 并做内核 `checkProof`；这是唯一允许写 `solved: true` 的依据。
- 输出走 FIFO（`LMC_OUTPUT_FIFO`），因为 Lean task 线程的 stdout 会被缓冲；响应前缀 `@@LMC@@ `。
- 版本锁：Lean `v4.28.0-rc1` + Reap `0090d73c` + 补丁集；`open`/`versions` 必须校验。

> 注意 spec `03-lean-session-protocol.md` 写的是 `open/apply/goals/release/close` + 字符串句柄；
> 实际实现是 `ping/goals/apply/focus/verify/close` + 整数句柄 + 每题一个 shell。读代码时以 `lmc/session.py` 为准。

## 3. Python MCTS（`lmc/mcts.py`）

与 `alphaproof/mcts` 同一套官方语义：

```text
c_base=3200, c_init=0.001, tau=200, ps_c=0.01, ps_alpha=0.6,
c_AND=64, c_pen=32, gamma=0.99, max_nodes/max_steps 可配
Q = gamma^(-1 - V)；未访问子 Q = V(s) - c_pen；AND 探索项 × c_AND
```

- OR：任一子解出即解出；AND：全部子解出；focus 伪动作边代价 0。
- 扩展时 `apply` 成功 → 子节点；失败 → 不建边；同战术先验累加、同 `state_key` 合并。
- 多目标 → 子节点 `to_play=AND`，立刻挂 `focus_goal i` 伪子节点（先验 1/n，代价 0）。
- solved 后：`_mark_optimal` → `_compute_value_target_iter`（终端 0 / OR `-1+子` / AND `min`）→ `_collect_script`。
- `state_key` 当前是目标文本哈希，**没有环境版本**；v2 要加 `env_id`。

## 4. 轨迹 store 与导出

```text
$LMC_STORE/
  waves/<wave_id>/<problem_id>/<search_id>/
    job.json            # 题目/预算/版本三元组/policy_version/config_hash
    steps.jsonl         # append-only 事件流
    tree.json           # 节点/边/统计/is_optimal
    transitions.jsonl   # solved 时 extract_transitions（未含 logprob_old）
    result.json         # solved/status/best_script/计数/耗时
    strict_receipt.json # 独立整文件编译收据
  export/<wave_id>/
    shard-0001.jsonl
    manifest.json       # 计数 + sha256 + 版本三元组 + policy_version
```

`Transition` 是唯一训练口径：

```json
{"prompt":"<tactic state>","action":"<tactic>","value_target":-7.0,
 "kind":"proof","solved":true,"terminal_verified":true,
 "logprob_old":null,"reward":null,
 "extra":{"search_id":"...","state_hash":"...","policy_version":"vN"}}
```

严格复验：`best_script` 生成独立 `.lean`（禁止 sorry/admit），`lake env lean` 整文件编译；
失败则 `result.json` 的 solved 撤回为 `unverified`，**未复验样本不得进 CE 主线**。

## 5. 命令手册

```bash
cd ~/repos/lean-mcts-cpu-server

python3 -m lmc.cli smoke          # goals → 3 applies → verify → close
python3 -m lmc.cli mcts-smoke     # Python MCTS 端到端（Pell 第一课）
python3 -m lmc.cli latency --cycles 100
python3 -m lmc.cli scale --sessions 1,2,4,8 --cycles 10
python3 -m lmc.cli wave --problems 8 --workers 4
python3 -m lmc.cli compare        # 旧式整文件编译 vs 会话增量

python3 -m lmc.cli search --problem pell --budget 64
python3 -m lmc.cli catalog
python3 -m lmc.cli export
python3 -m lmc.cli verify
python3 -m lmc.cli status
python3 -m lmc.cli versions
```

产物：`$LMC_RUN_DIR/logs/lmc-bench-*.json`、`$LMC_STORE/...`。

## 6. 性能基线（同机同版本才有意义）

| 指标 | 实测 |
| --- | --- |
| 单会话混合负载 | 13.7 applies/s |
| 多会话 | N=4→40、N=6→54.6、N=8→58.1、N=12→69 applies/s（饱和），N=16 不再增长 |
| 波次 | 6 并发、20 题、20/20 solved + 内核复验，wall 26.6s → 45.1 题/min |
| 会话冷启动 | ≈6s（加载 Mathlib）；进程池预热可摊薄 |
| warm apply | 1–6ms（README 口径；p50 目标 ≤500ms） |

旧管线对照：40 题/106 次尝试，Lean 占 96.7%，单次整文件编译 ≈25.9s。新链路的核心收益是把“每次尝试一次编译”变成“每会话一次 + 每步增量”。

## 7. 开发 recipe

### 7.1 加一个会话 op

1. `lean/lmc_preamble.lean` 的 `runLoop` 加分支，返回 `okMsg/errMsg`，字段与现有风格一致；
2. `lmc/session.py` 加 request 方法 + dataclass 结果；
3. `lmc/cli.py` 加命令（如果要暴露）；
4. `tests/` 加 mock session 测试；真 Lean 加一个 smoke；
5. 协议版本号 +1；`docs/new-python-version-mcts-plan/03` 同步（spec 与实现不要继续漂移）。

### 7.2 加一道题 / 一个课程

- 题目文件必须有可替换的证明体：`reapTrainingMCTS` / `reapMCTS` / `sorry` 之一；
- `lmc/shells.py::build_shell` 会替换成 `lmcSessionLoop`，并在最后一个 import 后注入 `import ReapRuntime`、`import Lean.Data.Json.Parser` 和 preamble；
- manifest 行至少含 `problem_id / theorem_file / policy / budget`；
- 课程题放 `examples/`，不要写死到 `lmc/policy.py`（脚本化 policy 只用于冒烟）。

### 7.3 加 `apply_block`（v2 agentic commit 的关键）

当前 `apply` 只跑一条 tactic；agent 的一个 commit 往往是多行 block。推荐新 op：

```text
{"op":"apply_block","state":h,"tactics":["intro x y h","simp only [step]","nlinarith [h]"]}
→ {"ok":true,"state":h2,"num_goals":0,"closed":true,"state_key":"...","steps":3}
```

语义：**原子执行**——任一条失败则回滚到 `h`，不产生中间句柄；成功只返回最终状态。
这样 Python 侧才能把“一个 block”当成一条边（`step_cost=len(tactics)`），而不是 N 条边。
实现要点：在 Lean 侧用 `runTactic` 逐条执行并保存起始 snapshot；失败 `restore`；成功只登记最终 handle。

### 7.4 加 `env_id` / 环境版本

v2 的节点身份必须是 `(env_id, goals)`，不能只看 goal 文本：

- `env_id = hash(lean_version, mathlib_rev, imports, 新增 helper 声明, git tree)`；
- `apply` / `focus` / `verify` 的响应加 `env_id`；
- `state_key = hash(env_id + canonical(goals_pp))`；
- shell 重新生成（新 import / 新 helper）时递增 `env_id`，旧状态句柄不可跨 env 使用。

### 7.5 进程池 / watchdog（STATUS 里未完成）

现状：一题一进程，启动 ≈6s。要上量：

- 预热 N 个会话，按题目 shell 复用；会话失效重建；
- 心跳 10s，连续 3 次无响应 → SIGTERM → 5s → SIGKILL；
- 搜索与会话绑定，会话失效则搜索失败落盘（不要静默续跑）；
- 内存护栏：可用内存 < 6GB 拒绝新搜索；
- 绑核 + `nice`（Ryzen 5700X，8C/16T，和他人共用）。

### 7.6 LSP 后端（路线 B）

如果 Reap 内部路线（A）不可维护，可切 `lean --server` + 每状态文件/快照：

- 优点：与 Reap 版本解耦、稳定；
- 代价：每步文件同步、goals 走 RPC、分支文件管理复杂；
- 先用路线 C（从根重放）做对拍裁判，100 组 `(state, tactic)` 结果一致再切。

## 8. 坑清单

1. **每题一进程**：没有 `open`，换题要重建 shell + 新进程；不要假设会话可跨题复用。
2. **`apply` 作用于全部目标**：想只证一个 goal，先 `focus`；否则会把 tactic 套到所有子目标上。
3. **失败会回滚**：`apply` 返回 `ok:false` 时状态不变，但 Python 侧仍要记录 attempt（负样本/修复数据）。
4. **`state_key` 只是目标哈希**：没有 env 版本，换 import/helper 后必须重建 key。
5. **FIFO 不是可选**：Lean task 线程 stdout 缓冲，必须走 `LMC_OUTPUT_FIFO`，否则 `request` 会超时。
6. **exfat 不能放 venv/热状态**：`/data` 是 exfat；venv、`LMC_RUN_DIR`、`LMC_STORE` 放 ext4。
7. **严格复验不能省**：`verify` 要整文件编译 + `checkProof`；`sorry`/`admit` 必须 FAIL。
8. **版本漂移**：rc1 / 正式版 / 补丁集不一致时收据不可比；`open`/`versions` 强校验。
9. **kill -9 测试**：搜索中杀 worker，必须搜索失败落盘、池 ≤5s 恢复、无僵尸。
10. **`lmc store` 是 append-only**：`steps.jsonl` 只追加；`tree.json/result.json` 用临时文件 + rename 原子写。

## 9. 测试分层

| 层 | 内容 |
| --- | --- |
| L1 | mock session：协议字段、错误码、超时、半行/乱序、FIFO |
| L2 | MCTS 语义：`tests/test_mcts_parity.py` + 迭代版 vs 递归版逐节点一致 |
| L3 | 真 Lean 单题：Pell solved + 严格复验 PASS；注入 `sorry` 必须 FAIL；同状态 8 候选分叉不串扰 |
| L4 | 池与故障：kill -9、apply 超时、版本不匹配、内存护栏 |
| L5 | 数据闭环：`lmc export` → `update_offline` 1 步；merge logprobs → `update_online` 1 步 |

## 10. 文件地图

```text
lmc/session.py      LeanSession：启动、FIFO、request/apply/focus/verify/close
lmc/mcts.py         PUCT、AND/OR、focus、backprop、value_target 迭代版
lmc/shells.py       题目 → 会话 shell（替换证明体 + 注入 preamble）
lmc/store.py        $LMC_STORE：原子写、catalog、export、strict receipt
lmc/eval_client.py  GPU /eval 客户端（重试 + -40 兜底）
lmc/bench.py        smoke / latency / scale / wave / compare
lmc/cli.py          命令面
lean/lmc_preamble.lean  会话循环 + apply/focus/verify 实现
```

## 11. 一句话

**这个服务的价值不是“跑得快”，而是“状态可分支、失败可回滚、结果可严格复验、轨迹可导出”；改它之前先保住这四条。**
