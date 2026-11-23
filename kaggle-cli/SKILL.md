---
name: kaggle-cli
description: 用 Kaggle CLI 跑 2×Tesla T4 GPU kernel、管理每周 GPU/TPU 配额、把 Kaggle Dataset 当跨会话持久存储（20GB /kaggle/working vs 100–200GB dataset），并附本地环境实测的上传/下载速度与 GPU 时间成本。Use when the user asks about Kaggle CLI, Kaggle GPU/T4, kaggle quota, kernel push/status/logs/output, dataset create/version/attach, moving data to/from Kaggle, or how much GPU quota an upload/download burns. Triggers: kaggle cli, kaggle gpu, T4, kaggle dataset, 上传数据集, kaggle 配额, kernel push, /kaggle/working, 20GB, 100GB dataset, kaggle 速度.
---

# Kaggle CLI：2×T4 GPU 与 Dataset 持久存储

## 0. 一句话结论

- 免费账号拿到的是 **2×Tesla T4（各 15.36GB）**；L4 请求会被静默回落成 T4，P100 已于 2026-09-15 下线。
- **30 GPU 小时/周**（TPU 20h/周），周六 00:00 重置；只有 kernel 处于 `RUNNING` 的时间计费，排队不算。
- `/kaggle/working` 只有 **20GB** 且随会话消失；Dataset 是**版本化上传**的持久存储（官方文档 200GB/数据集，部分账号/旧文档 100GB），不是可写挂载盘。
- 本地环境（the university）到 Kaggle 的实测吞吐约 **15 MB/s**，T4 读挂载 dataset 约 **98 MB/s**，HuggingFace 约 **132 MB/s**，GitHub 约 **5.6 MB/s**。
- 从本地或 CPU kernel 建 dataset **不花 GPU 时间**；在 GPU kernel 里传数据**会**按墙钟烧 GPU 配额。

## 1. 账号配额与硬件（2026-11-02 实测）

```bash
kaggle quota            # GPU/TPU 周配额
kaggle quota --format json
```

```
resource  used    remaining  total    refreshAt
GPU       0.04h   29.96h     30.00h   2026-11-07T00:00:00
TPU       0.00h   20.00h     20.00h   2026-11-07T00:00:00
```

CLI 版本：本地环境 2.2.5。升级命令（注意本地环境 `XDG_DATA_HOME=~/.opencode2/share` 会干扰 pipx）：

```bash
PIPX_HOME=~/.local/share/pipx PIPX_BIN_DIR=~/.local/bin pipx upgrade kaggle
```

2.2.5 起才有 `kaggle b quota`（美元 AI 额度）；`kaggle quota` 是 GPU/TPU 小时，两者不同。

实测硬件（T4 kernel 内 `nvidia-smi` + torch）：

| 项 | 值 |
|---|---|
| GPU | 2 × Tesla T4，15360 MiB/卡，compute capability 7.5 |
| CUDA / torch | CUDA 可用，torch 2.11.0+cu128 |
| CPU / RAM | 4 vCPU / 31 GB |
| 单次会话 | CPU/GPU 12h、TPU 9h（官方文档；老帖有 9h 说法，以界面为准） |
| 队列 | 实测排队 5–15 分钟，**不计入 GPU 配额** |
| L4 | 不可用：`machine_shape=NvidiaL4` 或 `--accelerator NvidiaL4/nvidiaL4` 都回落成 T4×2 |

## 2. 存储地图

| 路径 | 容量 | 持久性 | 备注 |
|---|---|---|---|
| `/kaggle/working` | **20GB**（`/dev/loop2` ext4） | 作为 kernel 输出保存，可下载 | 写 221 MB/s；超过 20GB 会失败 |
| `/kaggle/input` | 随 dataset（最大 100–200GB） | 只读，gcsfuse | 读 98 MB/s |
| `/dev/shm` | 14GB | 会话内，重启即失 | 内存盘，写 2.4 GB/s |
| `/tmp`、`/` | overlay，约 1TB 可用 | 会话内，随时可能被清 | 写 170 MB/s；**不要当持久盘** |
| `/kaggle/temp` | 不存在 | — | 2026-11 实测没有这个目录 |
| Kaggle Dataset | 100–200GB/数据集 | 永久、版本化 | 上限 50 个顶层文件 |

