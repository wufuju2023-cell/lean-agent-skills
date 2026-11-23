"""bench5: attention-path efficiency at high M (the resident part that hides PCIe),
plus a corrected overlap measurement."""
import torch, time, json

dev = "cuda"
res = {}
bf16 = torch.bfloat16
H, MOE_I, NE, TPE = 2048, 512, 256, 512


def timeit(fn, iters=10, warmup=3):
    for _ in range(warmup):
        fn()
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        fn()
    torch.cuda.synchronize()
    return (time.perf_counter() - t0) / iters


T = 16384
print(f"=== attention projection GEMMs at M={T} (dense, weights resident) ===", flush=True)
out = {}
# linear attention layer: qk proj to 16*128, v proj to 32*128, o proj back
shapes = {
    "lin qk  (2048->2048)": (H, 2048),
    "lin v   (2048->4096)": (H, 4096),
    "lin o   (4096->2048)": (4096, H),
    "full q  (2048->4096)": (H, 4096),
    "full o  (4096->2048)": (4096, H),
}
x = torch.randn(T, H, device=dev, dtype=bf16)
for name, (K, N) in shapes.items():
    a = torch.randn(T, K, device=dev, dtype=bf16)
    w = torch.randn(K, N, device=dev, dtype=bf16)
    t = timeit(lambda: a @ w)
    tf = 2 * T * K * N / t / 1e12
    out[name] = {"ms": t * 1e3, "tflops": tf}
    print(f"  {name:24s} {t*1e3:6.2f} ms  {tf:6.1f} TFLOP/s", flush=True)
res["attn_gemm"] = out

# linear-attention recurrent state (gated delta net) memory per layer per sequence
print("\n=== gated-delta-net state size (why 30/40 layers are cheap in ctx) ===", flush=True)
S = 32 * 128 * 128
print(f"  per layer per sequence: {S*4/1e6:.2f} MB fp32")
print(f"  30 layers x 16 seq of 1024 tok: {30*16*S*4/1e9:.2f} GB", flush=True)
res["lin_state_gb"] = 30 * 16 * S * 4 / 1e9

# ---- corrected overlap: 1 layer of expert compute vs 1 layer of weight stream
print("\n=== corrected per-layer overlap (int8, one layer = 805 MB) ===", flush=True)
Wg = torch.randn(NE, H, MOE_I, device=dev, dtype=bf16)
Xg = torch.randn(NE, TPE, H, device=dev, dtype=bf16)
dY = torch.randn(NE, TPE, MOE_I, device=dev, dtype=bf16)
WgT = Wg.transpose(1, 2).contiguous()
nbytes = NE * 3 * H * MOE_I
host = torch.empty(nbytes, dtype=torch.uint8).pin_memory()
gdev = torch.empty(nbytes, dtype=torch.uint8, device=dev)


def one_group():
    torch.bmm(Xg, Wg); torch.bmm(dY.transpose(1, 2), Xg); torch.bmm(dY, WgT)


t_comp = timeit(one_group, 5)
print(f"  compute-only (3 bmms, 1 matrix each): {t_comp*1e3:.1f} ms", flush=True)
s = torch.cuda.Stream()
torch.cuda.synchronize()
t0 = time.perf_counter()
with torch.cuda.stream(s):
    gdev.copy_(host, non_blocking=True)
one_group()
torch.cuda.synchronize()
t_ov = time.perf_counter() - t0
t_stream = timeit(lambda: gdev.copy_(host, non_blocking=True), 5)
print(f"  stream-only {t_stream*1e3:.1f} ms | compute-only {t_comp*1e3:.1f} ms | overlapped {t_ov*1e3:.1f} ms", flush=True)
print(f"  -> max(compute,stream)={max(t_comp,t_stream)*1e3:.1f} ms, overlapped {t_ov*1e3:.1f} ms"
      f"  overhead {(t_ov-max(t_comp,t_stream))*1e3:+.1f} ms", flush=True)
res["overlap"] = {"compute_ms": t_comp * 1e3, "stream_ms": t_stream * 1e3,
                  "overlapped_ms": t_ov * 1e3, "ideal_ms": max(t_comp, t_stream) * 1e3}

with open("/data/train35b/bench/bench5.json", "w") as f:
    json.dump(res, f, indent=1)
