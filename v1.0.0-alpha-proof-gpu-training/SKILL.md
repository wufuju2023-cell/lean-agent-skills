---
name: v1.0.0-alpha-proof-gpu-training
description: 'AlphaProof 10-4 的 GPU 侧训练与推理配方（v1.0.0）：gpu-serve 参数化 CLI、/eval 契约、离线 CE 专家迭代、在线 RTTT/TTTRL、64 桶价值头、pool 分片与 logprob 回填，以及已知的数学与工程缺陷。当用户要改 GPU 训练、换 base 模型、LoRA 或价值头、接 Qwen3.5、加新的 eval 引擎、跑真实 7B 冒烟、或排查 CE/值头/池子问题时使用。触发词：gpu-serve, /eval, update_offline, update_online, OfflineLearner, OnlineLearner, 64 桶, value head, CE 专家迭代, RTTT, TTTRL, pool, merge-logprobs, REAL-Prover, Qwen3.5 训练, LoRA target modules, gradient accumulation, 云端训练。'
---

# v1.0.0-alpha-proof-gpu-training

一句话：GPU 侧只做三件事——**装载 base/LoRA/64 桶头、按 `/eval` 契约提供 policy+value、按冻结的 CE/REINFORCE 逻辑更新参数**。
搜索、Lean 会话、轨迹落盘都在 CPU 侧（见 `v1.1.0-lean-mcts-cpu-server`）。

## 0. 什么时候用

用：
- 改 `update_offline/` / `update_online/` 的训练数据、超参、保存逻辑；
- 换 base 模型（REAL-Prover 7B → Qwen3.5-0.8B/2B/4B/9B）；
- 加一个 policy/value 引擎，或改 `/eval` 的返回字段；
- 跑云端真实 7B 冒烟、离线/在线 1 步更新；
- 排查 value loss、d̂、logprob、LoRA 不生效、池子 join 失败。

不用：
- 改 Lean 会话 / MCTS / 轨迹 store → 用 `v1.1.0-lean-mcts-cpu-server`；
- 把 LLM 放进 opencode v2 做 agentic 动作 → 用 `v2.0.0-alpha-proof`。

## 1. 规范路径

| 用途 | 路径 |
| --- | --- |
| 开发仓库 | `~/repos/10-4-alpha-proof` |
| 云端运行副本 | `/workspace/alphaproof-aligned/repo`（ROCm） |
| 云端 7B base | `/workspace/models/REAL-Prover-fe76f68d` |
| 云端 64 桶头 | `/workspace/new_value_head/heads-79efd240/train205628-full-v3/value-head.pt` |
| 本地环境模型 | `/data/models/Qwen3.5-{0.8B,4B,9B-AWQ-4bit}` |
| 训练池 | `/workspace/pool/<wave_id>/shard-*.jsonl + manifest.json` |
| 规格 | `docs/gpu-serve.md`、`docs/new-python-version-mcts-plan/02-architecture.md` §5 |
| 数学审计 | `docs/10-25-分析/1-learner-py-分析.md`、`2-与官方pseudocode对比.md` |

## 2. 代码地图

```text
gpu_serve/
  config.py        ModelSetup / LoraSpec / TrainHyper；CLI > TOML > 默认
  components.py    加载 tokenizer/base/PEFT adapter/裸 LoRA/64 桶头；hidden size 自适应
  engines.py       MockEvalEngine / TinyEvalEngine / HFEvalEngine，统一 eval(prompt,k,temp)
  serve.py         stdlib HTTP：GET /health、POST /eval、Bearer 认证
  train.py         train offline / train online；只调用 learner，不复制算法
  pool.py          训练池 pull/push/merge-logprobs/stats
  cli.py           命令面（冻结）
update_offline/
  learner.py       OfflineLearner：policy CE + 64 桶 value CE
  replay.py        OfflineBatchBuilder：proof/disproof/timeout + SFT 混比
update_online/
  learner.py       OnlineLearner：-r·Δ + β·Δ² + value CE
alphaproof/
  net/value_head.py    ValueHead64（H→256→64）、two-hot、expected_distance
  targets/             compute_value_target / extract_transitions
  data/events.py       Transition / Trajectory（唯一训练口径）
  config.py            TrainConfig：value_coef=1e-3、lr、micro/batch
```

