# 07 · 代码逐段讲解

## 这一篇讲什么

前两篇讲数学与装配，这一篇讲**当前机器上真正跑的那份代码**。四个文件、逐段引用、行号对齐：

| 文件 | 行数 | 作用 |
|---|---|---|
| `train/block_train.py` | 762 | 单 block（layer 3）的真实权重训练 harness；`ExpertStore` 是 GaLore 的宿主 |
| `kernels/galore_fold.py` | 149 | 融合 fold 内核：`Ŵ ← Q(deq(Ŵ) + P R)`，原地 |
| `kernels/moe_int8_gemm.py` | 267 | grouped int8 MoE GEMM + 量化粒度研究 |
| `kernels/quant_scheme_decision.py` | 104 | RTN / SR / EF 的判决实验 |

> **行号口径（2026-11-19）。** `block_train.py` 在修 RMSNorm 时一起改过，从 346 行长到 **762 行**，
> 并且已实现折叠与刷新（`--basis svd` 为默认）。本文的行号已更新到该版本；`kernels/` 三个文件的
> 行数未变（149 / 267 / 104）。当前锚点：`rmsnorm:77`、`Int8Expert:113`、`ExpertStore:216`、
> `_q:256`、`_eff:274`、`fwd:283`、`fold:301`、`measure:336`、`Block:354`、`refresh_basis:422`、
> `Block.moe:497`、`Block.loss:539`。

每一段都回答三个问题：**它在算什么（数学）、它花多少（成本）、如果按"显然的写法"会坏在哪。**

## 读完你会知道

- `_q` 的尺度为什么是"每输出通道"而不是"每组 32 个"；
- `_eff` 为什么要按 64 个专家分块，以及它每步被调用 16 次意味着什么；
- 方法 A 与方法 B 的差别在哪一行，以及方法 B 偷偷物化了什么；
- fold 内核的 tile 为什么是 `BM×BK`，为什么"一程序一行"慢 54 倍；
- `tf32` 与 `ieee` 的 48–50 倍差距，以及那句"exact fp32 FMA path"注释错在哪；
- int8 GEMM 为什么必须 B 列主序，epilogue 为什么逼你放弃 group-32 尺度；
- `quant_scheme_decision.py` 的指标为什么是"到最优点的距离"，以及它的两个建模局限。

---

## 1. 地图：一次 MoE 前向要经过哪些代码

```text
Block.loss                  block_train.py:539
 └ Block.moe                :497   路由、capacity、SmoothQuant 反缩放
    ├ ExpertStore.fwd("gu") :283   [A] _eff:274 或 [B] Int8Expert:113 + (X Rᵀ)Pᵀ
    ├ silu(gate) * up       :265
    └ ExpertStore.fwd("d")  :283
```

`Block.moe` 每个 2048-token 序列调用一次，所以 16,384 tokens/step 时 `fwd` 被调用 **16 次**
（8 序列 × gate_up/down 各一次）。这个数字是后面许多成本的根源。

---

## 2. `ExpertStore`：GaLore 的宿主

### 2.1 量化：`_q`（`block_train.py:256`）

```python
@staticmethod
def _q(w):
    amax = w.abs().amax(-1, keepdim=True).clamp_min(1e-12)
    return (torch.round(w / amax * 127).clamp(-127, 127).to(torch.int8),
            (amax / 127).squeeze(-1).to(torch.float32))
```

**数学。** 输入 `w` 形状 `[NE, N, K]`，`amax` 沿最后一维（输入通道 `K`）取，所以每个
`(专家, 输出通道)` 有一个尺度。`s = amax/127`，`Ŵ = round(w/s)`，`deq(Ŵ) = Ŵ·s`。
这就是 `00-notation.md` 的 `Ŵ` 与 `s`。用 ±127 而不是 ±128：对称量化，保证 `−127·s` 与 `+127·s`
对称，代价是舍掉 `−128` 这一个码（0.4% 的动态范围）。

**成本。** 每层一次，536.9 M 元素，读 2.15 GB、写 0.54 GB，HBM 上约 4.2 ms。

