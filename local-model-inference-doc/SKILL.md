---
name: local-model-inference-doc
description: '本地环境（单张魔改 RTX 3080 20G + 60G 内存 + NVMe）本地部署并实测 Qwen3.5-9B / Qwen3.8-27B / Qwen3.8-Flash-Next 三档模型的完整方案手册：用什么推理框架、怎么装、怎么起服务、OpenAI 端点与 OpenCode 接入、实测吞吐/并发/MTP/上下文数字，以及踩过的坑。当用户问本地环境怎么跑这些本地模型、用 llama.cpp/vLLM/Strata 哪个、起服务命令、接 OpenCode、或想要各模型吞吐/上下文实测值时使用。触发词：本地模型部署, 3080 20G, qwen3.5 9b, qwen3.8 27b, flash-next, llama.cpp, vLLM, Strata, MTP, 上下文, 吞吐, opencode 接本地模型, gloway 模型目录。'
---

# 本地环境本地大模型推理手册（Qwen3.5-9B / Qwen3.8-27B / Qwen3.8-Flash-Next）

一台机器：**魔改 RTX 3080 20G**（GA102，8704 核，760 GB/s，320W）+ **Ryzen 5700X**（8C/16T）+ **60G 内存** + **1.7T NVMe（/data）**。驱动 580.178.04，CUDA 13 由 torch 自带。

**铁律：所有模型/venv/引擎/缓存都放 `/data`，不碰系统盘（系统盘仅 ~85G）。** 跑推理时停图形桌面（用户走 SSH）：`systemctl stop gdm`（要桌面时 `systemctl start gdm`），省 ~55G 内存和显存。CPU 用 `taskset -c 0-11 nice -n 10` 限 12/16 核留余量。

## 0. 选型速查（哪个模型用哪个框架）

| 模型 | 框架 | 量化 | 为什么 |
|---|---|---|---|
| Qwen3.5-9B（稠密 9B，原生 262K ctx） | **vLLM** | cyankiwi AWQ-4bit | 单卡吞吐最高；int8 KV + MTP |
| Qwen3.8-27B（稠密 27B） | **llama.cpp** | unsloth UD-Q4_K_M(15.4G) | 单卡 vLLM 放不下 KV；llama+MTP 最优 |
| Qwen3.8-Flash-Next（125B MoE，6B 激活 + 51B engram） | **Strata** | ISTA-DAS IQ2_XS | 只有 Strata 的 GPU/RAM/SSD 三层专家卸载跑得动 125B |

## 1. 目录与关键路径

- 工程：`/data/qwen35-9b-throughput/`（9B + llama.cpp 构建 + env）、`/data/qwen38-throughput/`（27B + Flash + 评测）
- 模型：`/data/models/`（Qwen3.5-9B-AWQ-4bit、Qwen3.5-9B-GGUF、Qwen3.8-27B-GGUF、Qwen3.5-0.8B）；Flash 与 Strata 在 `/data/strata-data`、`/data/strata`
- llama.cpp 二进制：`/data/qwen35-9b-throughput/llama.cpp/build/bin/`（含 llama-server / llama-bench）
- vLLM venv：`/data/qwen35-9b-throughput/venv-vllm/`（vllm 0.32.0, torch 2.13.0+cu130）
- Strata 终端：`~/.local/bin/strata`（v0.2.13，引擎/数据在 gloway）
- 环境脚本：`source /data/qwen35-9b-throughput/env.sh`（CUDA/缓存全在里面）

### CUDA 工具链（最大的坑，务必懂）
本地环境**没有独立 nvcc**，但 torch cu130 自带完整工具链：`venv-vllm/.../nvidia/cu13`（nvcc 13.5 + cublas + cudart + cccl）。env.sh 用它拼了个标准布局的 `cuda-fake` 目录设成 `CUDA_HOME`。
**nvcc 13.5 与 pip cudart 头 13.0 小版本错位**，flashinfer JIT 和 llama.cpp 编译都会报 "CUDA compiler and CUDA toolkit headers are incompatible"。官方放行宏：
```sh
export NVCC_PREPEND_FLAGS="-DCCCL_DISABLE_CTK_COMPATIBILITY_CHECK"   # 全局，管 llama.cpp
export FLASHINFER_EXTRA_CUDAFLAGS="-DCCCL_DISABLE_CTK_COMPATIBILITY_CHECK"
export FLASHINFER_EXTRA_CFLAGS="-DCCCL_DISABLE_CTK_COMPATIBILITY_CHECK"
export FLASHINFER_WORKSPACE_BASE=$ROOT/cache/flashinfer   # JIT 缓存挪出系统盘！
```
这三行都在 env.sh 里，`source` 即生效。flashinfer JIT 首次编译几分钟，之后走缓存。

