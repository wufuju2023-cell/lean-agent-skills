---
name: FATE-OpenCode-Freeform-Agent
description: 在 OpenCode v2 里用本地 vLLM 模型（现为 Qwen3.5-0.8B）跑 FATE/Lean 代数题的**自由形式 agent** 评测：如何起 vLLM（含 Qwen3.5 必须的 qwen3_xml tool parser）、如何配 OpenCode provider/agent/lean-lsp MCP、如何建 Lean 4.28 项目并让 MCP 认它、如何发一次评测与判分、以及 0.8B 的失败模式基线。只覆盖自由形式 agent（模型自己决定 read/write/shell/MCP 调用），不含受限 tactic 循环。Use when starting a local model + OpenCode v2 + Lean/FATE free-form agent run, swapping the 0.8B for a stronger model, debugging why tool calls或 lean-lsp 不生效，或复现 FATE-M agent 基线。Triggers: FATE, FATE-M, Lean agent, OpenCode v2 本地模型, vLLM tool parser, qwen3_xml, lean-lsp MCP, lake env lean, 自由形式 agent, free-form agent, agentic Lean, 0.8B 基线, 换模型.
---

# FATE × OpenCode v2 自由形式 agent 评测

快照：**2026-11-14**。本 skill 只记录**自由形式 agent**：模型自己决定什么时候 `read`、
`write`、`shell`、`lean-goal`、`lean-multi_attempt`，自己不写死流程。
受限 tactic 循环（harness 替模型改文件）是另一条线，见 `/data/WSP/lean/`，不在本 skill 范围。

定位：0.8B 跑自由形式会崩，因此这份 skill 的真正用途是**给更强的模型准备好一套可复现的
启动 + 环境 + 判分流程**；0.8B 的数字只作为对照基线。

## 0. 三十秒命令

```sh
# 1) 起模型（0.8B，端口 8001）
bash ~/.config/opencode/skills/fate-opencode-freeform-agent/scripts/start_model.sh 0.8B

# 2) 自检三层：vLLM / OpenCode provider / lean-lsp
bash ~/.config/opencode/skills/fate-opencode-freeform-agent/scripts/smoke.sh

# 3) 在 Lean 项目里跑一道题（自由形式）
cd /data/WSP/lean/proj
env PWD=$PWD ~/.opencode2/bin/opencode run --standalone --auto \
  --agent leanwsp --model local08b/qwen3.5-0.8b --format json \
  "Prove tasks/m001/Problem.lean. Replace the TODO line. Use lean-goal first, then compile with lake env lean."
```

三条最容易踩的：**tool parser 必须是 `qwen3_xml`**、**必须 `--standalone`**、
**必须把 `PWD` 设成工作目录**（OpenCode v2 用 `$PWD` 定位 project，不认 `chdir`）。

## 1. 组件与端口

| 层 | 组件 | 地址/路径 |
| --- | --- | --- |
| 模型 | vLLM 0.32（venv 在 gloway） | `127.0.0.1:8001`，model id `qwen3.5-0.8b` |
| 评测备用实例 | 同上，独立端口 | `127.0.0.1:8011` |
| Agent 运行时 | OpenCode v2 | `~/.opencode2/bin/opencode` |
| 全局配置 | provider / agent / mcp | `~/.opencode2/config/opencode/opencode.json` |
| Lean 项目 | Lake + Mathlib 4.28.0 | `/data/WSP/lean/proj` |
| Lean 引擎 | FATE 官方 pin | `/data/lean-fate-related/FATE/FATE-M` |
| MCP | lean-lsp-mcp v0.33 | `~/.opencode2/bin/lean-lsp-mcp` |

显存：0.8B bf16 约 1.6 GB，`UTIL=0.22` 实测占 5–6 GB；两个实例并存无压力（实测 8.3 GB）。

## 2. 起模型（vLLM）

核心命令（`scripts/start_model.sh` 就是把这段参数化）：

