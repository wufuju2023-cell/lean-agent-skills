---
name: model-p2m-test
description: 用 prove2me 题库对「能作为自由 agent 做 Lean 证明」的模型做端到端评测：分层抽样 T1–T5、bench_blind 盲测环境（L0 脱敏 + L1 权限 + L2 guard，可选 --l3）、run_eval.sh 启动、编译/无 sorry/陈述不变三判据、失败的六类归因，以及与价值头 d_hat 的分解阈值接口。同时记录 owner 的立场：ICL 能力必须用 MCTS+CE 内化、要在 ICL 阶段塑造多智能体风格、大定理先自证再分解成本地 mission、资料不足时不许把 Langlands 之类结论当公理而应检索并入池；搜索单位是 mission 而非单步 tactic（任务分解即状态转移、mission-level MCTS、main_pool/sub_pool 掩码）。Use when designing or running a prove2me eval for a free-form Lean agent, when deciding whether a model is eligible, when sampling tiers or building blind envs, when scoring pass@1 / 分解率 / 检索率 / 池命中率, or when attributing a failure to decomposition vs retrieval vs missing knowledge. Triggers: model-p2m-test, p2m 评测, 自由 agent Lean, bench_blind, run_eval.sh, MCTS+CE, mission-level MCTS, 任务分解即状态转移, main_pool, sub_pool, 掩码, AND(children), 内化, 多智能体风格, 子智能体, 分解率, 检索率, 池命中率, guard 拦截, 越权尝试, 价值头, d_hat, 500 步, 费马大定理, Langlands, MinerU 入池, T1-T5.
---

# model-p2m-test：自由 agent × prove2me 端到端评测协议

**一句话**：先确认模型有资格当自由 agent，再把它丢进盲测题里看它**自证、分解、检索、入池**做得怎么样；MCTS+CE 是训练侧，评测只负责给出可归因的轨迹。

> **立场声明**：§1–§5、§8、§9 是 **owner 的判断**（设计决策），不是社区共识。照做前先能复述理由；
> 有反例就改这一节，不要默默偏离。所有数字要么有出处，要么写 `TBD` 并注明在哪测。

## 0. 三十秒

| 要做的事 | 用这个 | 位置 |
| --- | --- | --- |
| 选题、脱敏、建盲测环境 | `guard/l0l1/make_env.py` | `./guard/l0l1/` |
| 起一次盲测会话 | `guard/run_eval.sh <env> "<prompt>" [--l3]` | `./guard/` |
| 判分（编译 + 无 sorry + 陈述不变） | `p2m_check` / `lake env lean` | §6.4 |
| 分解成子任务 | `p2m_split` → `team_send` | `prove2me-agent` 插件 |

## 1. 目标模型画像（owner：只选一类模型）

**只选“本身就能作为自由 agent 做 Lean 证明”的模型**：自己决定 read/grep/编辑/编译/检索/派子任务并对结果负责，不是 tactic 续写器或单轮聊天模型。

| 准入项 | 判据 | 不满足的后果 |
| --- | --- | --- |
| 工具调用可用 | 一次会话里 ≥1 次成功 tool call | 退化成聊天，pass@1 无意义 |
| 多轮自恢复 | 编译错误后能改一版再编译 | 只能测“一次成”，与 MCTS 无关 |
| 自主检索 | 主动 `websearch`/`lean_search`，不等喂 | 检索率恒 0，天花板锁死 |
| 长任务不崩溃 | 50+ 工具调用后仍守住 workspace 与命题 | 数据全是 thrash，不可归因 |
| 能读 Lean 错误 | 把 `unknown identifier` 变成下一步动作 | 归因全落“知识缺失”，其实是不读错 |

历史基线（`/data/WSP/RESULTS.md`）：Qwen3.5-0.8B **不满足**前两条——会正确调 `p2m_next` 随后去改无关文件；只能跑受限 tactic 循环（5/10、6/10），本协议下 pass@1 写 `TBD`，不得当能力数据。

## 2. 为什么训练必须是 MCTS+CE（owner 的核心观点）

