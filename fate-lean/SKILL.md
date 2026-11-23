---
name: FATE-Lean
description: FATE（Formal Algebra Theorem Evaluation）benchmark 的本地环境总账：FATE-M/H/X 三个子基准的绝对路径、Lean 4.28.0 + Mathlib 4.28.0 版本 pin、已构建状态、重建与缓存命令，以及配合 lean-lsp MCP 做证明的方式。Use when working on the FATE benchmarks, proving the `sorry`s in FATE-M/H/X, checking which Lean/Mathlib version FATE pins, rebuilding the shared Mathlib checkout or its cache, or calling lean-lsp MCP tools on FATE files. Triggers: FATE, FATE-M, FATE-H, FATE-X, frenzymath, lean-fate-related, Formal Algebra Theorem Evaluation, Mathlib v4.28.0, 8f9d9cff, lake build, cache get, lean-lsp, sorry 补全, FATE benchmark.
---

# FATE-Lean：FATE benchmark 本地环境

快照日期：**2026-11-13**。所有数字以 `scripts/status.sh` 现算为准。

## 0. 三十秒结论

| 需求 | 用这个 |
|---|---|
| 做题 / 改证明 | `/data/lean-fate-related/FATE/FATE-M|FATE-H|FATE-X` |
| 共享 Mathlib（已编译） | `/data/lean-fate-related/mathlib4` |
| 重装 Mathlib 缓存 | `MATHLIB_CACHE_DIR=/data/lean-fate-related/cache/mathlib lake exe cache get` |
| 一键重建三个基准 | `/data/lean-fate-related/build-all.sh` |
| 看当前状态 | `~/.config/opencode/skills/fate-lean/scripts/status.sh` |

**全部在 `/data`（外置盘），不占 `/home`。** 总计约 9.4G。

## 1. FATE 是什么

`https://github.com/frenzymath/FATE`，抽象代数 / 交换代数定理证明评测集，是壳仓库 + 三个 submodule：

| 子基准 | 题数 | 定位 | 上游 commit |
|---|---|---|---|
| FATE-M | 150 | 本科教材习题 | `4eb33c8ccd0ff058b461cd763cc406509129743f`（tag v4.28.0） |
| FATE-H | 100 | 本科/研究生期末、资格考 | `17967b3118082adfba7c5a5fc03b5f4a53717b59`（tag v4.28.0） |
| FATE-X | 100 | PhD qualifying 及以上 | `a6fb49ee85fd05bb8ce9fc66e1c66797b5a0592d`（tag v4.28.0） |

每个 `.lean` 文件包含：一条完整形式化的陈述 + 一个 `sorry`，前置自然语言注释；FATE-M/H 不带额外定义，FATE-X 会带少量依赖定义。目录内另有每套基准的 `FATE-*.json` / `FATE-*.pdf`。FATE-M 是 REAL-Prover（arXiv 2505.20613）所用 benchmark 的重构版。

## 2. 版本（三套完全一致）

| 项 | 值 |
|---|---|
| Lean | `leanprover/lean4:v4.28.0`（**正式版**，不是 rc1） |
| Mathlib | `v4.28.0`，rev `8f9d9cff6bd728b17a24e163c9402775d9e6a365` |
| 直接依赖 | 只有 Mathlib |
| 传递依赖 | batteries / aesop / Qq / Proofwidgets4 / importGraph / LeanSearchClient / lean4-cli / plausible（由 Mathlib manifest 固定） |

本地环境 `~/.elan` 已装 `v4.28.0`。elan 默认是 `v4.28.0-rc1`，但每个 FATE 目录都有 `lean-toolchain`，`cd` 进去后 `lake` 会自动切到 4.28.0。

## 3. 本地布局

```text
/data/lean-fate-related/
├── FATE/                     # 2.6G，壳仓库 + 三个子模块
│   ├── FATE-M/               # 986M（.lake/packages 387M，151 olean）
│   ├── FATE-H/               # 788M（.lake/packages 387M，101 olean）
│   └── FATE-X/               # 790M（.lake/packages 387M，101 olean）
├── mathlib4/                 # 6.5G，v4.28.0 的完整 checkout + 已解压 olean（6.0G build）
├── cache/mathlib/            # 405M，官方 .ltar 缓存（MATHLIB_CACHE_DIR）
├── build-all.sh              # 顺序构建三个项目
├── README.md                 # 同内容的简短版
├── cache-get.log             # cache get 日志
└── build-all.log             # 构建日志（含 300+ 条 sorry warning）
```

`mathlib4/` 是从 `/data/projects/lean-corpus/mathlib4`（同为 `8f9d9cff`、纯源码无 olean）复制出来的独立副本；改原件不会影响它。

## 4. 与上游的差异

三个 `FATE-*/lakefile.lean` 的 mathlib 依赖由 git 改成 path：

```lean
require mathlib from "/data/lean-fate-related/mathlib4"
```

原 `lake-manifest.json` 重命名为 `lake-manifest.json.git-backup`，由 Lake 按 path 依赖重新生成。效果：三套基准共用一份 6G 构建产物，而不是各克隆一份 Mathlib（否则 3 × 7G）。