```sh
source /data/qwen35-9b-throughput/env.sh
vllm serve "$DIR" --served-model-name qwen3.5-0.8b \
  --max-model-len 65536 --gpu-memory-utilization 0.22 \
  --max-num-seqs 16 --kv-cache-dtype int8_per_token_head \
  --enable-prefix-caching --enable-chunked-prefill --language-model-only \
  --reasoning-parser qwen3 \
  --enable-auto-tool-choice --tool-call-parser qwen3_xml \
  --default-chat-template-kwargs '{"enable_thinking": false}' \
  --speculative-config '{"method":"mtp","num_speculative_tokens":2}' \
  --host 127.0.0.1 --port 8001
```

**为什么每一行都不能省**：

| 参数 | 作用 | 不写的后果 |
| --- | --- | --- |
| `--tool-call-parser qwen3_xml` | Qwen3.5 输出 `<tool_call><function=..><parameter=..>` XML | 用 `hermes` 会让 `tool_calls` 恒为 `null`，模型只输出文本，OpenCode 永远不执行工具 |
| `--enable-auto-tool-choice` | OpenCode 发 `tool_choice:"auto"` | 直接 400 |
| `--reasoning-parser qwen3` | thinking 分流到 `reasoning` 字段 | 内容混在一起；注意字段叫 `reasoning`，不是 `reasoning_content` |
| `--default-chat-template-kwargs '{"enable_thinking": false}'` | 0.8B 开 thinking 停不下来（500 token 内出不了正文） | content 恒 null，agent 无法行动；可用请求级 `chat_template_kwargs` 覆盖 |
| `--language-model-only` | 跳过视觉塔 | 多占 ~1 GB |
| `--kv-cache-dtype int8_per_token_head` | Ampere 无 FP8 | 默认 fp16 KV，长上下文吃显存 |
| MTP `--speculative-config` | 权重自带 mtp head | 单流吞吐掉 ~45% |

### 换模型（这是本 skill 的主要用途）

只改三处，其余不动：

```sh
DIR=/data/models/<新模型> NAME=<新 id> UTIL=<按显存> bash scripts/start_model.sh
# 同步改 opencode.json 里的 provider.models 与 agent.model
```

显存参考：0.8B `UTIL=0.22`、4B `UTIL=0.60`、9B-AWQ `UTIL=0.92`。
换模型后**先跑 `smoke.sh`**，确认 tool parser 仍然匹配——不同模型家族的 XML/JSON 格式不同，
parser 选错就回到"永远不调工具"的状态。

## 3. OpenCode v2 配置

### 3.1 provider

```jsonc
"providers": {
  "local08b": {
    "name": "Local Qwen3.5-0.8B (vLLM 8001)",
    "package": "@opencode/ai/providers/openai-compatible",
    "settings": { "baseURL": "http://127.0.0.1:8001/v1", "apiKey": "local",
                  "chunkTimeout": 300000 },
    "models": { "qwen3.5-0.8b": { "name": "Qwen3.5-0.8B (local)",
                                  "limit": { "context": 65536, "output": 8192 } } }
  }
}
```

`limit.context` 必须 ≤ 服务端 `--max-model-len`，否则超长会话会 400。

### 3.2 agent（leanwsp）

```jsonc
"agent": {
  "leanwsp": {
    "description": "Lean 4 prover agent with lean-lsp + web tools",
    "mode": "primary",
    "model": "local08b/qwen3.5-0.8b",
    "prompt": "You are a Lean 4 prover working in /data/WSP/lean/proj. ...",
    "tools": {
      "*": false,
      "read": true, "write": true, "edit": true, "shell": true,
      "glob": true, "grep": true,
      "lean-goal": true, "lean-multi_attempt": true,
      "lean-local_search": true, "lean-leansearch": true,
      "lean-diagnostic_messages": true, "lean-hover_info": true
    },
    "temperature": 0.2
  }
}
```

要点：

