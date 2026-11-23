---
name: lean-mathlib-local-path
description: 本地环境所有 Lean toolchain 与 Mathlib checkout 的绝对路径、版本、构建状态和磁盘占用总账，用于回答「哪个 mathlib 能用」「mathlib 在哪」「这个项目 pin 的哪个版本」「怎么切 toolchain」，并给出新增版本的可复现步骤。Use when the user asks where Mathlib/Lean lives locally, which checkout is built, how to point a project at a specific Mathlib rev, how to install another toolchain, or why `import Mathlib` is slow/missing. Triggers: local mathlib path, which mathlib, mathlib 在哪, 本地 mathlib, lean 版本, toolchain 路径, switch lean version, olean, lake env lean, cache get, runtime-436, lean-4.28-reap, formalpedia, prove2me 语料, AxiomMath Stacks, stacks project Lean, stacks tags, 源码索引.
---

# Lean / Mathlib 本地路径与状态总账

本地环境快照日期：**2026-11-08**。数字会变，权威数据用 §7 的脚本现算；本文件记录的是结构与判读方法。

## 0. 三十秒结论

| 需求 | 用这个 |
|---|---|
| 要最新栈（Lean + Mathlib `v4.36.0-rc2`） | `cd ~/lean-4.28-reap/runtime-436` |
| 要旧栈（`v4.28.0-rc1`，已有大量笔记/实验） | `cd ~/lean-4.28-reap/runtime` |
| 要 Prove2Me 语料（581k 文件，默认 Lean 4.33.1） | `cd ~/lean-4.28-reap/env-0df444a`；语料在 `../formalpedia/envs/0df444a` |
| 只想读 Mathlib 源码 / grep 定理名 | `/data/projects/lean-corpus/mathlib4`（源码全，无 olean） |
| 想要 2026-08 的 Mathlib 源码做对照 | `/data/projects/lean/mathlib`（部分构建，toolchain 缺失） |
| 要 AxiomMath/Stacks 源码 / tag 索引 / `StacksCore` | `/data/axiom-repos/Stacks`（`StacksCore` 已构建，可 `import StacksCore`）；索引在 `/data/axiom-repos/index/`（§3.6） |

两条铁律：

1. **能用 = toolchain 已安装 + olean 数量接近源文件数**。缺一个都只能读不能编。
2. **`~/.elan` 是符号链接**，指向 `~/lean-4.28-reap/elan`。删 `lean-4.28-reap` 会连带删掉**全部 10 个 toolchain（28G）**。

## 1. Toolchain 清单

elan 根目录：`~/lean-4.28-reap/elan`（`~/.elan` → 此处）
默认 toolchain：`leanprover/lean4:v4.28.0-rc1`（`settings.toml`，无 per-dir override）
总计约 **28G**。

| toolchain 目录 | Lean | commit | 大小 |
|---|---|---|---|
| `leanprover--lean4---v4.26.0` | 4.26.0 | `d8204c9f` | 2.5G |
| `leanprover--lean4---v4.28.0` | 4.28.0 | `7e01a1bf` | 2.6G |
| `leanprover--lean4---v4.28.0-rc1` | 4.28.0-rc1 | `3b0f2862` | 2.6G |
| `leanprover--lean4---v4.29.1` | 4.29.1 | `f72c35b3` | 2.7G |
| `leanprover--lean4---v4.33.0` | 4.33.0 | `d8b18978` | 2.9G |
| `leanprover--lean4---v4.33.0-rc1` | 4.33.0-rc1 | `62eed1db` | 2.9G |
| `leanprover--lean4---v4.33.1` | 4.33.1 | `819816b2` | 2.9G |
| `leanprover--lean4---v4.34.0-rc1` | 4.34.0-rc1 | `3447a668` | 2.9G |
| `leanprover--lean4---v4.35.0-rc4` | 4.35.0-rc4 | `c29b6dda` | 3.0G |
| `leanprover--lean4---v4.36.0-rc2` | 4.36.0-rc2 | `b35cb10c` | 3.1G |

**缺口**：`v4.33.0-rc2` 未安装（data disk 的 Mathlib 需要它）；`v4.35.0`、`v4.36.0` 正式版未安装。