当时的 LLM 本质是 **in-context learner**：推理期得到的能力只活在这次 context 里，下一题回到原点。唯一能留下的办法是**内化到参数**，路径就是搜索→后验轨迹→CE：

```text
大量 prove2me 题 → MCTS（分支/回滚/复验）→ 只留内核接受的 commit
                 → CE 更新（只对 tactic span 算 loss）→ 下一轮搜索更强
```

两条推论直接决定评测怎么设计：

1. **评测要产出轨迹，不只产出分数**：`node/action/commit/transition` 是下一轮训练的原料；工具调用只计数，不算搜索步数。
2. **动作失败必须可修**：被拒的 submit 不建边但留下 `attempts`，修复对是核心增量。

## 3. 多智能体风格要在 ICL 阶段塑造（owner 的观察）

很多模型在证明大定理时会**自发使用子智能体**——Anthropic 证费马大定理就用了大量子智能体分工（模形式、Galois 表示、Langlands 侧引理各一批），主 agent 只做计划与合流。所以分解不是兜底技巧，而是**要被训练出来的行为**：ICL 轨迹必须含“决定分解 → 写子任务契约 → 派发 → 收结果 → 合流/失败传播”，评测侧看**分解率**与分解是否有效，而不是只看最终 pass。

## 4. 主 agent 行为规范（owner：先自证，超复杂度才分解）

```text
接到目标 → A 自己试（预算 B0 / d_hat）
         → B 分解：p2m_split → team_send(children, queue) → status=split
         → C 合流：p2m_submit / 失败传播
```

| 触发分解的信号 | 不该分解的情况 |
| --- | --- |
| `d_hat > 500`（§9） | 还在一轮自证预算内 |
| 需要两套互不相干的数学（Langlands + 模形式） | 只差一条 `simp`/`exact` |
| 子目标本身是题库里的定理（DAG 规则强制） | 子目标只是主目标的改写 |
| 同一 goal 连续 3 次无进展 | 分解会破坏命题锁（陈述不可换） |

- **先自证，但要先看门限**：`d_hat ≤ 500` 才“先试”；`d_hat > 500` 一开始就分解，不算“一上来就分解”（§4.5、§9）。
- **深度上限 3（默认，配置项）+ 子任务契约**：触上限才需父会话批准；goal 一句话 + 允许的 import + 验收命令。
- **失败传播**：子 mission 失败必须回到父 `attempts`，不许自己编一条引理。

### 4.5 任务分解即状态转移（mission-level MCTS）

owner 的设计：搜索的单位是 **mission**，不是单步 tactic。人类证明本来就成块书写；AlphaProof/REAP 的单步动作在这个框架里降级为**可选模式**。它与 tactic 级搜索共用一套 node/action/commit 日志，区别只在 action 粒度与重采样触发器；评测据此分开统计“块内失败”与“分解失败”。

```text
state  = {env, mission_id, Lean context, goal}
action = 一次 agent 回答：(a) block 对当前 goal 给一段证明块 | (b) split 分解成若干子 mission
split 后状态 = AND(children)；此时不立刻重采样，下一次 K 采样由「子 agent 返回结果」或「证明块尝试结束」触发
```

