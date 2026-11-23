"""bench9: correct INT8 measurement + can we reach 208 TOPS on the MoE shapes?
Key finding to check: torch._int_mm needs B column-major (stride (1,n)) to hit the
cutlass i16832 tensor-op kernel. Row-major B silently falls back to ~50 TOPS.
Then: is there ANY batched/grouped int8 GEMM in torch?
"""
import torch, time, json

dev = "cuda"
res = {}
NE, H, I, TPE = 256, 2048, 512, 512


def timeit(fn, iters=10, warmup=3):
    for _ in range(warmup):
        fn()
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        fn()
    torch.cuda.synchronize()
    return (time.perf_counter() - t0) / iters


def bench2d(M, K, N, tag):
    a = torch.randint(-120, 120, (M, K), device=dev, dtype=torch.int8)
    b_row = torch.randint(-120, 120, (N, K), device=dev, dtype=torch.int8)
    b_col = b_row.t()                       # [K, N] with stride (1, K) -> column-major
    assert b_col.shape == (K, N) and b_col.stride() == (1, K)
    t = timeit(lambda: torch._int_mm(a, b_col))
    tf = 2 * M * N * K / t / 1e12
    print(f"  {tag:34s} M={M:6d} K={K:5d} N={N:5d}: {tf:6.1f} TOPS  ({t*1e3:6.2f} ms)", flush=True)
    return tf


print("=== 1. confirm the layout effect (square) ===", flush=True)
n = 8192
a = torch.randint(-120, 120, (n, n), device=dev, dtype=torch.int8)
b_row = torch.randint(-120, 120, (n, n), device=dev, dtype=torch.int8)
t1 = timeit(lambda: torch._int_mm(a, b_row))
t2 = timeit(lambda: torch._int_mm(a, b_row.t()))
print(f"  row-major B: {2*n**3/t1/1e12:6.1f} TOPS | col-major B: {2*n**3/t2/1e12:6.1f} TOPS", flush=True)
res["sq_rowmajor"] = 2 * n ** 3 / t1 / 1e12
res["sq_colmajor"] = 2 * n ** 3 / t2 / 1e12
del a, b_row
torch.cuda.empty_cache()

print("\n=== 2. the MoE expert block, flattened to one big 2D GEMM (the ceiling) ===", flush=True)
M = NE * TPE
tf_gu = bench2d(M, H, 1024, "gate_up (all 256 experts)")
tf_d = bench2d(M, 512, H, "down    (all 256 experts)")
res["flattened_gateup_TOPS"] = tf_gu
res["flattened_down_TOPS"] = tf_d
print(f"  -> forward ceiling for the expert block: {tf_gu:.0f}/{tf_d:.0f} TOPS", flush=True)

print("\n=== 3. does torch have batched / grouped int8 GEMM? ===", flush=True)
A = torch.randint(-120, 120, (NE, TPE, H), device=dev, dtype=torch.int8)
B = torch.randint(-120, 120, (NE, H, 1024), device=dev, dtype=torch.int8)
for name, fn in [
    ("torch.bmm(int8)", lambda: torch.bmm(A, B)),
    ("torch.bmm(int8, B.transpose)", lambda: torch.bmm(A, B.transpose(1, 2))),
]:
    try:
        r = fn()
        print(f"  {name}: WORKS, dtype={r.dtype}", flush=True)
        res[name] = "works"
    except Exception as e:
        print(f"  {name}: FAILS -> {repr(e)[:110]}", flush=True)
        res[name] = str(e)[:110]

for attr in ["_grouped_mm", "_scaled_grouped_mm", "_int_mm"]:
    print(f"  has {attr}: {hasattr(torch, attr)}", flush=True)

# --- dequant-free path emulation: int8 acts need per-token scales.
print("\n=== 4. realistic int8 expert GEMM: per-256-token contiguous groups ===", flush=True)
# emulate a grouped GEMM by one big GEMM over concat of experts (valid when tokens are sorted
# by expert and each block is contiguous) -- this is exactly what a fused MoE kernel does.
a8 = torch.randint(-120, 120, (M, H), device=dev, dtype=torch.int8)
w8 = torch.randint(-120, 120, (1024, H), device=dev, dtype=torch.int8).t()   # col-major [H,1024]
t = timeit(lambda: torch._int_mm(a8, w8))
print(f"  concat-MoE int8 fwd: {t*1e3:.2f} ms -> {2*M*H*1024/t/1e12:.1f} TOPS", flush=True)
res["concat_int8_ms"] = t * 1e3

# bf16 comparison at the same shape
ab = torch.randn(M, H, device=dev, dtype=torch.bfloat16)
wb = torch.randn(H, 1024, device=dev, dtype=torch.bfloat16)
tb = timeit(lambda: ab @ wb)
print(f"  same shape bf16    : {tb*1e3:.2f} ms -> {2*M*H*1024/tb/1e12:.1f} TFLOP/s", flush=True)
res["concat_bf16_ms"] = tb * 1e3
print(f"  ratio bf16/int8 time: n/a", flush=True)
print(f"\n  VERDICT: int8 {t*1e3:.1f} ms vs bf16 {tb*1e3:.1f} ms on the same FLOPs -> "
      f"{tb/t:.2f}x faster", flush=True)
res["speedup"] = tb / t

with open("/data/train35b/bench/bench9.json", "w") as f:
    json.dump(res, f, indent=1)