## 2. Mathlib checkout 清单

| 路径 | rev | tag | 日期 | 需要 toolchain | olean | 大小 | 状态 |
|---|---|---|---|---|---|---|---|
| `~/lean-4.28-reap/mathlib4-0df444a` | `0df444a3` | 无 tag | 2026-08-21 | v4.33.1 ✅ | 8322 | 7.1G | **READY** |
| `~/lean-4.28-reap/runtime-436/.lake/packages/mathlib` | `9d581dff` | v4.36.0-rc2 | 2026-10-27 | v4.36.0-rc2 ✅ | 8685 | 6.9G | **READY** |
| `~/lean-4.28-reap/runtime/.lake/packages/mathlib` | `5352afcc` | v4.28.0-rc1 | 2026-01-26 | v4.28.0-rc1 ✅ | 7527 | 6.6G | **READY** |
| `/data/projects/lean-corpus/mathlib4` | `8f9d9cff` | v4.28.0 | 2026-02-16 | v4.28.0 ✅ | 0 | 134M | **SOURCE-ONLY** |
| `/data/projects/lean/mathlib` | `5edf93c0` | 无 tag | 2026-08-06 | v4.33.0-rc2 ❌ | 338 | 873M | **PARTIAL** |

状态判读：

- **READY** — `lake build` 秒级完成（缓存命中），可 `lake env lean` 编译任意 `import Mathlib` 文件。
- **SOURCE-ONLY** — 只有 `.lean` 源码（8314 个文件、`.git` 26M 的 partial clone、无 `.lake`）。适合 grep/阅读，不能 import。
- **PARTIAL** — 只解压了 338 个 olean（约 4%），且所需 toolchain 未装；直接 import 会失败。

## 3. 依赖 Mathlib 的项目

| 项目 | lean-toolchain | Mathlib 来源 | 状态 |
|---|---|---|---|
| `~/lean-4.28-reap/env-0df444a` | v4.33.1 | **path** 依赖 → `../mathlib4-0df444a` | READY，已编译 formalpedia 样本 |
| `~/lean-4.28-reap/runtime` | v4.28.0-rc1 | git `v4.28.0-rc1`（本地 6.6G） | 已构建，7913 jobs |
| `~/lean-4.28-reap/runtime-436` | v4.36.0-rc2 | git `v4.36.0-rc2`（本地 6.9G） | 已构建，18180 jobs，12s |
| `~/文档/lean-math-tactics-learning` | v4.28.0-rc1 | **path** 依赖 → `runtime/.lake/packages/mathlib` | 已构建（387M） |
| `~/oil-cn/lean-math-tactics-learning` | v4.28.0-rc1 | **path** 依赖 → 同上 | 已构建（387M，与上者各自独立副本） |

path 依赖的含义：这些项目**不复制** Mathlib，只是指向已有的那一份；被指向的 checkout 一动，它们跟着动。

## 3.5 Prove2Me formalpedia 语料

路径 `~/lean-4.28-reap/formalpedia`（full clone，30G；`.git` 6.88G）。它是 prove2.me 的每日快照，不是 Mathlib，也不能单独 `lake build`；编译要进配套项目 `env-0df444a`。

| env | Lean / Mathlib | 文件数 | 大小 | 状态 |
|---|---|---|---|---|
| `envs/0df444a`（默认） | v4.33.1 / `0df444a360eaa` | 516,252 | 21.6G | 可编译，样本通过 |
| `envs/c5ea003` | v4.30.0 / `c5ea00351c28` | 31,474 | 304M | 仅源码，未配 Mathlib |
| `envs/777aaa6` | v4.29.0-rc3 / `777aaa61dcd2` | 33,723 | 287M | 仅源码，未配 Mathlib |

默认环境合计 **161,763,691 行**（2026-11-04 快照）：定理 231,995 个（`.lean` 以 `by sorry` 结尾）、定义 75,869 个、已验收解答 208,388 个。

**没有 Lean 4.28 环境**——目录名 `lean-4.28-reap` 是 REAP 项目的历史命名，与语料版本无关。

编译语料文件时必须先复制到 `/tmp`，否则 `.olean`/`.ilean` 会写进 516k 文件的语料目录：