| # | 规则 | 细节 |
| --- | --- | --- |
| 1 | 分解后状态是 AND(children) | 原 goal 等价于“所有子 mission 都被证明”；状态已变，但**不立即重采样**，等子 agent 回来或证明块收尾 |
| 2 | 门限只压父层 | 价值头 `d_hat > 500` 必须分解；**子 mission 不要求 `d_hat ≤ 500`**，子 agent 可继续分解，深度由配置上限（默认 3）控制 |
| 3 | 深度靠配置，不靠语义 | 浅层大扇出是正常形态：Anthropic Fable 5.2 重证费马定理，一上来就切了 60 个 mission |
| 4 | 两套池严格分离 | `main_pool`＝主 agent 自己的决策 + 它发出的 mission 契约 + 子 agent 返回的**摘要**；`sub_pool`＝每个子 session 的完整轨迹 |
| 5 | main_pool 必须掩码 | CE 更新时掩掉工具结果、子 agent 返回内容、system prompt；不掩就会把“调用子 agent”学成捷径 |
| 6 | AND/OR 只记录 | 不做严格 AND-OR 树/严格 AND 回传；主结构是 mission DAG（prove2me 风格），父节点价值由子节点**聚合** |
| 7 | 复用与去重 | mission 以 `sha256(env, statement_formal)` 去重；同一 env 共享一个 Lean 项目与 olean 缓存（编译加锁）；同一分解里重复的子 mission 先去重再派发 |
| 8 | 最小 action 是 N 步块 | `action_block_steps` 默认 10（候选 10/20/50/100）：一次采样最多贡献 N 步；块内完全自由（计划/骨架/编译反馈/工具/联网），只有**最终提交的证明块**不超过 N 步 |
| 9 | 转移靠 diff 判定 | 应用后比较新旧 `(context, goal)`：变了 → 状态转移 + 下轮 K 采样；没变 → 空动作/失败。`d_hat ≤ N` 时一次采样即可完成，**不进多轮 MCTS 也无学习信号**（有意为之：假定基座在自由 agent 下已能做这种难度） |
| 10 | 课程抬 N | `action_block_steps` 随模型变强提高（100 → 200 → … → 1000）；若 N=100/200/300/400 都能全解，就对 ≤1000 步的 mission 停止产信号 |

## 4.6 只有终点信号，没有分解奖励（owner）

学习信号全部来自专家迭代 + teacher forcing，且**只对成功的轨迹**算 CE：

- 主 agent 轨迹的终点 = 原始 `(context, goal)` 被证明；预算耗尽仍未完成 = 失败。失败轨迹只做诊断记录，**不进 CE 后验池**。
- 拆成 60 个 mission 最后成功，信号来自“最终证明成功”，不是“拆得好”；规划能力靠“哪种计划能走到终点”被**间接**学到。
- 明确写：**不存在** `decomposition_bonus` / `subagent_reward`；子 mission 成功不单独给奖励。

## 5. 资料不足时的行为（owner：不许把大结论当公理）

典型场景：费马大定理的形式化要吃掉大量 Langlands 相关结论。**正确行为不是 `axiom langlands`**：

| 级别 | 动作 | 记录字段 |
| --- | --- | --- |
| 1 本地池命中 | 池里已有该引理/定义 → 直接引用或顺手证明 | `pool_hit: true`, `pool_entry` |
| 2 主动检索 | 本地没有 → **必须 web search**（论文/讲义/nLab/Stacks），PDF 用 MinerU 转 md | `retrieval: [...]`, `source_url` |
| 3 明确降级 | 找不到形式化来源 → 显式声明缺口，不用 `axiom`/`sorry` 混过去 | `gap: "<缺什么>"`, `degraded: true` |

两个池（位置 TBD，owner 未定；建议 `<POOL>/md`、`<POOL>/code`）：**md 池**放论文/书/讲义，走 `mineru-pdf-to-md-to-epub`；**代码池**放 Lean 项目/脚本/notebook，单独一池。**是否持久化入池由模型判断**：一次性、与本题无关的不入池，判据是“下次同类题还会用到”；入池带来源、许可、抓取时间。

## 6. 测试流程

### 6.1 分层抽样（T1–T5）

| 方案 | 每层题数 | 用途 | 总量 |
| --- | --- | --- | --- |
| 小样本 | 8 | 冒烟 / 换模型第一轮 | 40 |
| 正式 | 12 | 出一份可比较的表 | 60 |

- 只用 `data/bench_blind/T{1..5}.jsonl`（已去 `theorem_id/url/fq_name/id`）；固定 seed，抽到的 `(tier, bench_id)` 落 `state/runs/<run>/sample.tsv`，保证可复算。
- T2–T5 大量题 import 平台 `Definitions.*`，本地编不过 → 只抽 `local_compilable`，或先编依赖；每层实际条数写进报告，不要默认“每层 8/12”。
- 小样本只报**计数与区间**，不报“能力提升 X 个百分点”。

### 6.2 建盲测环境（L0 脱敏）

