"""Bench2: dequant cost, MoE-shaped GEMM, and PCIe<->compute overlap (the decisive one)."""
import torch, time, json

dev = "cuda"
res = {}


def timeit(fn, iters=20, warmup=5):
    for _ in range(warmup):
        fn()
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        fn()
    torch.cuda.synchronize()
    return (time.perf_counter() - t0) / iters


# ---------- 1. int4 -> bf16 dequant ----------
print("== int4 dequant (lut gather) ==", flush=True)
N = 1 << 26
q = torch.randint(0, 16, (N,), device=dev, dtype=torch.int64)
lut = torch.arange(16, device=dev, dtype=torch.bfloat16)
t = timeit(lambda: lut[q], 10)
print(f"  64M elems: {t*1e3:.2f} ms -> {N/t/1e9:.1f} Gelem/s", flush=True)
res["dequant_Gelem_s"] = N / t / 1e9

# a fused-path style: unpack 2x4bit -> 2 values, shift/and, cast
u8 = torch.randint(0, 255, (N // 2,), device=dev, dtype=torch.uint8)


def unpack():
    lo = (u8 & 0x0F).to(torch.bfloat16)
    hi = (u8 >> 4).to(torch.bfloat16)
    return lo, hi


t = timeit(unpack, 10)
print(f"  bit-unpack 64M nibbles: {t*1e3:.2f} ms -> {N/t/1e9:.1f} Gelem/s", flush=True)
res["unpack_Gelem_s"] = N / t / 1e9

# ---------- 2. MoE-shaped GEMM ----------
print("== MoE-shaped GEMM (bf16) ==", flush=True)
# Qwen-ish MoE expert: hidden 2048 -> intermediate 768 (gate/up), 768 -> 2048 (down)
efficiency = {}
for tokens_per_expert in [8, 16, 32, 64, 128, 256, 512]:
    M = tokens_per_expert
    for (K, Nn, tag) in [(2048, 768, "gate/up"), (768, 2048, "down")]:
        a = torch.randn(M, K, device=dev, dtype=torch.bfloat16)
        w = torch.randn(K, Nn, device=dev, dtype=torch.bfloat16)
        t = timeit(lambda: a @ w, 50)
        tf = 2 * M * K * Nn / t / 1e12
        efficiency[f"{tag}_M{M}"] = tf
        print(f"  {tag:8s} M={M:4d}: {tf:6.2f} TFLOP/s", flush=True)
res["moe_gemm_TFLOPs"] = efficiency

print("== grouped 128-expert loop (128 x M=64) ==", flush=True)
ws = [torch.randn(2048, 768, device=dev, dtype=torch.bfloat16) for _ in range(128)]
as_ = torch.randn(64, 2048, device=dev, dtype=torch.bfloat16)


def grouped():
    for w in ws:
        _ = as_ @ w


t = timeit(grouped, 5)
fl = 128 * 2 * 64 * 2048 * 768
print(f"  128 experts x 64 tok: {t*1e3:6.2f} ms -> {fl/t/1e12:6.2f} TFLOP/s", flush=True)
res["grouped128_TFLOPs"] = fl / t / 1e12
res["grouped128_ms"] = t * 1e3

# ---------- 3. overlap: H2D vs compute ----------
print("== overlap test: PCIe H2D concurrent with GEMM ==", flush=True)
MB = 2048
n = MB * 1024 * 1024 // 2
host = torch.empty(n, dtype=torch.float16).pin_memory()
gpu_buf = torch.empty(n, dtype=torch.float16, device=dev)
chunks = 64
csz = n // chunks
dst = gpu_buf.view(chunks, csz)

# pure transfer
s = torch.cuda.Stream()
ev = torch.cuda.Event()
torch.cuda.synchronize()
t0 = time.perf_counter()
for i in range(chunks):
    with torch.cuda.stream(s):
        dst[i].copy_(host.view(chunks, csz)[i], non_blocking=True)
torch.cuda.synchronize()
t_transfer = time.perf_counter() - t0
print(f"  pure H2D {MB}MB: {t_transfer:.3f}s -> {MB/1024/t_transfer:.2f} GB/s", flush=True)

# compute-only baseline
a = torch.randn(4096, 4096, device=dev, dtype=torch.bfloat16)
b = torch.randn(4096, 4096, device=dev, dtype=torch.bfloat16)
t_gemm = timeit(lambda: a @ b, 3)


def gemm_n(k):
    for _ in range(k):
        a @ b


torch.cuda.synchronize()
t0 = time.perf_counter()
gemm_n(10)
torch.cuda.synchronize()
t_compute = time.perf_counter() - t0
print(f"  pure compute (10 big GEMM): {t_compute:.3f}s", flush=True)

# overlapped
torch.cuda.synchronize()
t0 = time.perf_counter()
for i in range(chunks):
    with torch.cuda.stream(s):
        dst[i].copy_(host.view(chunks, csz)[i], non_blocking=True)
gemm_n(10)
torch.cuda.synchronize()
t_overlap = time.perf_counter() - t0
print(f"  overlapped total: {t_overlap:.3f}s   (sum would be {t_transfer+t_compute:.3f}s)", flush=True)
print(f"  -> hidden fraction: {(t_transfer+t_compute-t_overlap)/t_transfer*100:.0f}% of transfer hidden", flush=True)
res["overlap"] = {
    "transfer_s": t_transfer,
    "compute_s": t_compute,
    "overlap_s": t_overlap,
    "hidden_pct": (t_transfer + t_compute - t_overlap) / t_transfer * 100,
}

with open("/data/train35b/bench/bench2.json", "w") as f:
    json.dump(res, f, indent=1)