```bash
cd ~/lean-4.28-reap/env-0df444a
cp ../formalpedia/envs/0df444a/Solutions/Sol_Foo.lean /tmp/check.lean
lake env lean /tmp/check.lean
```

## 3.6 AxiomMath/Stacks（源码镜像 + StacksCore + tag 索引）

路径 `/data/axiom-repos/Stacks`（2026-11-08 clone，commit `5ed82d14`，9.0G 含 `.lake`）。这是 Axiom 对 Stacks Project 的 Lean 4 形式化。**`StacksCore` 已在本地构建，`StacksFrontier` 仍是源码**：`import StacksCore` 可用，`import Stacks` 不可用（需要 62,527 个 Frontier 模块）。

| 项 | 值 |
|---|---|
| 文件 | 62,975 个 `.lean`（StacksCore 445 / StacksFrontier 62,527） |
| 行数 | 18,119,030（物理行） |
| 源码 | 1,010 MB（StacksCore 1.8 MB / StacksFrontier 1,003 MB） |
| 声明（启发式） | 653,383 |
| Stacks tag | 16,259 个唯一 tag，41,663 次出现 |
| EGA / SGA | 4,847 / 4,501 条引用 |
| `sorry`（代码，去注释后） | 0 |

版本 pin：`lean-toolchain` = `leanprover/lean4:v4.35.0`；Mathlib = `v4.35.0` / `56a005855ea17e0b0958f73ec801ae140b0a1679`；根模块 `Stacks.lean` 同时 import `StacksCore` 和 `StacksFrontier`。

**当前状态（2026-11-08 19:40）**：`StacksCore` 已构建完成——4758 jobs、445 个 olean、`.lake/build` 400 MB，实测 **2 分 20 秒**（Mathlib cache 已就位）；再跑 `lake build StacksCore` 是 1.8 秒的 no-op。`StacksFrontier` 未构建，`import Stacks` 仍会失败。`.lake` 总计 7.6 GB（Mathlib 6.9 GB + Stacks 0.4 GB），整个 checkout 9.0 GB。

构建时按剩余资源的 60% 限流（本地环境 16 核 / 50 GB 可用 → 9 核 / 30 GB）：

```bash
systemd-run --user --scope -p CPUQuota=900% -p MemoryMax=30G -p MemoryHigh=26G \
  -p IOWeight=50 nice -n 10 ionice -c2 -n7 /bin/bash -lc \
  'export PATH=$HOME/.elan/bin:$PATH; cd /data/axiom-repos/Stacks; lake build StacksCore'
```

注意 **Lake 5.0 没有 `-j`/`--jobs`**（`lake build -j 6` 会报 `unknown short option '-j'`），并发由 Lake 自己决定，用 cgroup 的 `CPUQuota`/`MemoryMax` 限流；实测峰值内存约 12 GB。

索引产物在 `/data/axiom-repos/index/`：

- `INDEX.md` — 汇总
- `stats.json` — 全部计数
- `stacks_tags.tsv` — `tag, file, line, kind, decl, source`
- `ega_sga.tsv` — `ref, file, line, kind, decl, series`

刷新：

```bash
cd /data/axiom-repos/Stacks && git pull --ff-only
python3 /data/axiom-repos/tools/index_stacks.py \
  /data/axiom-repos/Stacks -o /data/axiom-repos/index
```

脚本约 5–6 分钟（63k 文件、1 GB；逐行去注释后再统计）。**缓存现状（2026-11-08）**：官方没有发布任何 `.olean` / `.lake/build` 缓存，README 只说 “planned”；GitHub releases/artifacts 为空，26 个 fork、HuggingFace、Docker Hub、GHCR、Reservoir 均无。公开渠道唯一可用的是 Mathlib 官方缓存（约 7 GB），不含 Stacks；本地 `StacksCore` 缓存见上。

要从零复现：装 `leanprover/lean4:v4.35.0`，`lake update` 拉 Mathlib v4.35.0 并自动 `cache get`（本地环境约 10 分钟、7 GB），然后 `lake build StacksCore`（实测 2 分 20 秒）。`StacksFrontier` 62,527 文件，冷编译约 2–6 天、产物约 30–50 GB，放后台断点续跑；**不要裸跑 `lake build`**，默认目标会连 Frontier 一起建。

