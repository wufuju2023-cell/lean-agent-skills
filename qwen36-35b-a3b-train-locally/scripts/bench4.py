"""bench4: THE decisive experiment.
One full MoE expert block at 16384 tokens/step (tokens_per_expert = 512),
fwd + dX + dW computed as one grouped GEMM (uniform group size => torch.bmm is the ideal case),
and whether PCIe streaming of the int8 expert weights hides behind it.
"""
import torch, time, json

dev = "cuda"
res = {}
H, MOE_I, NE, TPE = 2048, 512, 256, 512   # TPE = tokens per expert
print(f"config: 16384 tok/step, {NE} experts, {TPE} tok/expert, H={H}, MOE_I={MOE_I}", flush=True)


def timeit(fn, iters=10, warmup=3):
    for _ in range(warmup):
        fn()
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        fn()
    torch.cuda.synchronize()
    return (time.perf_counter() - t0) / iters


bf16 = torch.bfloat16
# expert weights for ONE layer, per matrix: [NE, 2048, 512] = 537 MB bf16
Wg = torch.randn(NE, H, MOE_I, device=dev, dtype=bf16)
Xg = torch.randn(NE, TPE, H, device=dev, dtype=bf16)
print(f"  one matrix set: {NE*H*MOE_I*2/1e9:.2f} GB bf16", flush=True)

# ---- forward: [NE, TPE, H] @ [NE, H, MOE_I]
t_fwd = timeit(lambda: torch.bmm(Xg, Wg))
fl_fwd = NE * 2 * TPE * H * MOE_I
print(f"  fwd  grouped ({NE}x {TPE}x{H}x{MOE_I}): {t_fwd*1e3:6.2f} ms  {fl_fwd/t_fwd/1e12:6.2f} TFLOP/s", flush=True)
res["fwd_ms"] = t_fwd * 1e3
res["fwd_tflops"] = fl_fwd / t_fwd / 1e12

# ---- dW: dY^T @ X  -> [NE, MOE_I, H]
dY = torch.randn(NE, TPE, MOE_I, device=dev, dtype=bf16)
t_dw = timeit(lambda: torch.bmm(dY.transpose(1, 2), Xg))
fl_dw = NE * 2 * MOE_I * TPE * H
print(f"  dW   grouped (M={MOE_I},K={TPE},N={H}): {t_dw*1e3:6.2f} ms  {fl_dw/t_dw/1e12:6.2f} TFLOP/s", flush=True)
res["dw_ms"] = t_dw * 1e3
res["dw_tflops"] = fl_dw / t_dw / 1e12

# ---- dX: dY @ W^T -> [NE, TPE, H]
WgT = Wg.transpose(1, 2).contiguous()
t_dx = timeit(lambda: torch.bmm(dY, WgT))
fl_dx = NE * 2 * TPE * MOE_I * H
print(f"  dX   grouped: {t_dx*1e3:6.2f} ms  {fl_dx/t_dx/1e12:6.2f} TFLOP/s", flush=True)
res["dx_ms"] = t_dx * 1e3
res["dx_tflops"] = fl_dx / t_dx / 1e12

# ---- full expert block (gate + up + down => 3x the above per direction)
t_block = 3 * (t_fwd + t_dw + t_dx)
fl_block = 3 * (fl_fwd + fl_dw + fl_dx)
print(f"\n  FULL expert block (3 matrices x fwd+dW+dX): {t_block*1e3:6.1f} ms/layer"
      f"  {fl_block/t_block/1e12:6.2f} TFLOP/s", flush=True)
print(f"  x40 layers = {t_block*40:.2f} s/step  (experts only, no attention)", flush=True)
res["block_ms"] = t_block * 1e3
res["block_tflops"] = fl_block / t_block / 1e12
res["step_experts_only_s"] = t_block * 40

# ---- streaming overlap: int8 expert weights for one layer = 805 MB
print("\n== overlap: stream 805MB int8 from pinned host while computing the block ==", flush=True)
nbytes = NE * 3 * H * MOE_I  # int8, one layer
host = torch.empty(nbytes, dtype=torch.uint8).pin_memory()
gdev = torch.empty(nbytes, dtype=torch.uint8, device=dev)
t_stream = timeit(lambda: gdev.copy_(host, non_blocking=True), 10)
print(f"  pure H2D 805MB: {t_stream*1e3:.1f} ms -> {nbytes/1e9/t_stream:.2f} GB/s", flush=True)
res["stream_805ms"] = t_stream * 1e3

s = torch.cuda.Stream()
torch.cuda.synchronize()
t0 = time.perf_counter()
with torch.cuda.stream(s):
    gdev.copy_(host, non_blocking=True)
for _ in range(3):
    torch.bmm(Xg, Wg); torch.bmm(dY.transpose(1, 2), Xg); torch.bmm(dY, WgT)
torch.cuda.synchronize()
t_ov = time.perf_counter() - t0
print(f"  overlapped: {t_ov*1e3:.1f} ms   (block {3*t_block*1e3:.1f} + stream {t_stream*1e3:.1f} = {3*t_block*1e3+t_stream*1e3:.1f})", flush=True)
hid = (3 * t_block + t_stream - t_ov) / t_stream * 100
print(f"  -> {hid:.0f}% of the transfer hidden behind compute", flush=True)
res["overlap_ms"] = t_ov * 1e3
res["hidden_pct"] = hid

with open("/data/train35b/bench/bench4.json", "w") as f:
    json.dump(res, f, indent=1)