## 2. Qwen3.5-9B —— vLLM 部署

```sh
source /data/qwen35-9b-throughput/env.sh
bash /data/qwen35-9b-throughput/scripts/10_serve_prod.sh
#   CTX=262144 10_serve_prod.sh   # 长上下文
#   NOMTP=1 10_serve_prod.sh       # >=8 路并发时关 MTP（MTP 只赚单流）
```
核心命令：
```
vllm serve /data/models/Qwen3.5-9B-AWQ-4bit --served-model-name qwen3.5-9b \
  --max-model-len 65536 --gpu-memory-utilization 0.92 --max-num-seqs 8 \
  --kv-cache-dtype int8_per_token_head --enable-prefix-caching --enable-chunked-prefill \
  --language-model-only --reasoning-parser qwen3 \
  --speculative-config '{"method":"mtp","num_speculative_tokens":2}' --host 127.0.0.1 --port 8000
```
要点：Ampere **无 FP8**，KV 用 `int8_per_token_head`（不是 fp8）；`--language-model-only` 省视觉塔；`--reasoning-parser qwen3` 拦 thinking 不外泄。

实测（单卡 20G）：单流 decode 98.1（无MTP）/**110.9 t/s（MTP，+13%）**；并发总吞吐 c2 190/c4 362/**c8 694 t/s**；prefill 冷 ~3000、前缀命中 15K–52K t/s；262K 上下文可跑（显存 16.7/18.4G，int8 KV）。

## 3. Qwen3.8-27B —— llama.cpp 部署

```sh
bash /data/qwen38-throughput/scripts/up_27b.sh
#   可调 env: CTX=65536 PORT=8091 MTPN=2 TAG=... ALIAS=qwen3.8-27b
```
核心命令：
```
llama-server -m /data/models/Qwen3.8-27B-GGUF/Qwen3.8-27B-UD-Q4_K_M.gguf \
  --alias qwen3.8-27b -ngl 99 -fa on -c 65536 -np 1 --temp 0 \
  --cache-type-k q8_0 --cache-type-v q8_0 \
  --spec-type draft-mtp --spec-draft-n-max 2 --host 127.0.0.1 --port 8091
```
要点：unsloth 27B GGUF **含 MTP head**（`blk.64.nextn.*`），llama.cpp 原生 `--spec-type draft-mtp` 可用。注意 `-np` 会把上下文均分给每个并行槽（每槽 = ctx/n_slots），单条长文要么 `-np 1` 要么调大 ctx。

实测（单卡 20G）：单流 decode 37.3（无MTP）/**68.2 t/s（MTP n=2，+83%，接受率0.73–0.76，均接受长度2.5）**；并发总吞吐（无MTP）c1 37/c2 67/c4 104/**c8 130 t/s**；prefill（llama-bench）1442–1498 t/s；**64K 上下文单卡可载入**（15.4G 权重 + 64K q8 KV = 17.8G）。

## 4. Qwen3.8-Flash-Next —— Strata 部署

```sh
CTX=128k bash /data/qwen38-throughput/scripts/up_flash.sh   # 64k/128k 可选
# 停止: ~/.local/bin/strata launch --stop
```
核心命令：
```
strata launch --family qwen --model iq2_xs --context 128k \
  --data-dir /data/strata-data --port 8080 --vision off --drafting mtp --no-tui --yes
```
要点：
- 首次需 `HF_TOKEN`（在 `~/.cache/huggingface/token`），否则 HF **匿名下载会在 ~37G 处限速归零卡死**。up_flash.sh 已 `export HF_TOKEN`。下载 69G + MTP 草稿 5G，断点续传，卡住就重跑 `strata launch`。
- 量化档（60G 内存下）：**IQ2_XS 稳**（experts 35.5G+10G，下载 69G）；IQ3_XXS 偏紧；IQ3_S 放不下。低比特长文检索有漏点，IQ3 档更稳但吃内存。
- 只暴露 `/v1/chat/completions`（**无 `/v1/completions`**）。thinking 走 `reasoning_content`。支持原生 OpenAI tool-calling。
- 128K 单卡装得下：GPU 19.5G，RAM 用 45G/剩 15G（QSA 稀疏注意力 KV 涨慢）。

实测（单卡 20G + IQ2_XS + MTP）：短上下文 decode **101.8 t/s**（6B 激活，比稠密 27B 快）、并发总吞吐 c4 ~124–128 t/s（封顶）；prefill 2800–3000 t/s；满 83K-token 上下文 prefill TTFT 34s/~2400 t/s，decode 单流 92–123 t/s、并发2 总 41 t/s。

## 5. 用法：OpenAI 端点 + OpenCode 接入

三个服务都是 OpenAI 兼容，端口：9B→`:8000`，27B→`:8091`，Flash→`:8080`。
```
curl http://127.0.0.1:PORT/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"...","messages":[{"role":"user","content":"..."}],"max_tokens":256}'
```
接进 OpenCode v2（写进项目 `opencode.json`，`providers` 是复数，改动热重载不用重启）：
```jsonc
"providers": {
  "local27b": { "name":"...", "package":"@opencode/ai/providers/openai-compatible",
    "settings": { "baseURL":"http://127.0.0.1:8091/v1", "apiKey":"local", "chunkTimeout":300000 },
    "models": { "qwen3.8-27b": { "name":"...", "limit":{"context":65536,"output":8192} } } }
}
```
跑：`opencode run --model local27b/qwen3.8-27b --agent qa "<问>"`。用禁工具的 `qa` agent 做纯问答（本地模型跑 agentic 工具循环易乱）。完整配置见 `/data/qwen38-throughput/eval/opencode.json`。
- **Flash 模型 id**：strata 报 `qwen3.8-flash-next-iq2_xs`，在 models 里用 `"modelID"` 映射。
- **大坑**：OpenCode 的 `-f 附件会在 ~20K token 截断大文件！长文评测必须走 API 内联发送全文，别用 `-f`（实测直连 83K token 模型满分、经 `-f` 只送 20K）。

## 6. 评测资产（已建，可复用）

- 27B 长上下文多跳（24.8K token haystack，5 数学/代码题）：`/data/qwen38-throughput/eval/gen_haystack.py` + `run_eval.sh`。结果 27B 4/4、Flash IQ2_XS 3/4。
- Flash agentic coding + tool-call：`eval/agentic_eval.py`（read/write/run_tests 三工具修 bug，8 步通过）。
- Flash 128K 长文数学（83K token haystack）：`eval/gen_haystack_128k.py` + `eval/m128k_direct.py`（直连满分 566）。
- 吞吐压测：`scripts/bench.py`(9B)、`scripts/bench2.py`(27B)、`scripts/bench_flash.py`、`scripts/bench_128k_full.py`。
- 报告：`/data/qwen35-9b-throughput/README.md`、`/data/qwen38-throughput/README.md`。

## 7. 通用坑

- 后台跑 llama-server/strata/vllm 要 `setsid nohup … </dev/null & disown`；工具前台命令的 SIGTERM/SIGKILL 会连带杀未脱群的后台。脚本文件方式启动最稳。
- `pkill -f "xxx"` 的模式若出现在自己命令行里会**自杀**，用 `[x]xx` 括号法规避（如 `pkill -9 -f "[l]lama-server"`）。
- unsloth **9B** GGUF（含 UD-Q4_K_XL）**没有 MTP head**（427 张量无 mtp），llama.cpp `--spec-type draft-mtp` 起服即崩；官方 safetensors 有 15 个 `mtp.layers.0.*`，转换时丢了。27B 的 GGUF 则有。→ 9B 走 vLLM（MTP 来自权重内建）。
- HF 下载直连可用；匿名大文件会限速，用 `export HF_TOKEN="$(cat ~/.cache/huggingface/token)"`。