## 3. `/eval` 契约（不要改字段，除非升版本）

```text
POST /eval
  {"prompt": "<tactic state 文本>", "k": 6, "temperature": 1.0,
   "policy_version": "v123", "request_id": "..."}
→ 200
  {"candidates":[{"tactic":"...","logprob":-3.21}, ...×k],
   "value":{"v":-7.4,"d_hat":7.4},
   "model_revision":"REAL-Prover-fe76f68d","adapter":"..."}
```

- `logprob` 是**原始策略**下整条候选的 sum log p；`temperature` 只影响采样，先验温度由 CPU 侧 τ=200 处理。
- `v = -d_hat`；`d_hat` 是 64 桶期望剩余步数。
- 认证 `Authorization: Bearer <token>`，token 文件 600 权限，只驻内存、不进日志；`/health` 不鉴权。
- 超时/5xx 由客户端重试 3 次；仍失败按官方 `-40` 兜底，并落 `env_error`。
- `HFEvalEngine` 当前 `max_new_tokens=64`、`stop_at_newline=True`：**它是 tactic 级端点**，不是 action block 端点。

## 4. 训练目标（冻结逻辑）

离线（官方式专家迭代）：

```text
L = Σ_i w̃_i · (1/n_i) Σ_j -log πθ(a_ij | c_i, a_i,<j)
  + λ · (1/N_v) Σ_{i∈V} CE64(two_hot(d_i), Vφ(h_{L-1}))
```

- `d(s) = -value_target`；终端 0、OR `-1+子`、AND `min(子)`；
- `λ=value_coef=1e-3`；`value_lr=3e-4`；`policy_lr=1e-4`；
- proof + disproof 进训练，timeout 默认剔除，SFT 默认 10%；
- `micro_batch_size=16` 名义上做梯度累积。

在线（本地环境 RTTT/TTTRL）：

```text
policy = -r·Δ + β·Δ²,  Δ = logp_target - logprob_old,  r ∈ [-1,1]
total  = mean(policy) + value_coef · CE64
```

- 正奖励必须 `terminal_verified=true`；
- `value_target` 缺失时**不训练 value**，不再用 `r` 兜底；
- `learn_batch_size=1` 一条一更，`=N` 凑 N 条一更；`flush()` 处理残余。

## 5. 命令手册

```bash
cd ~/repos/10-4-alpha-proof

# 0) 不装依赖也能看命令
python -m gpu_serve --help
python -m gpu_serve serve-eval --help

# 1) 无依赖联调（契约/鉴权/端口）
python -m gpu_serve serve-eval --engine mock --port 18080

# 2) CPU tiny（全回路，不需要 HF 权重）
python -m gpu_serve smoke --tiny --out /tmp/gpu-smoke.json
python -m gpu_serve serve-eval --tiny --engine tiny

# 3) 真实 7B（云端）
python -m gpu_serve serve-eval \
  --base /workspace/models/REAL-Prover-fe76f68d --lora none \
  --head /workspace/new_value_head/heads-79efd240/train205628-full-v3/value-head.pt \
  --dtype bf16 --host 127.0.0.1 --port 18080 --token-file ~/.config/lmc/token

# 4) 离线一步
python -m gpu_serve train offline \
  --base /workspace/models/REAL-Prover-fe76f68d --head .../value-head.pt \
  --pool /workspace/pool/wave_001 \
  --steps 1 --batch-size 64 --micro-batch-size 16 \
  --lr 1e-4 --value-lr 3e-4 --value-coef 1e-3 --sft-mix 0.1 \
  --out run/receipts.jsonl --save-dir run/ckpt

# 5) 在线事件回放（壳）
python -m gpu_serve train online --base ... --head ... \
  --events run/events.jsonl --batch-size 1 --beta-kl 0.05

# 6) 留出评测 / 版本 / 池子
python -m gpu_serve eval heldout --base ... --head ... --pool run/heldout --out heldout.json
python -m gpu_serve versions --base ... --head ... --lora none
python -m gpu_serve pool stats --pool /workspace/pool/wave_001
python -m gpu_serve pool merge-logprobs --pool ... --logprobs run/gpu_logprobs.jsonl --strict
```