**CPU / GPU / TPU 不分区存储**：三种 accelerator 用的是同一套容器布局和同一份账号级 dataset。2026-11 实测 CPU 与 T4 完全一致（20GB `/kaggle/working`、14GB `/dev/shm`、4 vCPU / 31GB RAM）。切换 accelerator 不会带来新磁盘，也不会保留上一会话的 `/kaggle/working`；跨会话只能靠 dataset 或 notebook 输出。TPU 用同一镜像布局（官方文档同样写 20GB），只是后端机器不同。

## 3. GPU kernel 用法

`kernel-metadata.json`（最小可用）：

```json
{
  "id": "你的用户名/my-gpu-job",
  "title": "my-gpu-job",
  "code_file": "main.py",
  "language": "python",
  "kernel_type": "script",
  "is_private": true,
  "enable_gpu": true,
  "enable_tpu": false,
  "enable_internet": true,
  "machine_shape": "NvidiaTeslaT4",
  "dataset_sources": [],
  "competition_sources": [],
  "kernel_sources": [],
  "model_sources": []
}
```

```bash
kaggle kernels push   -p .                      # 提交并自动开跑
kaggle kernels push   -p . --accelerator NvidiaTeslaT4
kaggle kernels status 用户名/my-gpu-job
kaggle kernels logs   用户名/my-gpu-job          # -f 实时跟随
kaggle kernels output 用户名/my-gpu-job -p ./out # 下载 /kaggle/working 产物
kaggle kernels pull   用户名/my-gpu-job -p ./src -m
kaggle kernels delete 用户名/my-gpu-job -y
```

要点：

- `enable_gpu: true` 即可，`machine_shape` 不写也是 T4×2
- 输出必须写到 `/kaggle/working/`，否则 `kernels output` 拿不到
- 默认**没有网络**，要联网必须 `"enable_internet": true`
- 挂 dataset：`"dataset_sources": ["owner/slug"]`，只读
- 长任务自己写 checkpoint；会话到点会被杀

## 4. Dataset 当持久盘（20GB → 100/200GB）

Dataset 不是可写文件系统，而是**上传一个版本、只读挂载**。跨会话保存大文件的正确姿势：

```bash
mkdir -p ~/mydata && cd ~/mydata
kaggle datasets init -p .        # 生成 dataset-metadata.json
# 编辑 title / id / licenses
kaggle datasets create -p . -r zip          # 默认 private
kaggle datasets status 用户名/my-dataset     # 等 ready
kaggle datasets version -p . -m "v2: add shard" -r zip
kaggle datasets files 用户名/my-dataset
kaggle datasets download -d 用户名/my-dataset -p ./dl
```

`dataset-metadata.json`：

```json
{
  "title": "my-dataset",
  "id": "用户名/my-dataset",
  "licenses": [{ "name": "CC0-1.0" }]
}
```

在 kernel 里用：

```json
"dataset_sources": ["用户名/my-dataset"]
```

挂载路径（2026-11 实测）：`/kaggle/input/datasets/<owner>/<slug>/`；旧布局是 `/kaggle/input/<slug>/`。**不要硬编码**，用：

```bash
find /kaggle/input -maxdepth 3 -type d
```

限制与坑：