## 4. 常用操作

**编译一个临时文件（推荐 `lake env lean`，不要在项目外裸跑 `lean`）**

```bash
cd ~/lean-4.28-reap/runtime-436
lake env lean /path/to/File.lean
```

**交互式检查 / 打印版本**

```bash
cd ~/lean-4.28-reap/runtime-436 && lake env lean --version
cd ~/lean-4.28-reap/runtime-436 && printf 'import Mathlib\n#check Nat.Prime\n' | lake env lean --stdin
```

`lean` 没有 `-e` 选项；一次性检查走 `--stdin`，且必须自己带上 `import Mathlib`。

**给新项目 pin 某个 Mathlib 版本**

```bash
mkdir -p ~/proj && cd ~/proj
printf 'leanprover/lean4:v4.36.0-rc2\n' > lean-toolchain
cat > lakefile.toml <<'EOF'
name = "proj"
defaultTargets = ["Proj"]

[[require]]
name = "mathlib"
scope = "leanprover-community"
git = "https://github.com/leanprover-community/mathlib4"
rev = "v4.36.0-rc2"

[[lean_lib]]
name = "Proj"
EOF
elan toolchain install leanprover/lean4:v4.36.0-rc2   # 若尚未安装
lake update mathlib     # 克隆 + 自动跑 cache get（post-update hook）
lake build
```

**不复制 7G：用 path 依赖指向已有 checkout**

```toml
[[require]]
name = "mathlib"
path = "~/lean-4.28-reap/runtime-436/.lake/packages/mathlib"
```

代价：不再受 `lake update` 管理，版本由被指向的 checkout 决定。

**判断某个 checkout 到底能不能用**

```bash
d=/path/to/mathlib
find "$d/.lake/build/lib/lean" -name '*.olean' | wc -l   # 应 ≈ 源文件数
find "$d" -name '*.lean' | wc -l                          # 分母
cd "$d/../../.." && lake build                            # 最权威（上溯到项目根）
```

## 5. 坑

- **Lean 4.36 的 module system**：Mathlib `v4.36.0-rc2` 按模块系统构建。文件首行不加 `module` 时，每个 `import Mathlib` 都会 warning：

  ```lean
  module

  import Mathlib
  ```

  加了之后 `lake env lean` 反而更快（本地环境 24s → 2.6s 量级）。
- **裸 `lean`/`lake` 用默认 toolchain `v4.28.0-rc1`**，不是最新版。要么先 `cd` 进带 `lean-toolchain` 的项目，要么 `elan run leanprover/lean4:v4.36.0-rc2 -- ...`。
- **`/data` 是 NTFS（rw）**，该 checkout 有未提交修改（`.devcontainer/` 等）；不要假设它干净可更新。
- **`/data` 是外置盘，设备号变过**（曾为 `nvme1n1p3`，现为 `nvme1n1p1`），内容随之换过：早前那份 4.7G 的 mathlib 已不在，现为 134M 源码副本。引用前先 `df -h /data` + 数 olean。
- **缓存目录不是 checkout**：`~/.cache/mathlib`（24907 个 `.ltar`，1.3G）与 `~/.opencode2/cache/mathlib`（25644 个，1.3G）只是 `lake exe cache get` 的下载缓存，不能 import，也不能当 Mathlib 用；换版本后基本失效，可删。
- **`lake update` 会自动跑 `cache get`**（Mathlib 的 post-update hook），所以看到几万文件下载属正常，不必手动再跑一次。
- **formalpedia 语料不要原地编译**：`lake env lean path/to/Sol_*.lean` 会在 516k 文件的目录里生成 `.olean`/`.ilean`。先 `cp` 到 `/tmp` 再编译；定理文件以 `sorry` 结尾，只检查语句是否成立。
- **AxiomMath/Stacks 的 `StacksCore` 已 READY，`StacksFrontier` 没有**：`StacksCore` 有 445 个 olean（400 MB），`import StacksCore` 可用；`import Stacks` 会拉 62,527 个未编译的 Frontier 模块。不要裸跑 `lake build`，用显式 target `lake build StacksCore`。
- **Lake 5.0 没有 `-j`/`--jobs`**：`lake build -j 6` 直接报 `unknown short option '-j'`；限资源用 systemd `CPUQuota`/`MemoryMax` + `nice`/`ionice`，不要让 Lake 自己开满核。
- **Stacks 的 toolchain 是 `v4.35.0` 正式版**：本地环境原本只有 `v4.35.0-rc4`；rc4 编出的 olean 与 v4.35.0 不兼容，必须先 `elan toolchain install leanprover/lean4:v4.35.0`（2026-11-08 已装）。
- **`StacksFrontier.lean` 是 5.5 MB 的根文件**，列了 62,527 个 import；`import Stacks` 会拉全库。日常只 `import StacksCore`（445 文件）。
- **网上没有 Stacks 编译缓存**（2026-11-08 全网核查）：官方 releases/artifacts 为空，README 只说 “planned”；本地环境 `StacksCore` 的 `.lake/build`（400 MB）就是当前唯一可用缓存，`StacksFrontier` 仍需自己编。

