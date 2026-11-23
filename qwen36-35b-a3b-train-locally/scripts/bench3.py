"""bench3: weight-gradient (dW) GEMM shapes for MoE full-parameter training.
dW_gate = dY^T X : [MOE_I x t] @ [t x H]  -> M=512, K=t, N=2048
dW_down = dY^T X : [H x t] @ [t x MOE_I]  -> M=2048, K=t, N=512
Small K is the killer: arithmetic intensity and K-loop length.
"""
import torch, time, json

dev = "cuda"
res = {}


def timeit(fn, iters=30, warmup=8):
    for _ in range(warmup):
        fn()
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        fn()
    torch.cuda.synchronize()
    return (time.perf_counter() - t0) / iters


print("=== dW GEMM (weight-gradient) efficiency ===", flush=True)
out = {}
for tag, (M, N) in {"gate/up dW": (512, 2048), "down dW": (2048, 512)}.items():
    for K in [64, 128, 256, 512, 1024, 2048]:
        a = torch.randn(M, K, device=dev, dtype=torch.bfloat16)
        b = torch.randn(K, N, device=dev, dtype=torch.bfloat16)
        t = timeit(lambda: a @ b)
        tf = 2 * M * N * K / t / 1e12
        out[f"{tag}_K{K}"] = tf
        print(f"  {tag:12s} M={M:4d} K={K:5d} N={N:4d}: {tf:7.2f} TFLOP/s  ({t*1e6:6.1f} us)", flush=True)
res["dw_gemm"] = out

print("\n=== forward GEMM for comparison (activations are the M dim) ===", flush=True)
fw = {}
for t in [64, 256, 512, 1024]:
    a = torch.randn(t, 2048, device=dev, dtype=torch.bfloat16)
    w = torch.randn(2048, 512, device=dev, dtype=torch.bfloat16)
    tt = timeit(lambda: a @ w)
    tf = 2 * t * 2048 * 512 / tt / 1e12
    fw[t] = tf
    print(f"  fwd  t={t:5d}: {tf:7.2f} TFLOP/s", flush=True)
res["fwd_gemm"] = fw

print("\n=== how many dW GEMMs per layer ===", flush=True)
print("  256 experts x 3 matrices x 40 layers = 30,720 dW GEMMs per step")
print("  each is tiny -> kernel launch + tail effect dominate; must be GROUPED (one launch)")

# launch overhead measurement: 30720 tiny kernels
print("\n=== launch-overhead floor ===", flush=True)
a = torch.randn(512, 64, device=dev, dtype=torch.bfloat16)
b = torch.randn(64, 2048, device=dev, dtype=torch.bfloat16)
n = 2000
torch.cuda.synchronize()
t0 = time.perf_counter()
for _ in range(n):
    a @ b
torch.cuda.synchronize()
per = (time.perf_counter() - t0) / n
print(f"  1 tiny GEMM round-trip: {per*1e6:.1f} us  ->  30720 of them = {per*30720:.2f} s/step (!!)", flush=True)
res["tiny_gemm_us"] = per * 1e6
res["30720_sequential_s"] = per * 30720

# graph capture to see the floor
try:
    g = torch.cuda.CUDAGraph()
    s = torch.cuda.Stream()
    s.wait_stream(torch.cuda.current_stream())
    with torch.cuda.stream(s):
        for _ in range(5):
            a @ b
    torch.cuda.current_stream().wait_stream(s)
    with torch.cuda.graph(g):
        for _ in range(200):
            a @ b
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(10):
        g.replay()
    torch.cuda.synchronize()
    per_g = (time.perf_counter() - t0) / 10 / 200
    print(f"  with CUDA graph:        {per_g*1e6:.1f} us  ->  30720 = {per_g*30720:.2f} s/step", flush=True)
    res["tiny_gemm_graph_us"] = per_g * 1e6
except Exception as e:
    print("  graph failed:", e, flush=True)

with open("/data/train35b/bench/bench3.json", "w") as f:
    json.dump(res, f, indent=1)