**显然的写法会坏在哪。** 按 group-32 取 absmax 更准（0.5346% vs 每通道 0.8276%，
`kernels/sweep.json`），但 int8 GEMM 的 epilogue 就无法用一次外积 rescale——每 32 列一个尺度，
得在 `[BM,BN]` 累加器上逐组乘。本项目的选择是精度让位于速度（0.83%，换 139 TOPS）。

### 2.2 存储布局（`ExpertStore.__init__`，`:240-248`）

```python
self.P_gu = (torch.randn(NE, 1024, rank, generator=g) / math.sqrt(1024)).to(dev)
self.P_d  = (torch.randn(NE, 2048, rank, generator=g) / math.sqrt(2048)).to(dev)
self.R_gu = torch.zeros(NE, rank, 2048, device=dev, requires_grad=True)
self.R_d  = torch.zeros(NE, rank, 512,  device=dev, requires_grad=True)
```

**数学。** `P` 是 `[256, m, r]`，`R` 是 `[256, r, n]`，与 `05` 的 `P ∈ R^{m×r}`、`R ∈ R^{r×n}`
逐专家对齐。`P` 用 `randn/sqrt(m)` 初始化，列近似正交但**没有做 QR**，严格说 `PᵀP ≠ I`
（误差 `1/√m ≈ 3%`）；`05` 的所有定理都假设 `PᵀP = I_r`，这是一个理论瑕疵。
**旧版 `P` 永不更新**，所以那时是随机投影而不是 GaLore（`06` §7 第 4 条）。现在已修：`P` 的列由按专家
捕获的 `dW = dYᵀX` 的 SVD 得到并做 QR（`--basis svd` 默认），`--refresh 0 --fold 0` 可退回旧行为。
`requires_grad=True` 的只有 `R`，`P` 是常量；每层 `P` 50.33 MB（int8）、`R` 83.89 MB（bf16）。

### 2.3 有效权重：`_eff`（`block_train.py:274`）

```python
def _eff(self, which):
    """effective weight materialized in bf16 (method A); differentiable w.r.t. R."""
    P, R = self._PR(which)
    parts = []
    for i in range(0, NE, 64):                      # chunked: caps the fp32 transient
        w = self._deq(which, i, i + 64)
        parts.append(w + torch.bmm(P[i:i + 64], R[i:i + 64]).to(torch.bfloat16))
    return torch.cat(parts)
```

**数学。** 逐专家算 `deq(Ŵ_e) + P_e R_e`，即式 `W_eff = deq(Ŵ) + P R`。三处精度选择：

1. `q.float() * s` 在 fp32 里做，再转 bf16——正确，因为 int8 乘尺度必须精确；
2. `bmm(P,R)` 在 bf16 里做（`P` 是 bf16），结果再转 bf16；
3. **加法在 bf16 里做**。这会让 `W_eff` 的误差约 `2^-9` 倍的低秩修正（≈0.2% × 0.5% = 1e-5 的 W），
   比一个量化台阶（1.2e-4）小一个量级，可以接受；但如果 `R` 很大（折叠间隔太长），这一项会变大。

**成本。** 每层 `2·256·(1024·2048 + 2048·512)·64 = 103 GFLOP`，峰值 0.87 ms；实测整层
`_eff` 的 16 次调用共 0.377 s/step（`runs/A/REPORT.md` §3），即每次 23.5 ms——**远低于峰值**，
因为它是 memory-bound 的 elementwise 加一个瘦 `bmm`。

**显然的写法会坏在哪。** 不分块时 `q.float()` 产生 2.15 GB 的 fp32 临时量，吃掉显存 10%；
分块后 0.54 GB。另外 autograd 会为 `bmm(P,R)` 保存 `P` 的转置用于反传，这部分也要算进峰值。

### 2.4 前向：方法 A 与方法 B（`block_train.py:283`）