| 项 | 规则 |
|---|---|
| 单数据集大小 | 官方文档 200GB；旧文档/部分账号 100GB，以数据集页面配额为准 |
| 私有总量 | 200GB（超过就要转 public 或删旧数据集） |
| 顶层文件数 | **最多 50 个**；多了放子目录或打成一个压缩包 |
| 单文件 | 建议 <20GB，超大文件分片 |
| 目录 | 默认 `-r skip` **直接忽略子目录**！要传目录必须 `-r zip` 或 `-r tar` |
| 表格文件 | 默认自动转 CSV；要保留原格式加 `-t/--keep-tabular` |
| 可见性 | 默认 private；`-u/--public` 才公开，公开必须有 license |
| 刚创建就下载 | 可能 404；等 `status=ready` 后再等 30–60s |
| 在 kernel 里推 dataset | 默认**没有** `KAGGLE_USERNAME`/`KAGGLE_KEY`，CLI 未认证；需要把 token 配成 Kaggle Secret |

## 5. 能往 Dataset 上传什么

基本是**任意文件**：

- 数据：CSV / Parquet / JSON / JSONL / SQLite / HDF5 / NPZ
- 模型：`.safetensors`、`.bin`、`.gguf`、`.onnx`、checkpoint
- 媒体：图片、音频、视频、PDF
- 代码/二进制：源码、编译好的可执行文件、`.so`、wheel、conda pack
- 压缩包：zip / tar / tar.gz / 7z（推荐，规避 50 文件限制）

不允许：侵权内容、恶意软件、隐私数据、违反 Kaggle Terms 的东西。公开数据集必须能合法再分发。

## 6. 实测传输速度（the university 服务器，2026-11-02）

### 6.1 本地环境 ↔ Kaggle

| 路径 | 方向 | 速度 | 样本 |
|---|---|---|---|
| `kaggle datasets create` | 本地环境 → Kaggle | **15.3 MB/s** | 512MiB / 35.0s |
| `kaggle datasets download` | Kaggle → 本地环境 | **14.8 MB/s** | 512MiB / 36.2s |
| `kaggle kernels output` | kernel 输出 → 本地环境 | **8.5 MB/s** | 512MiB / 60.4s |

**没有"实例 ↔ 本地环境"直连通道**：实例在内网、没有公网入口，本地环境也不在 Kaggle 内网。所有本地互通只能走 `kaggle kernels output`（8.5 MB/s）或 `kaggle datasets`（约 15 MB/s）。想更快就从实例直接拉 HF/GitHub，或在实例内算完只回传结果。

### 6.2 T4 实例 ↔ 外部

| 路径 | 方向 | 速度 | 样本 |
|---|---|---|---|
| `/kaggle/input`（gcsfuse） | 读 | **98.3 MB/s** | 512MiB |
| HuggingFace | 下载 | **132.2 MB/s** | gpt2 548MB / 4.2s |
| HuggingFace | 上传 | **33.1 MB/s** | 256MiB / 8.1s（T4 + Kaggle Secret） |
| GitHub（linux tar） | 下载 | **5.6 MB/s** | 274MB / 48.9s |
| Cloudflare `__up` | 上传 | **29.0 MB/s** | 256MiB / 9.3s |
| Kaggle API（无凭据） | 下载 | 403 | 需要认证 |
| 实例 → Kaggle Dataset | 上传 | 未直接测到 | kernel 内无凭据；API 上限参考 15 MB/s |

### 6.3 本地环境基线

| 路径 | 速度 |
|---|---|
| Cloudflare 下行 | 64.2 MB/s |
| Cloudflare 上行 | 59.9 MB/s |
| HuggingFace 下载（公开 gpt2） | 80.9 MB/s |
| HuggingFace 下载（私有 512MiB） | 40.2 MB/s |
| **HuggingFace 上传（512MiB）** | **14.4 MB/s**（37.4s） |
| HuggingFace 上传（256MiB） | 14.4 MB/s（18.7s） |
| GitHub 下载 | 6.7 MB/s |

### 6.4 实例本地磁盘

| 路径 | 写 | 读 |
|---|---|---|
| `/kaggle/working` | 221 MB/s | 3.8 GB/s（page cache） |
| `/tmp`（overlay） | 170 MB/s | 2.9 GB/s（page cache） |
| `/dev/shm` | 2450 MB/s | 5086 MB/s |

### 6.5 换算成时间