```sh
ROOT=.; RUN=mp2m_$(date +%Y%m%d_%H%M%S); mkdir -p $ROOT/state/runs/$RUN $ROOT/eval/$RUN
python3 - "$RUN" <<'PY'          # 每层 8 题，seed 固定 → sample.tsv（只取 local_compilable）
import json, random, sys, pathlib
random.seed(20261114); run = sys.argv[1]
with open(f"./state/runs/{run}/sample.tsv", "w") as f:
    for tier, k in {"T1":8,"T2":8,"T3":8,"T4":8,"T5":8}.items():
        rows = [json.loads(l) for l in open(f"./data/bench_blind/{tier}.jsonl")]
        for r in random.sample([r for r in rows if r.get("local_compilable", True)], k):
            f.write(f"{tier}\t{r['bench_id']}\n")
PY
while IFS=$'\t' read -r tier bid; do      # 一题一目录
  python3 $ROOT/guard/l0l1/make_env.py --bench-id "$bid" --tier "$tier" --out $ROOT/eval/$RUN/$tier-$bid --force
done < $ROOT/state/runs/$RUN/sample.tsv
```

`make_env.py`：定理名改成 `solution`（去 namespace/docstring/`context_pre`）、只留 `statement_formal` + 必要 imports、写单 commit 的 git、把 `env.json/secrets.json` 放在 `repo/` **外面**；产物里搜不到 `fq_name|theorem_id|bench_id`。

### 6.3 启动

```sh
# 正式档：L1 权限 + L2 guard（P2M_GUARD=on），以当前用户运行
bash $ROOT/guard/run_eval.sh $ROOT/eval/$RUN/T1-<bench_id> \
  "Prove \`solution\` in Problem.lean. Verify with \`lake env lean Problem.lean\`. Do not change imports or the statement. Stay inside this directory." \
  --model opencode-go/deepseek-v4.1-flash
bash $ROOT/guard/setup_sandbox.sh                                  # 仅 L3 需要，一次性
bash $ROOT/guard/run_eval.sh <env> "<prompt>" --l3 --model <id>    # 独立 uid + 只许本地代理出网
```

`run_eval.sh` 固定 `--standalone --auto --agent p2m-eval --format json`，并 `cd <env>/repo` + `env PWD=<env>/repo`。换模型只改 `--model`；对照组用 `make_env.py --profile eval-open`。

### 6.4 判分（三条同时成立）

| 判据 | 怎么查 | 谁执行 |
| --- | --- | --- |
| 编译通过 | `lake env lean <file>` 无输出 | 父会话 `p2m_check`（自带 env pin） |
| 无 sorry/自定义公理 | `#print axioms` 只有 `propext/Classical.choice/Quot.sound` | `p2m_check` 规则 A/B |
| 陈述不变 | 题面 hash 与 `make_env.py` 记录的一致 | 父会话对比 `env.json` |

子智能体**不判自己的分**：只回传 proof 文本，父会话编译，失败原文回灌（`repair_rounds=3`）；不看“agent 说它证完了”。

### 6.5 guard 与越权统计

`guard.log` 每行 `{ts, hook, tool, action, resource, decision}`，`decision ∈ {allow, deny, rewrite, inject}`。

```sh
grep -c '"decision":"deny"'    $ROOT/guard/guard.log   # 被拦次数
grep -c '"decision":"rewrite"' $ROOT/guard/guard.log   # 查询被改写次数
grep '"decision":"deny"' $ROOT/guard/guard.log | head  # 逐个看是哪一类
```

要分开记**被拦次数**（guard 生效）与**越权尝试次数**（模型有意图，哪怕被拦）。`decision=rewrite` 说明模型确实想搜答案站：既证明防线生效，也说明“检索行为跑偏”。

## 7. 指标定义

```text
pass@1      = #{三判据全过} / #{该层题数}             一条轨迹、不重试、不看参考证明
分解率      = #{触发过 p2m_split 的 mission} / #{领取的 mission}
检索率      = #{至少一次 websearch|webfetch 的 mission} / #{mission}
池命中率    = #{证明里实际引用到池中条目} / #{声称需要外部资料的次数}
guard 拦截率 = #{decision=deny} / #{工具调用总数}
越权尝试率  = #{命中黑名单的尝试} / #{mission}
修复率      = #{compiler error 后改对} / #{出现 compiler error 的 mission}
中位墙钟    = median(ended - started)                  单位 s，超时样本单列
```