```python
def fwd(self, which, X):
    if self.method == "a":
        return torch.bmm(X, self._eff(which).transpose(1, 2))
    # B: int8 tensor cores + separate rank-r correction
    ...
    y = Int8Expert.apply(X, q, s, cfg, n_out, n_in, inv)
    # rank-r correction: X @ (P@R)^T  =  (X @ R^T) @ P^T
    y = y + torch.bmm(torch.bmm(X, R.transpose(1, 2).to(X.dtype)), P.transpose(1, 2).to(X.dtype))
    return y
```

**数学。** 方法 A 直接用 `W_eff` 做 bf16 GEMM：`y = X W_effᵀ`。方法 B 把同一个式子拆成
`X deq(Ŵ)ᵀ + X (P R)ᵀ`，第二项用结合律算成 `(X Rᵀ) Pᵀ`，**从不在显存里造 `P R`**。
`M=128, r=64` 时 `gate_up` 的修正是 `2·128·64·(2048+1024) = 50.3 MFLOP`，物化 `P R` 再乘要
268 MFLOP，省 5.3 倍。方法 B 的修正 GEMM 约 4 ms/step（按 50 TFLOP/s 估，**UNVERIFIED**）；
A → B 的端到端加速是 **1.28×**（`runs/B/REPORT.md` §0）。绝对秒数（1.54 s / 1.183 s）不要引用：
它们来自 capacity 有缺陷的版本（`STATE.md` §5）。

### 2.5 `Int8Expert`：int8 前向，bf16 反传（`block_train.py:113`）

```python
ne, M, K = x.shape
# xs is the step: max|x / xs| == 127 exactly, so the scaled value is x / xs.
# It used to be `round(x / xs * 127)` — i.e. x·127²/amax — which saturated 97.7 % of elements.
xs = (x.abs().amax(-1, keepdim=True) / 127).clamp_min(1e-12)
x8 = torch.round(x / xs).clamp(-127, 127).to(torch.int8)
y = moe_i8_gemm(x8, xs.squeeze(-1), q8, s8, M, K, n_out, cfg, ne)
ctx.save_for_backward(q8.float() * s8[..., None])   # W_eff for dX
```

**数学。** 激活按 **per-token** 对称量化（`amax` 沿 `K`），与权重的 per-channel 尺度配对：
`y[m,n] = xs[m]·ws[n]·Σ_k x8[m,k]·ŵ[n,k]`。整数累加在 int32 里精确（`K=2048, 127²·2048 = 3.3e7 < 2³¹`），
epilogue 再乘 `xs·ws`。

**成本与一个隐藏的坑。** `save_for_backward` 在**前向**就物化了整层的 **fp32** 反量化权重：
`gate_up` 2.15 GB、`down` 1.07 GB，合计 **3.2 GB**。方法 B 的目标是"不物化 bf16 权重"，
却为 dX 物化了 fp32 权重（比 bf16 大一倍），而且这份 `W_eff` **只含骨架**：

```python
dx = torch.bmm(dy, w.to(dy.dtype))        # w = q8*s8，没有 P R
```

所以方法 B 的 `dX` 漏掉了低秩修正（约 0.5% 的权重），而方法 A 经由 `W_eff` 的 autograd 是
包含的。**这是 A/B 之间一个未记录的行为差异**；旧报告里"60 步 loss 差 0.085 nats"的归因**待重测**
（1-block 的 loss 在错缩放的 RMSNorm 上测的，见 `06` §0）。
正确做法：把 `(P R)ᵀ` 也加进 `dx`，并把保存的 dtype 降到 bf16。

### 2.6 两个真出现过的 W8A8 bug（CPU 自检抓到的）

这两个不是设计讨论，是 2026-11-19 的活 bug，也是"为什么 method-B 的训练数字全废"的原因
（`STATE.md` §4）。它们都**不报错、不 NaN，loss 还能下降**。

**① 激活量化多乘了一次 127。** `xs = amax/127` 本身就是"一格"，再写 `round(x / xs * 127)` 就变成
`x·127²/amax`：

```text
错误   round(x / (amax/127) * 127) = round(x·127²/amax)  → 几乎全部越界 → clamp 到 ±127
实测   97.7% 的元素饱和；输出相对误差 248–288%
正确   round(x / xs)                                     → 0.05% 饱和、0.83% 误差
```

