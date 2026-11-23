---
name: 3080-20g-local-information
description: '本地环境那张魔改 RTX 3080 20G 的算力总账：硬件身份（GA102-200、68 SM、5MB L2、320-bit 19Gbps、320W、VBIOS 94.02.27.00.14）、gpu_unlock 2.0.0 到底解锁了什么（FP16/BF16/TF32 + FP32 累加 tensor 速率翻倍）、2026-11-17 实测的各精度峰值与官方 3080 参数逐项对比、以及哪些东西没被解锁（FP32 持续受 320W 墙、INT8 本来就满速 238 TOPS、20GB 是改板）。当用户问这台 3080 20G 的算力/带宽/温度/功耗、gpu_unlock 是否生效或该不该重跑、FP32 为什么只有 21 TF/s、INT8 怎么测/为什么低、显存是不是 20G、或要复现 benchmark 时使用。触发词：3080 20G, 3080-20g, gpu_unlock, 解锁, tensor core 半速, FP16 107, TF32 53, INT8 208, INT8 50, 列主序 B, FP32 21.5, 760 GB/s, 320W, GA102-200, memtest_vulkan, 算力核对。'
---

# 本地环境 RTX 3080 20G 算力总账

一张魔改卡：**RTX 3080 20GB**（GA102-200，68 SM，8704 CUDA，5 MB L2，320-bit @19 Gbps，
320W），跑在 Ubuntu + 驱动 580.178.04 / CUDA 13.0 + PyTorch 2.14.0+cu130 / Triton 3.8.0。
`gpu_unlock` 2.0.0 已装并在开机时生效。

**一句话：gpu_unlock 只把 FP16/BF16/TF32 的 FP32-累加 tensor 速率翻倍（到官方标称的每时钟值），
其余算力项没动、与官方 3080 一致；FP32 持续低是 320W 墙，INT8 本来就满速（238 TOPS），
20GB 是改板。**

## 1. 硬件身份（nvidia-smi / torch 可查）

| 项 | 值 |
|---|---|
| 名称 | NVIDIA GeForce RTX 3080（20GB 改板） |
| PCI ID / 子系统 | `10de:2206` / `10de:146d`，bus `0000:08:00.0` |
| GPU part number | `2206-200-A1` = GA102-200（3080 10G 的 die，不是 3090） |
| VBIOS | `94.02.27.00.14`，GSP 580.178.04 |
| SM / CUDA / Tensor / RT | 68 / 8704 / 272（4 per SM）/ 68（1 per SM） |
| L2 | 5.0 MB（GA102 满配 6 MB，3080 切到 5 MB） |
| 显存 | 20480 MiB（PyTorch 19.58 GiB），9501 MHz = 19 Gbps，320-bit，标称 760 GB/s |
| 功耗 | default 320 W，min 100 W，max 320 W（**没有解锁功耗墙**） |
| 时钟 | 空闲 210/405 MHz；轻载最高 1935–1950 MHz（支持表到 2100）；持续 tensor 1620–1650；持续 SGEMM ~1560–1605 |
| PCIe | 空闲 Gen1 x16（ASPM 省电），负载下 Gen4 x16 |
| 温度 | 30 秒 BF16 满载 320 W / 60 °C；SGEMM 53 °C；memtest 时显存 88 °C |

## 2. gpu_unlock 状态与证据

- 源码/工程：`~/gpu-unlock`（Zagitta/gpu-unlock v2.0.0，DKMS + dracut `rd.driver.pre=gpu_unlock`）
- 测试与基线：`~/gpu-unlock-test/`（`baseline.json` 解锁前、`after.json` 解锁后、`REPORT.md`、`rollback.sh`、`initrd.pre-gpu-unlock.img`）
- 模块：`lsmod | grep gpu_unlock` 有 `gpu_unlock <size> 0`
- 本次开机 dmesg（`sudo dmesg | grep gpu_unlock`）结尾：
  `stage=host ss0=0x88888888 ... stage=handoff ret=0 state=4 ... gpu_unlock: unlocked`
- 解锁是**易失**的：每次冷启动由 initramfs 里的模块重放；S3 唤醒会重放（`gpu_unlock.resume`）。
- 关闭：跑 `~/gpu-unlock-test/rollback.sh`。

**它到底改了什么**：GeForce 卡上 FP16/BF16/TF32 用 FP32 累加时被限到一半速率，
模块在驱动加载前改写 fuse/PLM 状态，使这条路径翻倍；**不碰 FP32/FP64 向量，不改功耗墙；
INT8 本来就满速（SS0/SS1 的 IMLA 字段默认 full rate），实测解锁前后不变。**

## 3. 官方参数 vs 实测（2026-11-17）

官方 RTX 3080：68 SM、8704 CUDA、boost 1710、FP32 29.77 TF/s、FP64 0.465（1:64）、
TF32 tensor 59.5 dense、FP16/BF16 119 dense（238 含 sparsity）、10 GB 19 Gbps 760 GB/s、320 W。

