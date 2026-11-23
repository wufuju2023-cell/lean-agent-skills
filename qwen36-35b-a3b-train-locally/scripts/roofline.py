"""Roofline probe for 3080-20G: PCIe H2D/D2H, bf16 matmul, int8 matmul, dequant cost."""
import torch, time, json, sys

dev = "cuda"
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True
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


# ---------------- PCIe ----------------
print("== PCIe (pinned) ==", flush=True)
pcie = {}
for mb in [1, 4, 16, 64, 256]:
    n = mb * 1024 * 1024 // 2
    host = torch.empty(n, dtype=torch.float16).pin_memory()
    gpu = torch.empty(n, dtype=torch.float16, device=dev)
    it = max(5, 200 // mb)

    def h2d():
        gpu.copy_(host, non_blocking=True)

    def d2h():
        host.copy_(gpu, non_blocking=True)

    th = timeit(h2d, it)
    td = timeit(d2h, it)
    pcie[mb] = {"h2d_GBs": mb / 1024 / th, "d2h_GBs": mb / 1024 / td}
    print(f"  {mb:4d} MB  H2D {mb/1024/th:6.2f} GB/s   D2H {mb/1024/td:6.2f} GB/s", flush=True)
res["pcie"] = pcie

# pageable -> pinned staging cost (the naive offload path)
print("== pageable->pinned staging ==", flush=True)
n = 64 * 1024 * 1024 // 2
page = torch.empty(n, dtype=torch.float16)
pinned = torch.empty(n, dtype=torch.float16).pin_memory()
ts = timeit(lambda: pinned.copy_(page), 5)
print(f"  pageable copy 64MB: {64/1024/ts:.2f} GB/s (CPU-side memcpy)", flush=True)
res["pageable_copy_GBs"] = 64 / 1024 / ts

# ---------------- compute ----------------
print("== dense matmul ==", flush=True)
mm = {}
for dt, name in [(torch.bfloat16, "bf16"), (torch.float16, "fp16")]:
    for M in [1024, 4096, 8192]:
        N = K = 4096
        a = torch.randn(M, K, device=dev, dtype=dt)
        b = torch.randn(K, N, device=dev, dtype=dt)
        t = timeit(lambda: a @ b, iters=10)
        tf = 2 * M * N * K / t / 1e12
        mm[f"{name}_{M}x4096x4096"] = tf
        print(f"  {name} M={M:5d}: {tf:7.1f} TFLOP/s", flush=True)
res["matmul_TFLOPs"] = mm

# ---------------- int8 ----------------
print("== int8 tensor core ==", flush=True)
try:
    i8 = {}
    for M in [4096, 8192]:
        N = K = 4096
        a = torch.randint(-127, 127, (M, K), device=dev, dtype=torch.int8)
        b = torch.randint(-127, 127, (K, N), device=dev, dtype=torch.int8)
        t = timeit(lambda: torch._int_mm(a, b), iters=10)
        tf = 2 * M * N * K / t / 1e12
        i8[f"int8_{M}"] = tf
        print(f"  int8 M={M:5d}: {tf:7.1f} TOP/s", flush=True)
    res["int8_TOPs"] = i8
except Exception as e:
    print("  int8 failed:", e, flush=True)

# ---------------- memory bandwidth ----------------
print("== HBM bandwidth ==", flush=True)
x = torch.empty(1 << 28, dtype=torch.uint8, device=dev)  # 256MB
y = torch.empty_like(x)
t = timeit(lambda: y.copy_(x), 10)
print(f"  copy 256MB: {2*256/1024/t:.1f} GB/s effective", flush=True)
res["hbm_copy_GBs"] = 2 * 256 / 1024 / t

# ---------------- dequant cost (toy) ----------------
print("== dequant overhead (int4->bf16, elementwise) ==", flush=True)
N = 1 << 26  # 64M
q = torch.randint(0, 16, (N,), device=dev, dtype=torch.uint8)
lut = torch.arange(16, device=dev, dtype=torch.bfloat16)
t = timeit(lambda: lut[q], 10)
print(f"  LUT dequant 64M elems: {t*1e3:.2f} ms -> {N/t/1e9:.1f} Gelem/s", flush=True)
res["dequant_Gelem_s"] = N / t / 1e9

print(json.dumps(res, indent=1))
with open("/data/train35b/bench/roofline.json", "w") as f:
    json.dump(res, f, indent=1)