（248% 是 `down`、279% 是 `gu`，都在自检的随机数据上；账本记的真实激活是 288%。误差随矩阵与
数据变，**97.7% 的饱和比例才是判据**。）

危害在于它**看起来还在工作**：全是 ±127 的激活退化成一个符号图样，前向照样有值，只是信息没了。
**检验量化器要看饱和比例**，不要盯着公式：`(x8.abs() == 127).float().mean()` 一行就抓住了。

**② 反量化被除了两次。** 调用方已经在**图内**把 `X` 除以 `sk_gu`（SmoothQuant 的折叠），
autograd 因此会给 `dX` 自带 `1/sk_gu`；而 `Function.backward` 里又乘了一次旧的 `inv_sk = 1/sk_gu`，
gu 的梯度被除了两次。`sk = amax(x)^0.7` 不是 ≈1，所以这不是舍入级的问题。
**规则：自定义 `Function` 里尺度只能住在一个地方**；要查的是"我现在在图内还是图外"。

**给读者的坑：旧公式还活在注释里。** `train/block_train.py` 的注释、`train/method_b.py` 的
docstring + `repo_form` 开关、以及 `runs/B/{whatif,profile_split}.py` 里的旧 `Function` 副本，
都还写着 `round(x / xs * 127)`。所以**字符串 grep 会命中注释和复现副本**，判断"现在用的是哪一种"
必须走结构检查：`train/method_b.py --selftest` 用 `ast.parse` + `ast.unparse`（丢掉注释）断言
`round(x / xs)` 在、`127` 那个形式不在，并检查 `apply` 的参数个数与 `backward` 的返回值个数。

---

## 3. `galore_fold.py`：折叠内核

### 3.1 一个 tile 在算什么（`galore_fold.py:24-49`）

```python
p  = tl.load(P + pid_e*N*RANK + rm[:, None]*RANK + rr[None, :]).to(tl.float32)  # [BM,RANK]
rb = tl.load(R + pid_e*RANK*K + rr[:, None]*K + rk[None, :]).to(tl.float32)    # [RANK,BK]
s  = tl.load(S + pid_e*N + rm)                                                  # [BM]
q  = tl.load(W8 + off).to(tl.float32)

lr = tl.dot(p, rb, input_precision="tf32")          # [BM,BK]
w  = q * s[:, None] + lr
nq = tl.minimum(tl.maximum(tld.rint(w / s[:, None]), -127.0), 127.0)
tl.store(OUT + off, nq.to(tl.int8))
```

**数学。** 对每个专家 `e`、每个 `BM` 行块、每个 `BK` 列块：

```text
w      = ŵ·s + (P_e R_e)[BM,BK]        # deq(Ŵ) + P R
nq     = clamp(rint(w/s), −127, 127)   # Q(w)，s 冻结
```

`tld.rint` 是 round-half-to-even（与 `torch.round` 一致，100% 码一致的前提）；±127 与 `_q` 对称；
`q*s + lr` 在 fp32 里加，比 `_eff` 的 bf16 加法更精确。

**成本。** 每 tile `BM×BK×RANK = 262 K` 次乘加（0.52 MFLOP），HBM 流量 16 KB（int8 读写各
8 KB），加上每 tile 的 `P,R` 共 24 KB。算术强度在 13–32 flops/byte 之间（取决于 `P,R` 是否
被 L2 命中），**远低于屋脊点 274**，所以是带宽 bound，与 `moe_int8_gemm` 的 160 flops/byte
不是一回事。实测 4.1 ms（`gate_up` 半区 0.503 GB，r=32）= 同区域纯 int8 拷贝的 2.61 倍。

### 3.2 为什么"一程序一行"慢 54 倍（`galore_fold.py:29-31`）

```python
"""One program = BM output channels x BK K-elements of ONE expert.
The R block [RANK, BK] is loaded once per program and reused for all BM rows; the earlier
version was one program per row and re-read R 1024x, which cost 54x."""
```