- 每个指标都写**分子/分母**；跨 run 先对齐分母再比。`检索率` 用**原始意图**算（guard 改写查询不算“没检索”）；`池命中率` 的分母是“模型声称需要外部资料”的次数。
- pass@1 与 pass@k 分开报；`k>1` 要说明重试是否共享 workspace。
- pass 率必须按**是否需要多轮采样**拆两栏报：`d_hat > N`（进 MCTS）与 `d_hat ≤ N`（一次采样、无学习信号，§4.5 规则 9）。合在一起报会被无信号带稀释，看着像“模型没学会”。

## 8. 失败归因（六类，必选其一）

| 类别 | 判据 | 下一步动作 |
| --- | --- | --- |
| 直接可证 | 未分解未检索，一两次修复即过 | 收成正样本（最短轨迹优先） |
| 需分解 | 自证预算耗尽，`p2m_split` 后子任务全过、合流成功 | 收成 DAG 样本；调分解触发器 |
| 需检索 | 分解也不动，`websearch`/池命中后过 | 收“检索→动作”样本；补池 |
| 需外部定理 | 缺库外结论，且网上无形式化来源 | 记 `gap`；不判模型错，改题库/课程 |
| 知识缺失 | 读不懂陈述/定义，动作方向随机 | 补基础课数据；该 tier 对其超纲 |
| 循环 | 同一动作 ≥3 次或 goal 文本不变 ≥5 步 | 硬失败；harness 介入（`exact?` 兜底） |

归因只认**证据**：工具调用、编译错误、guard 日志。一个 mission 可多标签，但要有主标签。

## 9. 与价值头的接口

64 桶价值头在 `/eval` 返回 `value.v` 与 `value.d_hat`。**`d_hat` 是 mission 级的“还要写多少块/多远”的剩余估计，不是 tactic 步数**（`v = -d_hat`，契约见 `v1.0.0-alpha-proof-gpu-training`）。门限按 mission 粒度评估，且**每次子 agent 返回都重估一次**（§4.5）：

```text
d_hat ≤ 500  → 允许硬证；d_hat 记进 mission，作为 value target 的对照
d_hat > 500  → 该 mission 强制分解，不许硬证（owner 设定）
d_hat 不可用  → 用自证预算 B0 兜底；B0 数值 TBD（在 §6 的 run 里标定）

p2m_next → mission → goal 状态 → gpu-serve POST /eval → {value:{v,d_hat}} + K 个 sketch
         → d_hat > 500 ? p2m_split(subtasks) : 自证块
         → 子 agent 返回/块收尾 → 重估 d_hat（子 mission 不继承 ≤500 约束）→ 再分 K 个
```

插件名 `value-head-training`（规划中；安装路径与 tool 名 `TBD`），落地前等价做法是直接打 `gpu-serve` 的 `/eval`。阈值 500 是 owner 的决策、不是拟合值；换 base 后要重标（旧头 hidden 不通用）。

## 10. 一条完整命令序列

```sh
ROOT=.; RUN=mp2m_$(date +%Y%m%d_%H%M%S)
ls $ROOT/data/bench_blind/T1.jsonl ~/lean-4.28-reap/env-0df444a/lakefile.toml  # 0) 健康检查
# 1) 抽样 + 2) 建环境：见 §6.2
bash $ROOT/guard/l0l1/probe.sh $ROOT/eval/$RUN/T1-<bench_id> --json   # 3) 防线探针（记哪层挡的）
for d in $ROOT/eval/$RUN/T*; do          # 4) 逐题跑：每题一个独立 session
  bash $ROOT/guard/run_eval.sh "$d" "$(cat $d/repo/README.md)" --model opencode-go/deepseek-v4.1-flash >> $ROOT/state/runs/$RUN/agent.log 2>&1
done
# 5) 判分：父会话 p2m_check({mission_id, proof}) → solved/errors
python3 -c 'import json,sys;r=[json.loads(l) for l in open(sys.argv[1])];print(len(r),sum(1 for x in r if x.get("accepted")))' \
  $ROOT/state/runs/$RUN/missions.jsonl     # 6) 汇总：missions 计数（分母写清）
grep -c '"decision":"deny"' $ROOT/guard/guard.log   # 加上：拦截/越权
# 7) 报告：pass@1 / 分解率 / 检索率 / 池命中率 / 拦截与越权，按 tier 分行
```