## 6. 版本对照（2026-11-04 远端）

| | 最新稳定 | 最新预发布 |
|---|---|---|
| Lean | `v4.35.0`（2026-10-12） | `v4.36.0-rc2`（2026-10-27） |
| Mathlib | `v4.35.0`（2026-10-13） | `v4.36.0-rc2`（2026-10-28） |

Mathlib4 的 tag 与 Lean 版本号一一对应；`mathlib4/master` 当前 pin `v4.36.0-rc2`。

2026-11-08 追加：AxiomMath/Stacks 已镜像并构建 `StacksCore`，pin Lean `v4.35.0` / Mathlib `v4.35.0`；官方编译缓存仍未发布。

## 7. 刷新本清单

```bash
~/.config/opencode/skills/lean-mathlib-local-path/scripts/inventory.sh        # markdown
~/.config/opencode/skills/lean-mathlib-local-path/scripts/inventory.sh --tsv  # 机器可读
```

脚本行为：枚举 `$ELAN_ROOT/toolchains/*`；发现 `$HOME` 下深度 ≤6 的 `*/.lake/packages/mathlib`、顶层 `mathlib4-*` checkout（须有 `lean-toolchain`），外加两个磁盘上的语料目录和 `LEAN_CORPORA` 数组里的 formalpedia、`/data/axiom-repos/Stacks`；对每个 checkout 报 rev、tag、日期、`lean-toolchain`、olean 数、大小；最后列缓存目录。新增顶层 Mathlib 后无需改脚本；新增语料把路径加到脚本的 `LEAN_CORPORA` 数组。

Stacks 的 tag 索引单独用：

```bash
python3 ~/.config/opencode/skills/lean-mathlib-local-path/scripts/stacks_index.py \
  /data/axiom-repos/Stacks -o /data/axiom-repos/index
```

它会扫 62,975 个 `.lean`、去注释后统计 tag/EGA/SGA/声明/`sorry`，输出 `stats.json`、`stacks_tags.tsv`、`ega_sga.tsv`、`INDEX.md`，约 5–6 分钟。

## 8. 新增一个版本的成本（实测）

| 步骤 | 命令 | 时间 | 磁盘 |
|---|---|---|---|
| toolchain | `elan toolchain install leanprover/lean4:vX` | 1–3 min | ~3G |
| 克隆 + 解析 | `lake update mathlib` | 5–15 min | ~5G（含历史） |
| 预编译 olean | 自动（post-update hook），或 `lake exe cache get` | 10–30 min | ~7G |
| 验证 | `lake build` | 10–30 s | — |

合计约 15G、30–60 min，瓶颈全在网络。想省 4G/10min 可 `git clone --depth 1 --branch vX` 后改用 path 依赖，代价是失去 `lake update` 管理。

本次 formalpedia 实测（2026-11-04）：full clone 7G pack → 30G checkout，约 40 min；Mathlib depth-1 fetch + `cache get` 约 3 min（缓存服务器命中），`env-0df444a` 总计 394M。