`R` 块是 `[RANK, BK]`，对 `BM` 行是**共享**的。一程序一行时，每个程序都重新从 HBM 读一遍
`R`（`RANK×BK`），而它只做 `1×BK×RANK` 的乘加——算术强度掉到 `RANK/(RANK+1) ≈ 1` flop/byte，
`R` 的读放大 `BM` 倍。54× 是实测（注释）。

**修法**不是"换更大的 tile"，而是**改变复用结构**：让 `BM` 行共享同一个 `R` 块。`BM=64` 是因为
再大则 `P` 块 `[BM,RANK]` 的寄存器压力会压 occupancy；`BK=128` 是为了摊掉 `R` 的读。

### 3.3 为什么冻结尺度（`galore_fold.py:5-8`）

```text
the fold happens every k optimizer steps and the update over k steps is small relative to the
weight, so the per-output-channel absmax barely moves. Freezing s turns the fold into a
single read-modify-write pass instead of two (absmax pass + store pass) over 34 GB.
```

**数学。** 重算 `s = absmax/127` 要先扫一遍 `deq(Ŵ)+P R` 求 absmax 再量化——两趟 34 GB 的
PCIe；冻结 `s` 只需一趟。代价是长期单调增长的通道会让 `s` 偏小、最终被 clamp 到 ±127。
**这个风险没有测量**（UNVERIFIED）：`K=20` 时漂移约 `3.7q`，`s` 的相对变化 3%，概率低但不是零。

### 3.4 `tf32` vs `ieee`：48–50 倍（`galore_fold.py:45`）

```python
lr = tl.dot(p, rb, input_precision="tf32")          # [BM,BK], exact fp32 FMA path
```

**注释是错的。** tf32 只有 10 位显式尾数，乘积**不是** exact fp32。真实情况是"tf32 的误差小到
不改变任何一个 int8 码"。2026-11-17 用与仓库内核逐行等价的脚本（只把 `input_precision`
参数化）在空闲卡上复测：

| 精度 | r=32 | r=64 |
|---|---|---|
| `ieee` | 331.74 ms | 1019.06 ms |
| `tf32` | **6.63 ms** | **14.95 ms** |
| 比值 | **50.0×** | **68.2×** |
| int8 码一致率 | 100.000% | 100.000% |

项目记录的倍数是 **48×**，复测是 50×（r=32）/ 68×（r=64），同一现象：Triton 在 sm86 上把
`ieee` 的 fp32 dot 降级成 FMA 循环，吞吐差两个数量级。

**为什么够用、什么时候不够。** 最坏界 `γ_r·Σ|p_i r_i|`，`γ_r ≈ r·2^-11 = 3.1%`（r=64）；
修正项占 W 的 ~0.5%，最坏误差约 `1.5e-4`，**略大于一个台阶 1.2e-4**——理论上可能翻码。
实测 536 M 元素 0 次翻码（"100.000%"意味着不一致 < 3×10⁻⁹），随机符号让实际误差小一个量级。
**但余量不大**：`R` 越大，tf32 误差同比例上升。这是"用 EF 管住 `R`"的又一个理由。

### 3.5 正确性与成本（`galore_fold.py:90-130`）

```python
ref = W8.clone(); fold_torch(ref, s, P, R)
got = fold_triton(W8, s, P, R)
agree = (got == ref).float().mean().item()
```

`fold_torch` 是参考实现：物化 `bmm(P,R)` 的 fp32（0.54 GB）再分块量化。它慢且费显存，但语义
与内核逐位一致——这是正确性的唯一证据。实测（r=32，`gate_up` 半区）：码一致率 **100.000%**；fold 残差
`‖deq(fold)−target‖/‖target‖ = 0.088%`（r=64 时 0.125%），是 0.045 个台阶，符合 RTN 的
`q/√12` 预期。

**地板对比**：同一 0.503 GB 区域，纯 int8 拷贝 1.57 ms，fold 4.1 ms = **2.61×**；多出的 2.5 ms 是
`P R` 与重量化。整层（1.543 GB）约 6.6 ms。想把折叠做快，答案不是优化内核而是减少次数，
因为 PCIe 的上限是 1.357 s/次。**4.1 / 2.61× / 100% 这三项只有运行时打印，没有落盘 JSON**
（`STATE.md` §8）。