- MCP 工具在模型侧的**名字是 `<server>-<tool>`**，带连字符且保留下划线：
  `lean-goal`、`lean-multi_attempt`、`lean-local_search`、`lean-leansearch`。
  不叫 `lean_goal`，也不是 `lean-lsp_lean_goal`。
- `"*": false` 是必须的：默认会把所有 skill、`goal`、`mineru`、`session_*` 都暴露给模型，
  0.8B 会随机调用它们（实测调用过 `mineru-pdf-to-md-to-epub` 和 `personnel_search`）。
- code-mode 的 `execute` 无法通过 `"execute": false` 关掉（名字不是这个）；
  真要禁就用 `"*": false` 白名单。
- `permissions` 建议加 `external_directory` 限制；0.8B 实测会往 `~`、`/etc` 写文件。

### 3.3 MCP（lean-lsp）

```jsonc
"mcp": {
  "servers": {
    "lean-lsp": {
      "type": "local",
      "command": ["~/.opencode2/bin/lean-lsp-mcp"],
      "environment": {
        "LEAN_LOG_LEVEL": "ERROR",
        "PATH": "~/.elan/bin:~/.local/bin:~/.opencode2/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin"
      }
    }
  }
}
```

**PATH 里必须有 `~/.elan/bin`**：OpenCode 后台进程默认没有它，lean-lsp 找不到 `lake`
就会所有调用返回 `None`（表现为"工具调了但没输出"）。

## 4. 三条硬规则（启动 agent 时）

```sh
env PWD=$PWD ~/.opencode2/bin/opencode run \
  --standalone --auto --agent leanwsp --model local08b/qwen3.5-0.8b \
  --format json "<prompt>"
```

| 规则 | 原因 | 症状 |
| --- | --- | --- |
| `--standalone` | 否则会话挂到后台共享服务，project 根是启动目录 | agent 在别的目录里读写文件 |
| `env PWD=<taskdir>` | OpenCode v2 用 `$PWD` 而不是 `chdir` 定位 project | 任务在 A 目录，agent 全程在 B 目录操作 |
| `--auto` | 非交互模式下权限提示没人点 | 退出码 1，无任何输出 |

`--format json` 每行一个事件；工具调用在 `{"type":"tool_use","part":{...}}`，
文本在 `{"type":"text","part":{"text":...}}`。做自动化判分只解析这两类即可。

## 5. Lean 项目：让 lean-lsp 认它

lean-lsp 有一条硬约束：**文件必须位于某个含 `lean-toolchain` 的 Lean 项目内**，
否则报 `Invalid Lean file path: ... not found in any Lean project`。FATE 自带的三个目录可用，
但不要在 benchmark 里改题；建议单独建项目：

```sh
mkdir -p /data/WSP/lean/proj && cd /data/WSP/lean/proj
printf 'leanprover/lean4:v4.28.0\n' > lean-toolchain

cat > lakefile.toml <<'EOF'
name = "wsplean"
defaultTargets = ["Wsplean"]
[[require]]
name = "mathlib"
path = "/data/lean-fate-related/mathlib4"
[[lean_lib]]
name = "Wsplean"
EOF

mkdir -p Wsplean && printf 'import Mathlib\n' > Wsplean/Basic.lean
printf 'import Wsplean.Basic\n' > Wsplean.lean

export PATH=$HOME/.elan/bin:$PATH
export MATHLIB_CACHE_DIR=/data/lean-fate-related/cache/mathlib
lake update       # 走本地 path 依赖 + 已缓存 olean，约 20 s
lake build        # 8028 jobs，约 3 s
```

注意 `[[lean_lib]]` 要求根文件 `Wsplean.lean` 存在，否则 `lake build` 报
`file: .../Wsplean.lean`。

单文件检查（这也是 agent 的编译反馈来源）：

```sh
cd /data/WSP/lean/proj && lake env lean tasks/m001/Problem.lean
# 无输出 = 通过；有输出 = 报错，直接回灌给模型
```