| 项目 | 官方 | 实测（本地环境） | 每时钟折算 | 判断 |
|---|---:|---:|---|---|
| FP16 tensor（FP32 acc） | 119 | **107.6 中位 / 116.5 最好 @1620** | 977–1060 flop/clk/SM（官方 1024） | 解锁后一致 |
| BF16 tensor（FP32 acc） | 119 | **110.4 @1620** | ~1000 | 解锁后一致 |
| TF32 tensor（FP32 acc） | 59.5 | **53.0 @1650** | 472（官方 512，92%） | 解锁后一致 |
| INT8 | 238（GA102 白皮书，dense） | **207–209 TOPS**（cuBLASLt，B 列主序）@1552 | 1961 ops/clk/SM（满速 2048 的 96%） | 本来就满速，无需解锁 |
| FP32（cuBLAS SGEMM） | 29.77 @1710 | **21.0–21.3**，2048–16384 全尺寸平 | 76–78% | 320W 墙 + SGEMM 开销，非阉割 |
| FP32（纯 FMA 内核） | — | **27.83 @1873** | 219 flop/clk/SM（理论 256 的 86%） | 流水线完整 |
| FP64 | 0.465 | **0.45 @1935** | 3.42 flop/clk/SM（1:64 的 86%） | 一致 |
| 显存 copy / read / fill | 760 | 687 / 719 / 723 GB/s | 90–95% | 一致 |
| 显存容量 | 10 GB | **20 GB** | — | 硬件改板，与 gpu_unlock 无关 |
| 功耗墙 / PCIe | 320 W / 4.0 x16 | 320 W / Gen4 x16（负载） | — | 一致 |

### 解锁前后（同一张卡，2026-11-12 基线 → 11-17）

| 测试（8192³） | 解锁前 | 解锁后 | 每时钟 |
|---|---:|---:|---|
| FP16 | 64.4 TF/s | 107.6–116.5 | 512 → ~1000 flop/clk/SM |
| BF16 | 64.4 TF/s | 110.4 | 同上 |
| TF32 | 31.9 TF/s | 53.0 | 256 → 472 |
| FP32（对照） | 21.5 | 21.3 | 不变 |

结论：**解锁后 tensor 的每时钟吞吐才达到 NVIDIA 标称值；零售态只有标称的一半。**

## 4. 容易踩的坑

1. **FP32 21.5 不是被锁**。纯 FMA 内核 1.87 GHz 下 27.8 TF/s（219/256 flop/clk/SM）；
   cuBLAS SGEMM 在 320 W 墙下把 SM 压到 ~1.6 GHz，所以持续只有 21.3。
2. **INT8 正确测法**：`torch._int_mm(a, b)` 里 B 必须是列主序（`b_row.t()`，stride `(1, n)`），
   才会走 `cutlass_80_tensorop_i16832gemm_s8`，得 207–209 TOPS；B 行主序会退回 legacy
   非 tensor-core 内核，只有 ~50 TOPS。Triton 的 BK=128 配置也只有 ~115 TOPS（不如 cuBLASLt）。
3. **INT8 本来就满速，没有可解锁的倍率**：官方 238 TOPS dense，实测 207–209（96%）；
   社区 A/B（issue #15）158–160 TOPS 解锁前后不变。`gpu_unlock` 的 SS0/SS1 选择器里
   虽有 IMLA0–4 字段，但消费卡这些字段默认已经是 full rate。想要 >238 只能走
   sparsity（2:4，翻倍到 476）或 INT4（476 dense），那是换数学模式，不是解锁。
4. **显存 20GB 是改板**：10 颗 2GB 颗粒，位宽仍 320-bit，带宽仍 760 GB/s 标称；
   `memtest_vulkan` 30 分钟全卡扫描 `no any errors`（632–646 GB/s）。
5. **PCIe 空闲显示 Gen1 是正常的**，跑负载会升到 Gen4 x16，别误判。
6. **没有 nvcc**：`torch.utils.cpp_extension` 会报 `CUDA_HOME not set`；微基准用 Triton 3.8。
7. 空闲显存占用 57 MiB（gnome-shell ~40 MiB），不影响 benchmark。

## 5. 复现与文件位置

```bash
cd ~/gpu_test
python3 verify_now.py          # 全套：FP32/TF32/FP16/BF16/INT8/FP64 + 带宽 + 30s 持续 → verify_now.json
python3 fp32_peak_triton.py    # 纯 FP32 FMA 短脉冲（~9ms）
python3 fma_sustained.py       # 纯 FP32 FMA 10s 持续 + 时钟/功耗
python3 cublas_sizes.py        # cuBLAS SGEMM 2048..16384
python3 triton_mm.py           # Triton FP32/TF32/FP16/BF16/INT8（注意：import 会重跑全部）
python3 int8_colmajor.py       # INT8 正确测法：B 用列主序，4096/8192/16384
python3 int8_sustained.py      # INT8 10s 持续 + 时钟/功耗
```

- 本次完整记录：`~/gpu_test/VERIFY_2026-11-17.md`
- 原始 JSON：`~/gpu_test/verify_now.json`
- 历史基线：`~/gpu-unlock-test/baseline.json`、`after.json`、`REPORT.md`
- 解锁源码：`~/gpu-unlock`；健康检查：`~/gpu_health/`
- 显存/温度长测：`~/gpu_test/memtest_vulkan.log`、`memtest_30m.log`、`thermal_*.csv`

## 6. 变更记录

- 2026-11-12：装 gpu_unlock 2.0.0，记录解锁前/后基线；30 分钟 memtest 通过。
- 2026-11-17：全面复测（本 skill 数据来源）；确认 FP32 受 320W 墙、20GB 全可寻址。
- 2026-11-17 修注：INT8 之前记成 115 TOPS/半速是测量错误。B 用列主序后 207–209 TOPS
  = 官方 238 的 96%，INT8 本来就满速，不需要也不能再解锁（只能换 sparsity/INT4）。