## 11. 目录与路径

| 项 | 路径 | 说明 |
| --- | --- | --- |
| 盲测题 | `./data/bench_blind/T{1..5}.jsonl` | 去身份，评测唯一入口 |
| 题库 | `data/bank_local/T*`、`data/bank/T*` | 训练自测 / 含 `theorem_id` 可真提交 |
| 判分项目（4.33.1）/ FATE（4.28.0） | `~/lean-4.28-reap/env-0df444a`、`/data/WSP/lean/proj` | 两套 olean 不通用；`p2m_check` 自动选前者 |
| L0/L1 工具 | `./guard/l0l1/` | `make_env.py`、`permissions.json`、`probe.sh` |
| 启动器 / 沙箱 | `guard/run_eval.sh`、`guard/l3/` | L1+L2(+L3)；`setup_sandbox.sh`、`p2mrun.sh` |
| guard 配置/日志 | `guard/guard.json`、`guard/guard.log` | 日志是拦截统计唯一来源 |
| 状态/轨迹 | `state/runs/<run>/{missions.jsonl,claims,attempts,exports}` | append-only；环境在 `eval/<run>/` |
| 插件 | `~/.opencode2/plugins/{prove2me-agent,p2m-guard}` | 源码在 `p2m/plugin`、`guard/l2` |
| 已知基线 / 沙箱方案 | `/data/WSP/RESULTS.md`、`./GUARD_PLAN.md` | 0.8B 失败模式；`p2m/RESULTS.md` 截至 2026-11-14 **不存在** |

## 12. 常见坑

| # | 坑 | 表现 | 修法 |
| --- | --- | --- | --- |
| 1 | `PWD` 不跟着 `cwd` 走 | agent 在上一题的目录里跑 | 启动必须 `env PWD=<env>/repo` |
| 2 | 忘 `--standalone` | 会话共享后台 project 根，题与题串味 | 一律 `--standalone` |
| 3 | tool parser 错配 | 本地 vLLM 下 `tool_calls` 恒 null | `--tool-call-parser qwen3_xml`（Qwen3.5） |
| 4 | 双 toolchain | 4.33.1 候选丢进 4.28.0 项目，报不存在的名字 | 只信 `p2m_check` 的 env pin，别手工 `lake` |
| 5 | `eval-blind` 禁 `subagent` | 想测多智能体风格却派不出子智能体 | solo 档测 pass@1；tree 档单列（继承 TBD） |
| 6 | 把 guard 改写当“不会搜” | `decision=rewrite` 被算成检索失败 | 检索率用原始意图口径 |
| 7 | 抽到编不过的题 | T2+ 大量 `Definitions.*` import | 先过滤 `local_compilable`，或先编依赖 |
| 8 | 小样本下结论 | n=8 就写“提升 12pp” | 只报计数/区间，写清分母 |
| 9 | 0.8B 跑本协议 / 手改 `missions.jsonl` | 领完题去改无关文件；归因与分数对不上 | 0.8B 只跑受限循环；轨迹 append-only |
| 10 | `decision=allow` 但有 error | 误判“越权成功” | 看 L3 是否真断网，看 `resource` 原文 |

## 13. 验收清单

- [ ] 模型过 §1 的 5 条准入；不过就换模型，不改判分。
- [ ] `sample.tsv` 可复算（tier + bench_id + seed）；每层实际条数写进报告。
- [ ] 每个环境 `repo/` 里搜不到身份字段；git 只有一个 commit；8 条探针记下“哪层挡的”。
- [ ] 判分三判据都由父会话执行，子智能体不给自己打分；每条 mission 有主归因标签（§8）+ 证据引用。
- [ ] 每个指标都带分子/分母；没有数字的地方写 `TBD` + 测法；五项齐全：分解率、检索率、池命中率、guard 拦截、越权尝试。