真实 7B 冒烟（一次性）：

```bash
python scripts/cloud_real_smoke.py \
  --model /workspace/models/REAL-Prover-fe76f68d \
  --head .../value-head.pt --out outputs/cloud_smoke
```

看 `report.json` 的 `s18_head.missing/unexpected`、`lora`、`model_hidden/vocab`、`offline_update`、`online_updates`。

## 6. 换 base 模型（以 Qwen3.5 为例）

按顺序做，任何一步失败就停：

1. **hidden size**：0.8B=1024、2B=2048、4B=2560、9B=4096。`--hidden-size 0` 会从 `config.hidden_size` 或 `text_config.hidden_size` 推断；换完先跑 `gpu-serve versions` 核对。
2. **tokenizer**：`--tokenizer` 可单独指向；缺 pad 会自动退化为 eos。
3. **LoRA target modules**：默认 7 个投影里，`q/k/v/o` 只覆盖 1/4 的全注意力层（`gate/up/down` 属于 MLP，每层都有）；Qwen3.5 有 3/4 层是 GDN，必须加：
   `in_proj_qkv`, `in_proj_z`, `in_proj_a`, `in_proj_b`, `out_proj`（以及可选 `conv1d`）。
   不加的话注意力侧只覆盖 1/4 层，容量明显偏小，loss 下降但能力提升有限——这是最容易误判的坑。
4. **加载类**：Qwen3.5 权重是 `Qwen3_5ForConditionalGeneration`，文本子模块键前缀是 `model.language_model.*`；`AutoModelForCausalLM` 未必能直接加载。优先用 `Qwen3_5ForCausalLM` + key 映射，或写一个薄 loader；不要假设 `--language-model-only` 在 HF 侧存在（那是 vLLM 参数）。
5. **价值头**：换 hidden 后旧头失效，必须用新 base 的 hidden 重训 `H→256→64`；先 freeze 主干只训头，成本最低。
6. **chat template**：Qwen3.5 是 instruct 模型，`/eval` 的 `prompt` 必须由调用方用 `apply_chat_template(..., enable_thinking=False)` 包好；engine 本身不做模板。训练侧同理，见 §8 第 1 条。
7. **冒烟阶梯**：`--engine mock` → `--tiny` → 0.8B → 4B → 9B；每级都跑 `versions` + 1 次 `/eval` + 1 次 offline。
8. **本地环境显存**：4B bf16 权重 9.3GB，LoRA 训练 14–18GB；9B bf16 19.3GB，20G 卡只能推理（AWQ 8.6GB），训练上云。

## 7. 开发 recipe

### 7.1 加一个 eval 引擎

1. 在 `gpu_serve/engines.py` 继承 `BaseEvalEngine`，实现 `eval(prompt, k, temperature) -> dict`；
2. 返回必须含 `candidates[*].tactic/logprob`、`value.v/d_hat`、`model_revision`、`adapter`；
3. 在 `cli.py` 的 `--engine` 分支注册；
4. 用 `serve-eval --engine <name>` + `curl /eval` 做契约测试；
5. 不要改 `serve.py` 的字段，除非升 `/eval` 版本。

### 7.2 加一个新损失 / 新更新算法

`docs/architecture/core-and-branches.md` 把 `update_offline` / `update_online` 的 CE 逻辑冻结为“只调用、不许改”。
正确做法：

- 新建 `update_xxx/learner.py`，实现 `update(batch)`，保持 `receipt` 字段；
- 在 `gpu_serve/train.py` 加子命令（这是主线变更，需要显式拍板，不是支线）；
- 不要复制 `_policy_ce` / `two_hot`，从原模块 import，避免两套口径；
- 新旧算法用同一份 `Transition` 和同一个 `value_head`，才能 A/B。

### 7.3 加数据 / encode 路径

