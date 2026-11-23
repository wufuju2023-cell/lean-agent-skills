# Lean / Agent Skills

A collection of Agent Skills used to build and run autonomous Lean 4 proving
agents, multi-agent orchestration, and local model training experiments. Each
directory contains a `SKILL.md` with when-to-use guidance, commands and
implementation notes. Paths are placeholders (`~`, `/data`, `<host>`); adapt
them to your environment.

| Skill | What it covers |
|---|---|
| `3080-20g-local-information` | 本地环境那张魔改 RTX 3080 20G 的算力总账：硬件身份（GA102-200、68 SM、5MB L2、320-bit 19Gbps、320W、VBIOS 94.02.27.00.14）、gpu_unlock 2.0.0 到底解锁了什么（FP16/BF16/TF32 + FP32 累加... |
| `Test-harness` | Build self-contained Python exercise files that teach a topic from zero and grade themselves — lesson docstring, a "predict the output" quiz (CASES... |
| `ai-agent-gui` | Browser and desktop automation on this machine via the AI Agent GUI semantic CLI (agentgui), plus the machine's permanent browser-accessible XFCE r... |
| `explain-from-zero-with-ref` | 当用户贴一段 Lean 源码（或点名一个符号/文件）并要求「逐行逐块、从零讲、做真实验、写一套 .lean + .md、中文、自包含、放到某个路径」时使用：先判重与定位，再按「原文→拆块→排章→讲义→实验→引用→验收」产出可编译的教学工程，已有材料只引用不重写，引用必须是 nvim gF 可跳... |
| `fate-lean` | FATE（Formal Algebra Theorem Evaluation）benchmark 的本地环境总账：FATE-M/H/X 三个子基准的绝对路径、Lean 4.28.0 + Mathlib 4.28.0 版本 pin、已构建状态、重建与缓存命令，以及配合 lean-lsp MCP ... |
| `fate-opencode-freeform-agent` | 在 OpenCode v2 里用本地 vLLM 模型（现为 Qwen3.5-0.8B）跑 FATE/Lean 代数题的**自由形式 agent** 评测：如何起 vLLM（含 Qwen3.5 必须的 qwen3_xml tool parser）、如何配 OpenCode provider/ag... |
| `galore-explain` | 从零开始、自包含的中文教学系列，严格推导 GaLore 的数学原理（投影、Eckart–Young、收敛界、折叠与基刷新的可表示性定理、Adam 的基相关性），并给出它在本项目（Qwen3.6-35B-A3B 单卡全参数训练）里的具体装配；同时从基础讲 bf16/int8/int4、量化与反量... |
| `kaggle-cli` | 用 Kaggle CLI 跑 2×Tesla T4 GPU kernel、管理每周 GPU/TPU 配额、把 Kaggle Dataset 当跨会话持久存储（20GB /kaggle/working vs 100–200GB dataset），并附本地环境实测的上传/下载速度与 GPU 时间成本 |
| `lean-mathlib-local-path` | 本地环境所有 Lean toolchain 与 Mathlib checkout 的绝对路径、版本、构建状态和磁盘占用总账，用于回答「哪个 mathlib 能用」「mathlib 在哪」「这个项目 pin 的哪个版本」「怎么切 toolchain」，并给出新增版本的可复现步骤 |
| `local-lean-source-code-explain` | 用本地环境 6 个本地 Lean 4 教学语料库回答任意 Lean 关键词或整句提问：先在语料里定位，再用「绝对路径:行号」引用原文讲解 |
| `local-model-inference-doc` | 本地环境（单张魔改 RTX 3080 20G + 60G 内存 + NVMe）本地部署并实测 Qwen3.5-9B / Qwen3.8-27B / Qwen3.8-Flash-Next 三档模型的完整方案手册：用什么推理框架、怎么装、怎么起服务、OpenAI 端点与 OpenCode 接入、实... |
| `make-up-experiment` | 把某个数学对象/算法/损失函数拆成可手算、可复现的「手工数值实验」：编一套自洽的小数据（状态、词表、logits、树、权重、API 响应），每章一张手算表 + 一个零依赖脚本对拍，读者不需要模型/GPU/网络就能看懂全部逻辑 |
| `md-latex-rule` | 编写 Markdown 文档时选择数学公式写法并避免渲染失败：**首选纯文本公式**（Unicode 符号 + 代码段，任何渲染器原样显示），仅当纯文本无法表达（大分式/矩阵/对齐推导/cases 等）才用 LaTeX（GitHub GFM/KaTeX $..$ 与 $$..$$ 规则、本地 ... |
| `mineru-pdf-to-md-to-epub` | Convert/process a PDF through the MinerU pipeline (PDF → Markdown via MinerU cloud API → EPUB via pandoc) and file it into the math-ai-base-data ho... |
| `model-p2m-test` | 用 prove2me 题库对「能作为自由 agent 做 Lean 证明」的模型做端到端评测：分层抽样 T1–T5、bench_blind 盲测环境（L0 脱敏 + L1 权限 + L2 guard，可选 --l3）、run_eval.sh 启动、编译/无 sorry/陈述不变三判据、失败的六... |
| `prove2me-question-bench-train` | 把本地 prove2me/formalpedia 快照（516k Lean 文件、0 个 olean）零编译抽成 T1–T5 分级题库，既能当 benchmark 也能当训练题；并给出让 OpenCode v2 agent 自动领题、编译、拆子任务、导出 /verify 提交包的整套环境（vL... |
| `python-lean-hover-docs` | 「python-lean-悬停文档写法」——为 Python/Lean 源码加"零基础悬停文档"（nvim 悬停键 K）的完整方法论与工具链：本地 typings stubs 遮蔽（pyrightconfig.stubPath）+ 官方文档 backfill（防遮蔽丢官方内容）+ 中文讲解只追... |
| `qwen36-35b-a3b-train-locally` | 在单张魔改 RTX 3080 20G + 60G 内存上对 Qwen3.6-35B-A3B 做全参数 continued pretraining 的实测方案：roofline、模型真实结构、int8 主权重 + GaLore + 内存流式三段式设计、量化定论、三个自研内核、以及每层成本与最终吞吐账本 |
| `ssh-old-apple` | SSH into the old Apple/Windows machine (Tailscale host <host>, user <user>) for remote commands, file transfer, or troubleshooting. Use when the us... |
| `stacks-project-style-tags` | Apply or validate Stacks-Project-style tagged, numbered items（每个定义/定理/证明/代码/notebook cell 都有唯一 Tag，可交叉引用、不重复）to Markdown docs, source files, and Ju... |
| `tui-e2e-test-experience` | 用 tmux 驱动真实 OpenCode TUI（真实 PTY、真实渲染、send-keys 输入、capture-pane 读屏），再用 OpenCode HTTP API 做硬断言的端到端验收流程：启动、等待、发提示、轮询、取证、triage、清理；含本地环境 v2 二进制路径、模型 pi... |
| `v1.0.0-alpha-proof-gpu-training` | AlphaProof 10-4 的 GPU 侧训练与推理配方（v1.0.0）：gpu-serve 参数化 CLI、/eval 契约、离线 CE 专家迭代、在线 RTTT/TTTRL、64 桶价值头、pool 分片与 logprob 回填，以及已知的数学与工程缺陷 |
| `v1.1.0-lean-mcts-cpu-server` | AlphaProof 10-4 的 CPU 侧 Lean 会话与 MCTS 服务（v1.1.0）：持久 Lean 进程、状态句柄、任意历史状态分叉、失败回滚、focus 单目标、严格复验、Python PUCT、轨迹 store/export |
| `v2.0.0-alpha-proof` | 从 AlphaProof v1.0.0/v1.1.0 升级到 v2.0.0 的完整路线：把 LLM 放进 OpenCode v2 作为 agentic 动作执行器，在 Lean 4 题目序列上做 MCTS + CE |
| `wx-article-to-md` | Convert a WeChat 公众号 article (mp.weixin.qq.com/s/...) into a Markdown file with complete LaTeX formulas (inline $...$, display $$...$$) using a fix... |

## Layout

```text
<skill-name>/
  SKILL.md          # trigger, rules, commands
  scripts/          # optional helpers
  docs/             # optional long-form notes
```

## Notes

- These skills are written for an agent runtime that can read files, run shell
  commands and call tools; they are not a standalone application.
- Any absolute path shown in a command is a placeholder. Replace it with a path
  in your own workspace.