MCP 侧验证（在 execute 里）：

```js
await tools["lean-lsp"].lean_goal({
  file_path: "/data/WSP/lean/proj/tasks/m001/Problem.lean", line: 9 })
```

## 6. 题目与判分

题目放在 `proj/tasks/<id>/`，每个目录：

```text
Problem.lean   原题，唯一的改动是 `  sorry` → `  -- TODO: replace this line with a proof`
meta.json      {id, source, statement, nl_comment, reference_proof}
```

判分三条同时成立：

1. `lake env lean tasks/<id>/Problem.lean` 无输出（编译通过）；
2. 文件里没有 `sorry`；
3. theorem 语句与 `meta.json.statement` 逐字一致（防改题）。

一行判分：

```sh
cd /data/WSP/lean/proj
lake env lean tasks/m001/Problem.lean 2>&1 | grep -q . || ! grep -q sorry tasks/m001/Problem.lean
```

参考实现：`/data/WSP/lean/`（`try_tactic.sh`、`run_loop.py` 属于受限循环，供对照）。

## 7. 0.8B 基线（换强模型后的对照）

| 设置 | 结果 | 说明 |
| --- | --- | --- |
| 自由形式 OpenCode + lean-lsp | **不可用** | 读不到文件、`lake env lean` 写成 `lake env`、往 `/home` 乱写、无限循环 |
| 受限 tactic 循环（10 道最易 FATE-M） | 5/10 → 6/10（秩一编辑后） | `simp`/`exact <lemma>` 全过，`aesop` 题全挂 |
| 搜索率 | 0/311 | 即使 prompt 要求 `SEARCH:` 也不发起 |

失败模式（自由形式）：找不到工作目录 → 重建文件 → 路径又错 → 死循环；几乎不调用
`lean-goal`；即使调用也把 `line` 写成字符串 `"9"`（schema 要 integer）。

**换强模型后的验收顺序**：先确认它能稳定完成 m001（1–2 步），再跑 m001–m010，
最后才上 FATE-M 全量。

## 8. 坑清单

1. **parser 错配**：`hermes` → `tool_calls: null`；Qwen3.5 必须 `qwen3_xml`。换模型先验这一条。
2. **`PWD` 不跟随 `chdir`**：`subprocess(cwd=...)` 无效，必须 `env PWD=...`。
3. **不加 `--standalone`**：会话共享后台 project，所有 agent 在同一目录互相污染。
4. **MCP 文件不在 Lean 项目内**：`not found in any Lean project`。
5. **PATH 缺 elan**：MCP 调用返回 `None`，无报错。
6. **工具名写成下划线**：`lean_goal` 不存在，正确是 `lean-goal`。
7. **`line` 传字符串**：schema 是 integer，传 `"9"` 会失败。
8. **模型权限过宽**：0.8B 实测删过源文件、`rm -rf`、`pkill -f node`。评测目录必须可丢弃，
   或只读挂载 + 独立工作副本。
9. **`pkill -f "vllm serve <DIR>"` 会跨端口误杀**：同目录的两个实例会被一起杀。
   按端口 kill，或用不同的 `DIR` 副本。
10. **重复 `import unittest` 之类的脚手架 bug**：生成任务时先跑一遍基线，确认失败原因就是
    你想测的那个，不要把脚手架噪声当成模型能力。

## 9. 换强模型 checklist

```text
[ ] start_model.sh 改 DIR/NAME/UTIL，确认 /v1/models 有响应
[ ] chat/completions + tools 手测一次：tool_calls 非 null
[ ] opencode.json：provider.models、agent.model 同步
[ ] smoke.sh 三层全过（vLLM / provider / lean-goal）
[ ] 在 proj 里跑 m001，人工确认它真的调了 lean-goal 且用 `lake env lean` 编译
[ ] 再跑 10 题，记录 pass/步数/工具序列
[ ] 最后才换 FATE-M 全量（150 题，注意并发与 token 预算）
```