| 数据量 | 路径 | 预计 |
|---|---|---|
| 20GB 输出 | kernel → 本地环境（8.5 MB/s） | ≈ 40 分钟 |
| 20GB | Kaggle dataset → 本地环境（14.8 MB/s） | ≈ 23 分钟 |
| 20GB | 本地环境 → Kaggle dataset（15.3 MB/s） | ≈ 22 分钟 |
| 100GB | dataset 挂载读取（98 MB/s） | ≈ 17 分钟（不计 GPU 的话仍是 0.28h） |
| 100GB | HF 下载（132 MB/s） | ≈ 13 分钟 |
| 100GB | GitHub 下载（5.6 MB/s） | ≈ 5 小时（别这么干） |

## 7. 会不会花 GPU 时间？

**会，但不是因为"上传/下载"本身，而是因为 kernel 在跑。**

| 操作 | GPU 配额 |
|---|---|
| 本地环境 `kaggle datasets create/version/download` | **0** |
| CPU kernel 里建 dataset / 传数据 | **0**（CPU kernel 不扣 GPU） |
| GPU kernel 里 `kaggle datasets version` | **按墙钟计**：512MB @15MB/s ≈ 35s ≈ 0.01h |
| GPU kernel 启动时下载 10GB dataset | 挂载是懒加载，读 10GB @98MB/s ≈ 102s ≈ 0.03h |
| GPU kernel 里从 HF 下 10GB | ≈ 76s ≈ 0.02h |
| 排队等 T4 | **0**（实测排队 10 分钟，配额只涨了 0.02h） |

计算式：

```
GPU 小时 = (下载 + 上传 + 计算 + 等待) 的 RUNNING 墙钟 / 3600
```

省钱原则：

1. 数据准备、清洗、打包、上传全部放在**本地环境或 CPU kernel**。
2. GPU kernel 只做真正需要 GPU 的计算；启动时直接挂载 dataset。
3. 大文件先压成 tar/zip，减少文件数和传输开销。
4. 输出 <20GB 才写 `/kaggle/working`；超过就分片，或写到 `/dev/shm` 临时处理后再压缩。

## 8. 常见坑

- **L4 拿不到**：写 `NvidiaL4` 不报错，但实际给你 T4×2，别以为用上了 L4。
- **`/kaggle/temp` 不存在**：临时文件用 `/tmp` 或 `/dev/shm`。
- **子目录被忽略**：`kaggle datasets create` 默认 `-r skip`，目录不会上传。
- **顶层文件 >50**：直接失败或截断；打包或分子目录。
- **刚建完 404**：等 `status=ready` 再等 30–60s。
- **`kaggle datasets list -m` 显示 size 0**：刚创建时的显示问题，`files` 能看到实际大小。
- **kernel 里没有 Kaggle 凭据**：`KAGGLE_USERNAME`/`KAGGLE_KEY` 都是空，想在 kernel 里推 dataset 必须用 Kaggle Secret。
- **输出下载比 dataset 慢**：8.5 vs 14.8 MB/s；大批量结果优先走 dataset。
- **tabular 自动转 CSV**：Parquet 也会被转，除非 `-t`。
- **`/kaggle/working` 20GB 是硬上限**：不是剩余空间，是 loop 设备大小。

## 9. HuggingFace / GitHub CLI 与 token

**不用装**：Kaggle 镜像（2026-11 实测）已经自带

```
hf / huggingface-cli      /usr/local/bin（huggingface_hub 1.29.0）
gh                        /usr/bin（GitHub CLI）
git                       /usr/bin
huggingface_hub 1.29.0 / datasets 4.8.5 / transformers 5.16.1 / kagglehub 1.0.2
kaggle_secrets           可 import
git-lfs                  缺失（只有需要 GitHub LFS 仓库时才装）
```

本地环境（the university 服务器）也已经装好：`hf 2.4.0`、`gh 2.103.3`；`gh` 已登录，`hf` 已登录（`WufuJu`，org `alpha-proof-open-source`）。私有 repo 512MiB 上传实测 **14.4 MB/s**，下载 **40.2 MB/s**。