---

## 4. `moe_int8_gemm.py`：grouped int8 GEMM

### 4.1 列主序 B 是硬性要求（`moe_int8_gemm.py:83-91`）

```python
x_ptr = X + e * sx_e + rm[:, None] * K + rk[None, :]
# W[e] is [N, K] row-major; B tile [BK, BN] wants B[k, n] = W[e][n, k] -> stride 1 along k
w_ptr = W + e * sw_e + rn[None, :] * K + rk[:, None]
...
acc += tl.dot(a, b, out_dtype=tl.int32)
```

**数学。** `W[e]` 是 `[N,K]` 行主序，元素 `(n,k)` 的偏移是 `n·K + k`。tile 要的是
`B[k,n] = W[n,k]`，所以 `k` 用 `rk[:, None]`（步长 1）、`n` 用 `rn[None,:]`（步长 `K`）——
**`k` 连续 = B 列主序**。

**成本。** `bench/bench9.json`：`torch._int_mm` 在 B 行主序时 **50.3 TOPS**，列主序 **205.8 TOPS**，
差 4.1×。不是精度问题，是 cuBLASLt 静默退回了 legacy 非张量核内核（同一文件的
`sq_rowmajor` vs `sq_colmajor`）。`torch.bmm` 对 int8 直接报
`"baddbmm_cuda" not implemented for 'Char'`，所以这个内核不是"优化"，是"唯一能用的路"。

### 4.2 tile 顺序决定 L2 命中（`moe_int8_gemm.py:56-77`）

`ORDER=0` 是 expert-fastest：相邻 CTA 处理**不同专家**，权重面板和激活面板都不共享。
`ORDER=4` 是 expert-major + 2D swizzle。注释（第 27–32 行）算得很清楚：tile 的算术强度
只有 ~160 flops/byte，而 int8 屋脊点是 274，所以内核是 **L2 复用 bound**，不是张量核 bound。

`gm = math.gcd(cfg.get("gm", 2), TM)`（111 行）是必要防御：`gm` 不整除 `TM` 时 tile 解码不再是
双射，会**静默算错**（`runs/B/REPORT.md` §1 记录了 M=128 时的一次错误 loss）。

### 4.3 epilogue：一次外积 rescale（`moe_int8_gemm.py:95-101`）

```python
xs = tl.load(XS + e * sxs_e + rm, mask=m_mask, other=0.0)   # per-token
ws = tl.load(WS + e * sws_e + rn)                           # per-output-channel
y  = acc.to(tl.float32) * (xs[:, None] * ws[None, :])
tl.store(Y + ..., y.to(tl.bfloat16), ...)
```

**数学。** `Y[m,n] = xs[m]·ws[n]·acc[m,n]`，一个 rank-1 外积。**这就是为什么尺度必须是
per-token × per-output-channel**：任何更细的粒度（group-32）都会让 `ws` 变成 `[BN/32]` 的向量，
外积不再成立，得在累加器上做逐组乘法，吞吐立刻掉下来。

**代价**（`kernels/sweep.json`）：per-channel 相对误差 0.8276%，group-32 是 0.5346%——
group-32 更准，但慢。功能误差 1.17%（per-channel，含 int8 激活），在 `06` §6 的 2.5% 折叠误差
之下，可以接受。

### 4.4 实测配置表（`runs/B/REPORT.md` §2.1，M=128，即 harness 真实形状）

| 配置 | ms | TOPS | vs order-0 |
|---|---|---|---|
| `o4g4-BM128-BN256-BK128-w8-s3` | 0.99 | **139.4** | 1.48× |
| `o4g2-...`（默认） | 0.99 | 139.0 | 1.48× |
| `o2-...` | 0.99 | 138.5 | 1.47× |
| `o4g4-BM256-BN128-BK128-w8-s3` | 1.46 | 94.2 | 1.00× |
| `module-baseline (order 0)` | 1.46 | 94.0 | — |