## 5. 构建 / 重建

```sh
/data/lean-fate-related/build-all.sh            # 三个都建
/data/lean-fate-related/build-all.sh FATE-X     # 只建一个
```

脚本等价于：

```sh
export PATH="$HOME/.elan/bin:$PATH"
export MATHLIB_CACHE_DIR=/data/lean-fate-related/cache/mathlib
cd /data/lean-fate-related/FATE/FATE-M && lake build
```

实测（2026-11-13，缓存已就位）：

- `cache get`：8010 个 `.ltar`，约 6–8 分钟（主站 Cloudflare 对该 commit 返回 404，实际走 Azure `lakecache.blob.core.windows.net`，速度 100–300 KB/s）。
- 构建：FATE-M 8177 jobs，FATE-H / FATE-X 各 8127 jobs；三套合计约 10 分钟（16 核）。
- 每个题文件结尾是 `sorry`，构建成功但会有 `declaration uses 'sorry'` warning，这是 benchmark 的正常形态。FATE-H/51.lean 另有一条 `Finset.toSet` deprecated 警告，不影响。

只重装 Mathlib 缓存（不重新下载，因为 `.ltar` 已在 `cache/mathlib`）：

```sh
cd /data/lean-fate-related/mathlib4
export PATH="$HOME/.elan/bin:$PATH"
export MATHLIB_CACHE_DIR=/data/lean-fate-related/cache/mathlib
lake exe cache get
```

## 6. 配合 lean-lsp MCP

OpenCode V2 的 MCP 已在全局配置 `~/.opencode2/config/opencode/opencode.json` 里注册为 `lean-lsp`（stdio，按文件路径自动识别项目），不需要为 FATE 单独配置。服务器本体是 `~/.opencode2/bin/lean-lsp-mcp`（`uv tool install lean-lsp-mcp`，v0.33.0），配置里显式给了含 `~/.elan/bin` 的 `PATH`——V2 服务进程默认 PATH 里没有 elan，不补就会找不到 `lake`。

常用调用（Code Mode 下在 `execute` 里）：

```js
await tools["lean-lsp"].lean_goal({ file_path: ".../FATE/FATE-M/FATEM/1.lean", line: 9 })
await tools["lean-lsp"].lean_diagnostic_messages({ file_path: "..." })
await tools["lean-lsp"].lean_multi_attempt({ file_path: "...", line: 8, attempts: ["simp", "ring", "omega"] })
await tools["lean-lsp"].lean_local_search({ query: "prod_card", project_root: ".../FATE-M" })
```

已验证：对 `FATE-M/FATEM/1.lean` 第 9 行（`sorry`）调用 `lean_goal`，返回

```text
G : Type u_1
inst✝¹ : Fintype G
inst✝ : Group G
n : ℕ
⊢ Fintype.card (Fin n → G) = Fintype.card G ^ n
```

即 Mathlib olean 与 LSP 链路正常。首次进入某个 FATE 项目会启动 `lake serve`，冷启动几秒到十几秒；之后同一文件的调用是毫秒级。

## 7. 常用检查

```sh
# 版本
cat /data/lean-fate-related/FATE/FATE-M/lean-toolchain
git -C /data/lean-fate-related/mathlib4 rev-parse HEAD

# 构建是否完整
find /data/lean-fate-related/FATE/FATE-M/.lake/build/lib/lean -name '*.olean' | wc -l   # 151
find /data/lean-fate-related/mathlib4/.lake/build/lib/lean -name '*.olean' | wc -l        # 7655

# 单文件类型检查（不改 .lake 结构）
cd /data/lean-fate-related/FATE/FATE-M
export PATH="$HOME/.elan/bin:$PATH"
lake env lean FATEM/1.lean
```

## 8. 坑

- **`v4.28.0-rc1` 不兼容**：`~/lean-4.28-reap/runtime` 那套是 rc1，别拿来给 FATE 用；FATE 必须正式版 `v4.28.0`。
- **别删 `mathlib4/.lake`**：oleans 有 6G，重解压要 `cache get`；`.ltar` 还在本地，所以重装是分钟级而不是重新下载。
- **Cloudflare 镜像不可用**：`mathlib4.lean-cache.cloud` 对 `8f9d9cff` 返回 404，`lake exe cache get` 自动回退 Azure；不要手改 `MATHLIB_CACHE_GET_URL` 指向 Cloudflare。
- **每个 FATE 项目都有 387M 的 `.lake/packages` 副本**，这是 Lake 对 path 依赖的正常行为；磁盘够就不用去重。
- **改 `lakefile.lean` 的路径会破坏可移植性**：如果之后 `git checkout` 覆盖了 lakefile，需要重新把 `require mathlib from git ...` 改回 path，或让 Lake 重新克隆 Mathlib。
- **磁盘**：`/home` 只剩约 70G，任何 Mathlib 相关的克隆、缓存、构建都放 `/data`。
- **`/data` 是外置盘**，设备号可能变化；换盘后上面所有绝对路径失效，需要整体迁移。