`OfflineLearner` 只依赖 `encode_fn(prompt, action) -> (input_ids, labels, prompt_len[, attention_mask])`。
换 chat 模型时不要改 learner，改 encode：

```python
# 目标形态
prompt_ids = tokenizer.apply_chat_template(
    [{"role": "system", "content": SYS}, {"role": "user", "content": state_pp}],
    add_generation_prompt=True, enable_thinking=False, return_tensors="pt",
)
action_ids = tokenizer(action_text, add_special_tokens=False, return_tensors="pt")
input_ids = cat([prompt_ids, action_ids])
labels = [-100] * len(prompt_ids) + action_ids
```

注意：当前 `make_hf_encode_fn` 是 `tokenizer(prompt)` 直接拼 `tokenizer(action)`，没有 chat template，也没有在 action 末尾补 eos。接 Qwen3.5 必须换成上面的形态，并保留 `prompt_len`。

### 7.4 加池子来源

- 池子只认 `Transition` 行；目录里 `shard-*.jsonl` 优先；
- `pool pull` 逐 shard 校验 `sha256`、行数、bytes，再核对 `counts`；
- `pool push` 只从 `HF_TOKEN` 读 token，不落盘；
- `merge-logprobs` 的 join 键是 `(search_id, state_hash, action)`；新增动作类型时不要复用 `action` 字段，另加 `commit_id`。

## 8. 已知缺陷（接真实模型前必须知道）

来自 `docs/10-25-分析/1`、`2`，并已在代码中核对：

| # | 问题 | 症状 | 处理 |
| --- | --- | --- | --- |
| 1 | `micro_batch_size` 不是真正的梯度累积 | 峰值显存仍 `O(N)`；大 batch OOM | 循环前算好 `w_i/Σw` 与 `λ/N_v`，每个 chunk `backward()` 后释放图 |
| 2 | policy CE 在 bf16 logits 上算 | 低概率 token 下溢，梯度失真 | `shift_logits.float()` 后再 `cross_entropy` |
| 3 | `_two_hot(-value_target)` 无断言 | 上游传 `d` 时值函数退化成常数，loss 仍下降 | 用 `sample.distance` 或 `assert value_target <= 0` |
| 4 | `run_expert_iteration.py` 把 replay 复制进 SFT 池 | 同一样本 policy 被加权 2 倍 | SFT 池必须是独立分布；至少去重 |
| 5 | `λ` 对独立参数组近乎无效 | 调 `value_coef` 看不到 value 头变化 | 调 `value_lr`；分别打印 policy/value 梯度范数 |
| 6 | 价值项按 `N_v` 归一 | `λ_eff=λ·N/N_v` 随 batch 漂移 | 记录 `N_v`，或显式改成 `λ/N` |
| 7 | 终端 `d=0` 落到桶 1 | `V=-1` 而非 0，PUCT 有常数偏移 | 搜索侧单独处理 terminal，或改桶定义（需升版本） |
| 8 | 默认 LoRA 不覆盖 GDN | 3/4 层冻结，容量极低 | 加 `linear_attn.*` 目标模块 |
| 9 | `HFEvalEngine` 只生成 64 token 且遇换行即停 | 只能出单条 tactic | v2 action 要另开 proposal/commit 通道，不要硬改这个端点 |

## 9. 测试与验收

```bash
python3 -m pytest tests -q                 # 无 torch 自动跳过更新测试
python3 -m gpu_serve smoke --tiny          # 前向 + offline + online
python3 scripts/cloud_real_smoke.py ...    # 真实 7B
```

验收看：

- `value_head` 加载 `missing=[] unexpected=[]`；
- `model_hidden` 与 `hidden_size` 一致；
- offline `loss/policy_loss/value_loss` 有限，`value_samples > 0`；
- online 正奖励事件 `terminal_verified=true`；
- `save-dir` 里 `value-head.pt` + `adapter/` + `meta.json` 齐全。

## 10. 一句话

**GPU 侧是“参数化装载 + 冻结 CE + `/eval` 契约”；换模型是配置问题，换算法是新模块问题，不要动主线。**