`down`（K=512, N=2048）最好的是 `o4g4-BM128-BN256-BK128-w8-s3`，0.63 ms / **108.8 TOPS**。
更大 M 的形状（study，不是 harness 真实形状）：M=512 **189.6**、M=1024 **189.3**、
M=2048 **186.3** TOPS。**M=128 的 139 TOPS 不是内核差，是形状的带宽上限**：
643 MB 最少流量 / 637 GB/s = 1.01 ms，而实测 0.99 ms。

**显然的写法会坏在哪。** 逐专家循环 256 次小 GEMM：18.2 TFLOP/s vs grouped 75.0
（**未落盘**：只看得到旧报告正文，仓库里没有对应 JSON），加上 30,720 次微内核启动 0.28 s/step。
grouped 不是"更好"，是"唯一可行"。

---

## 5. `quant_scheme_decision.py`：判决实验

### 5.1 指标：到最优点的距离（`quant_scheme_decision.py:1-10`）

```text
The metric that decides it is the thing we optimize: distance to the optimum after N steps.
```

这是整份代码里方法论证最正确的一段。`foldnoise.py` 测的是"跟理想轨迹的偏差"，那个指标天然
偏袒低方差的 RTN；真正要优化的是"2000 步后离最优点多远"。两个指标可以给出相反的排序，
不是谁错了，而是**问的问题不同**。

### 5.2 两个量化器（`quant_scheme_decision.py:25-32`）

```python
def q_rtn(w, s):
    return torch.round(w / s).clamp(-127, 127)

def q_sr(w, s):
    x = (w / s).clamp(-127, 128)
    fl = torch.floor(x)
    return (fl + (torch.rand_like(x) < (x - fl)).float()).clamp(-127, 127)
```

**数学。** RTN 是 `round`；SR 是 `floor(x)+Bernoulli(frac(x))`，`E[SR(x)] = x`。上界 128 是为
`floor` 留一格、最后再 clamp 到 127，保证 `x = 127.0` 不越界。代价是每元素一次 RNG；survey §7.2
估计全模型每折约 0.1 s，**相对 54 ms 的 PCIe 不小**——这也是"EF 之后不必 SR"的实际理由。

### 5.3 `run()` 的折叠循环（`quant_scheme_decision.py:44-66`）

```python
for t in range(N_STEPS):
    g = (w - w_target) + torch.randn(M, N) * 0.05
    step = -lr * g / (g.abs().mean() / 3 + 1e-12)
    acc += step
    if (t + 1) % fold_every == 0:
        w_ref = (q.float() * s) + acc + resid
        ...
        if "sr" in scheme: qn = q_sr(target, s)
        else:              qn = q_rtn(target, s)
        if scheme.endswith("_ef"):
            resid = target - qn * s
        q = qn.to(torch.int8)
        w = q.float() * s
        acc.zero_()
    else:
        w = (q.float() * s) + acc
```

**数学。** `w` 始终是"骨架 + 未折叠累加"；`acc` 是 `K` 步的位移和；折叠时
`target = 骨架 + acc + resid`，量化后 `w = qn·s`，`acc` 清零；EF 时 `resid = target − qn·s`
留到下一次。**逐行对应 `05` 式 (8) 与 `06` §5.4。**

**两个建模局限**：`step = −lr·g/(mean|g|/3)` 是**全局**归一化，不是 Adam 的逐坐标 `M̂/√V̂`；
`acc` 是**全秩** `m×n`，不是 `r×n`。所以它测"量化器 + 折叠"，不测 Adam，也不测 rank 截断
——正好适合回答 EF vs SR vs RTN，但**不能**回答 r=64 够不够。

**死代码**（50–53 行）：`if ..._ef: target = w_ref else: target = w_ref`，两分支相同。无害，
但说明这段是从更早版本改的。

---

## 6. "显然的写法"对照表

