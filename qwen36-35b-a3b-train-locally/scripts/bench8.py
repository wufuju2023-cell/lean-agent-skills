"""bench8: a real Triton int8->bf16 dequant kernel (no fp32 intermediates),
to measure how much of the +229% naive penalty a decent kernel recovers.
Also tells us whether sm86 INT8 tensor cores are usable at all.
"""
import torch, time, json
import triton
import triton.language as tl

dev = "cuda"
bf16 = torch.bfloat16
NE, H, I = 256, 2048, 512
res = {}


@triton.jit
def deq_kernel(Q, S, OUT, n_elem_per_row, GROUP: tl.constexpr, BLOCK: tl.constexpr):
    """Q: int8 [n_rows, n_elem_per_row], S: fp16 [n_rows, n_elem_per_row//GROUP], OUT: bf16 same shape as Q."""
    pid = tl.program_id(0)
    row = pid // tl.cdiv(n_elem_per_row, BLOCK)
    blk = pid % tl.cdiv(n_elem_per_row, BLOCK)
    offs = blk * BLOCK + tl.arange(0, BLOCK)
    mask = offs < n_elem_per_row
    q = tl.load(Q + row * n_elem_per_row + offs, mask=mask, other=0).to(tl.float32)
    g = offs // GROUP
    s = tl.load(S + row * (n_elem_per_row // GROUP) + g, mask=mask, other=1.0).to(tl.float32)
    tl.store(OUT + row * n_elem_per_row + offs, (q * s).to(tl.bfloat16), mask=mask)


def q8(W, group=32):
    out, inn = W.shape[1], W.shape[2]
    Wg = W.float().view(NE, out, inn // group, group)
    amax = Wg.abs().amax(-1, keepdim=True).clamp_min(1e-12)
    sc = (amax / 127).squeeze(-1).to(torch.float16)
    q = torch.round(Wg / amax * 127).clamp(-127, 127).to(torch.int8).view(NE, out, inn)
    return q.contiguous(), sc.contiguous()


def timeit(fn, iters=10, warmup=3):
    for _ in range(warmup):
        fn()
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        fn()
    torch.cuda.synchronize()
    return (time.perf_counter() - t0) / iters


Wgu = torch.randn(NE, 1024, H, device=dev, dtype=bf16)
Wd = torch.randn(NE, H, 512, device=dev, dtype=bf16)
qgu, sgu = q8(Wgu)
qd, sd = q8(Wd)
buf_gu = torch.empty_like(Wgu)
buf_d = torch.empty_like(Wd)

n1, n2 = qgu.numel(), qd.numel()
BLOCK = 1024
print(f"int8 bytes {n1/1e9:.2f} GB (gate_up) + {n2/1e9:.2f} GB (down)", flush=True)

# ---- naive (torch) ----
def deq_torch(q, s):
    out, inn = q.shape[1], q.shape[2]
    return (q.float().view(NE, out, inn // 32, 32) * s.float().unsqueeze(-1)).view(NE, out, inn).to(bf16)


t_naive = timeit(lambda: (buf_gu.copy_(deq_torch(qgu, sgu)), buf_d.copy_(deq_torch(qd, sd))))
print(f"  torch dequant          : {t_naive*1e3:6.2f} ms  ({2*(n1+n2)/1e9/t_naive:.0f} GB/s r+w)", flush=True)
res["torch_dequant_ms"] = t_naive * 1e3

# ---- triton ----
def deq_tri(q, s, out):
    n_rows, ncols = q.shape[0] * q.shape[1], q.shape[2]
    grid = (n_rows * triton.cdiv(ncols, BLOCK),)
    deq_kernel[grid](q, s, out, ncols, GROUP=32, BLOCK=BLOCK)


t_tri = timeit(lambda: (deq_tri(qgu, sgu, buf_gu), deq_tri(qd, sd, buf_d)))
print(f"  triton dequant         : {t_tri*1e3:6.2f} ms  ({2*(n1+n2)/1e9/t_tri:.0f} GB/s r+w)  speedup {t_naive/t_tri:.1f}x", flush=True)
res["triton_dequant_ms"] = t_tri * 1e3
res["speedup"] = t_naive / t_tri

# verify correctness
deq_tri(qgu, sgu, buf_gu)
ref = deq_torch(qgu, sgu)
print(f"  max abs err vs torch   : {(buf_gu.float()-ref.float()).abs().max().item():.3e}", flush=True)

# ---- end to end ----
X = torch.randn(NE, 512, H, device=dev, dtype=bf16)
hh = torch.randn(NE, 512, 512, device=dev, dtype=bf16)


def gemm():
    torch.bmm(X, buf_gu.transpose(1, 2)); torch.bmm(hh, buf_d.transpose(1, 2))


t_gemm = timeit(gemm)
def path_naive():
    buf_gu.copy_(deq_torch(qgu, sgu)); buf_d.copy_(deq_torch(qd, sd)); gemm()
def path_tri():
    deq_tri(qgu, sgu, buf_gu); deq_tri(qd, sd, buf_d); gemm()
t_naive_e2e = timeit(path_naive, 5)
t_tri_e2e = timeit(path_tri, 5)
print(f"\n  pure GEMM              : {t_gemm*1e3:6.2f} ms   (the floor)", flush=True)
print(f"  naive dequant+GEMM     : {t_naive_e2e*1e3:6.2f} ms   (+{(t_naive_e2e/t_gemm-1)*100:.0f}%)", flush=True)
print(f"  triton dequant+GEMM    : {t_tri_e2e*1e3:6.2f} ms   (+{(t_tri_e2e/t_gemm-1)*100:.0f}%)", flush=True)
res.update(gemm_ms=t_gemm * 1e3, naive_e2e_ms=t_naive_e2e * 1e3, triton_e2e_ms=t_tri_e2e * 1e3)
print(f"\n  a fused (dequant-in-GEMM) kernel should get close to {t_gemm*1e3:.1f} ms;"
      f" the remaining gap is the streaming cost you pay once anyway.", flush=True)

# ---- int8 tensor core truth check (triton int8 dot) ----
print("\n=== does sm86 use INT8 tensor cores? (triton tl.dot with int8) ===", flush=True)
@triton.jit
def mm_i8(A, B, C, M, N, K, BM: tl.constexpr, BN: tl.constexpr, BK: tl.constexpr):
    pid = tl.program_id(0)
    nbn = tl.cdiv(N, BN)
    pm, pn = pid // nbn, pid % nbn
    rm = pm * BM + tl.arange(0, BM)
    rn = pn * BN + tl.arange(0, BN)
    rk = tl.arange(0, BK)
    acc = tl.zeros((BM, BN), dtype=tl.int32)
    for k in range(0, K, BK):
        a = tl.load(A + rm[:, None] * K + (k + rk)[None, :])
        b = tl.load(B + (k + rk)[:, None] * N + rn[None, :])
        acc += tl.dot(a, b, out_dtype=tl.int32)
    tl.store(C + rm[:, None] * N + rn[None, :], acc)


M = N = K = 4096
ai = torch.randint(-127, 127, (M, K), device=dev, dtype=torch.int8)
bi = torch.randint(-127, 127, (K, N), device=dev, dtype=torch.int8)
ci = torch.empty((M, N), device=dev, dtype=torch.int32)
grid = (triton.cdiv(M, 64) * triton.cdiv(N, 64),)


def run_i8():
    mm_i8[grid](ai, bi, ci, M, N, K, BM=64, BN=64, BK=64)


try:
    t = timeit(run_i8, 5)
    tf = 2 * M * N * K / t / 1e12
    print(f"  triton int8 GEMM 4096^3 : {t*1e3:.2f} ms -> {tf:.0f} TOP/s (sm86 spec ~238)", flush=True)
    res["triton_int8_TOPs"] = tf
except Exception as e:
    print("  failed:", repr(e)[:200], flush=True)

with open("/data/train35b/bench/bench8.json", "w") as f:
    json.dump(res, f, indent=1)