**token 存哪里**

| 环境 | 推荐位置 | 说明 |
|---|---|---|
| 本地环境 | `hf auth login` → `~/.cache/huggingface/token`（600） | 一次登录，长期有效 |
| 本地环境 | `gh auth login` → `~/.config/gh/hosts.yml`（600） | 已经登录过 |
| Kaggle | **Kaggle Secrets**（Add-ons → Secrets） | 账号级创建，但必须 attach 到具体 notebook |
| ❌ 不要 | Kaggle Dataset / `/kaggle/working` / metadata | dataset 可被共享、有版本历史；工作区每次清空 |

**Secrets 的三个硬规则（实测踩过）：**

1. 创建 Secret 只是账号级；还要在 **Notebook Editor → Add-ons → Secrets** 里把对应 label 的勾选框打开，attach 到这个 notebook。
2. `kaggle kernels push` **不能** attach secret（Kaggle CLI #582）；CLI 推出来的 kernel 如果没在 UI 里 attach，`get_secret` 会报 `HTTP 400 / ConnectionError`。
3. 浏览器里开着 draft 时**不要**同时用 CLI push，否则 `Save Version` 会报：
   `ConcurrencyViolation Sequence number must match Draft record ... ExpectedSequence=5, ActualSequence=4`
   正确顺序：UI 勾选 secret → `Save Version → Save & Run All` → 之后 CLI 只读查询。

kernel 里读 Secret：

```python
import os
from kaggle_secrets import UserSecretsClient

secrets = UserSecretsClient()
os.environ["HF_TOKEN"] = secrets.get_secret("HF_TOKEN")
os.environ["GH_TOKEN"] = secrets.get_secret("GH_TOKEN")
```

常用命令：

```bash
# 公开模型不需要 token；gated 模型（Llama 等）需要 HF_TOKEN
hf download openai-community/gpt2 --local-dir /kaggle/working/gpt2
hf download meta-llama/Llama-3.1-8B --token "$HF_TOKEN" --local-dir /kaggle/working/llama

# 公开仓库
git clone --depth 1 https://github.com/org/repo.git
gh repo clone org/repo -- --depth 1

# 私有仓库（不需要 gh）
git clone https://x-access-token:${GH_TOKEN}@github.com/org/private-repo.git
```

注意：

- 下载公开 HF 模型/数据集**不需要** token；只有 gated/private 需要，且要先在网页同意条款。
- `git-lfs` 只在 GitHub LFS 仓库需要；HF 的 LFS/Xet 由 `hf` 自己处理。
- 不要把 token 写进 `kernel-metadata.json` 或 `dataset-metadata.json`，这些文件会被上传并保存在版本历史里。

## 10. 可复用脚本

- `scripts/kernel-metadata.json` — GPU kernel 模板
- `scripts/probe.py` — 打印 GPU/CPU/磁盘/挂载信息
- `scripts/speedtest.py` — 测磁盘、dataset 读取、GitHub/HF 下载（需在 kernel 里跑）
- `scripts/hf_upload_t4.py` — 读 `HF_TOKEN` Secret，测 T4 → HuggingFace 上传速度
- `scripts/dataset-metadata.json` — dataset 模板

## 11. 快速自检清单

```bash
kaggle quota                                   # 还有多少 GPU 小时
kaggle kernels status 用户名/kernel             # QUEUED/RUNNING/COMPLETE
kaggle datasets status 用户名/dataset           # ready?
kaggle datasets files 用户名/dataset            # 实际文件与大小
```

跑一次 probe（把 `scripts/probe.py` 当 `code_file`，metadata 用模板）：

```bash
mkdir -p ~/kprobe && cd ~/kprobe
cp ~/.config/opencode/skills/kaggle-cli/scripts/probe.py ./main.py
cp ~/.config/opencode/skills/kaggle-cli/scripts/kernel-metadata.json .
# 改 id/title/code_file 后：
kaggle kernels push -p .
kaggle kernels logs  用户名/kprobe
```