| 显然的写法 | 实际后果 | 证据 |
|---|---|---|
| 整层 `q.float()` 一次 | 2.15 GB fp32 临时量 | `_eff`（:274）的分块注释 |
| 每个序列重新 dequant | 16 次/step，0.377 s（24%） | `runs/A/REPORT.md` §3 |
| fold 一程序一行 | 54× | `galore_fold.py:29-31` |
| fold 的 dot 用 `ieee` | 331.74 ms vs 6.63 ms（50×） | 本文 §3.4 复测 |
| int8 GEMM 用 B 行主序 | 50.3 vs 205.8 TOPS | `bench9.json` |
| 用 `torch.bmm` 做 int8 | `baddbmm_cuda not implemented` | `bench9.json` |
| group-32 权重尺度 | epilogue 不能一次 rescale，掉吞吐 | `moe_int8_gemm.py:7-9` |
| 逐专家循环 GEMM | 18.2 vs 75.0 TFLOP/s（**未落盘**） | 旧报告正文 |
| 物化 `P R` 再乘 | 268 vs 50.3 MFLOP/次 | 本文 §2.4 |
| 方法 B 为 dX 存 fp32 骨架 | 3.2 GB，且漏掉 `P R` | `Int8Expert`（:113）的 `save_for_backward` / `backward` |
| 激活量化写 `round(x / xs * 127)` | 97.7% 饱和、输出偏 279–288% | `train/method_b.py --selftest`（CPU，10 s） |
| `backward` 里再乘 `1/sk_gu` | gu 梯度被除两次 | 同上（`inv_sk` 已删，`apply` 6 参） |

---

## 本篇要点

1. `_q` 是**每输出通道**对称量化（±127），不是 group-32；精度 0.83% 换 epilogue 一次外积
   和 139 TOPS。group-32 更准（0.53%）但会让 int8 GEMM 掉速。
2. `_eff` 的 64 专家分块把 fp32 临时量从 2.15 GB 压到 0.54 GB；但它在 bf16 里做加法，
   且每步被调用 16 次（只有 2 次必要），占前向 50%。
3. 方法 B 用 `(X Rᵀ) Pᵀ` 避免物化 `P R`，省 5.3 倍 FLOPs；但 `save_for_backward` 偷偷存了
   **3.2 GB fp32 骨架**，且 `dX` 漏掉 `P R`——一个未记录的 A/B 差异。
4. fold 内核的价值是"一趟、原地、100% 码一致"；它的 4.1 ms（`gate_up` 半区）是纯拷贝的 2.61 倍，
   这三个数**只有运行时打印，未落盘**。而**它也不是账本里的主项**：一次刷新步（只刷一层）是
   11.72 s，折叠内核只有毫秒级（`06` §4.6–§4.7）。
5. "一程序一行"慢 54× 的根因是 `R` 块被重复读 `BM` 次；修法是让 `BM` 行共享 `R`，不是换更大 tile。
6. `tf32` 比 `ieee` 快 48–50×（复测 50×/68×），代价是 10 位尾数；536 M 元素 0 次翻码，
   但最坏界已接近一个量化台阶，`R` 再大就不安全。注释里的 "exact fp32" 是错的。
7. int8 GEMM 必须 B 列主序（50.3 → 205.8 TOPS）；tile 顺序决定 L2 命中（94 → 139 TOPS @M=128）；
   epilogue 的 rank-1 rescale 是"per-channel 尺度"这一选择的唯一理由。
8. `quant_scheme_decision.py` 用"到最优点的距离"而不是"跟踪误差"，是全文方法论证最正确的一段；
   但它用全秩 `acc` 与全局归一化，只能回答量化问题，不能回答 rank 问题。
9. W8A8 的两个活 bug 都在"看起来还在工作"的地方：多乘 127（97.7% 饱和）与重复除 `sk_gu`。
   检验前者看**饱和比例**，检验后者问"尺度住在一处还是两处"；旧公式还留在注释与复现副本里，
   所以只能用 AST 断言（`train/method_b.py --selftest`）。

---

**上一篇** → [`06-galore-in-our-framework.md`](06-galore-in-our-framework.md)：三区设计、内存账本、
折叠/刷新调度与局限。

**下一篇** → 本系列到此结束。回到 [`00-notation.md`](00-notation.md) 查记号，或从
[`SKILL.md`](../SKILL.md) 的索引选下一个主题。
