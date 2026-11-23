"""bench7: is a FUSED int8-dequant GEMM worth writing?
Compare the expert block three ways:
  (a) weights already bf16 in HBM          -> pure GEMM
  (b) int8 in HBM, dequant to a bf16 buffer, then GEMM  (what plain torch forces)
  (c) int8 in HBM -> H2D only (the stream cost we must beat)
"""
import torch, time, json

dev = "cuda"
bf16 = torch.bfloat16
H, NE, I = 2048, 256, 512
res = {}


def timeit(fn, iters=8, warmup=3):
    for _ in range(warmup):
        fn()
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        fn()
    torch.cuda.synchronize()
    return (time.perf_counter() - t0) / iters


TPE = 512
print(f"expert block, tokens/expert={TPE}", flush=True)
X = torch.randn(NE, TPE, H, device=dev, dtype=bf16)
hh = torch.randn(NE, TPE, 512, device=dev, dtype=bf16)   # swiglu output -> down_proj input
Wgu_bf = torch.randn(NE, 1024, H, device=dev, dtype=bf16)
Wd_bf = torch.randn(NE, H, 512, device=dev, dtype=bf16)

# int8 quantized copies + per-group(32) fp16 scales, laid out as [NE, out, in]
def q8(W):
    out, inn = W.shape[1], W.shape[2]
    Wg = W.float().view(NE, out, inn // 32, 32)
    amax = Wg.abs().amax(-1, keepdim=True).clamp_min(1e-12)
    sc = (amax / 127).squeeze(-1).to(torch.float16)
    q = torch.round(Wg / amax * 127).clamp(-127, 127).to(torch.int8).view(NE, out, inn)
    return q, sc


qgu, sgu = q8(Wgu_bf)
qd, sd = q8(Wd_bf)


def deq(q, s):
    out, inn = q.shape[1], q.shape[2]
    f = q.float().view(NE, out, inn // 32, 32) * s.float().unsqueeze(-1)
    return f.view(NE, out, inn).to(bf16)


# (a) bf16 in HBM
t_a = timeit(lambda: (torch.bmm(X, Wgu_bf.transpose(1, 2)), torch.bmm(hh, Wd_bf.transpose(1, 2))))
print(f"  (a) bf16 HBM            : {t_a*1e3:6.2f} ms", flush=True)
res["a_bf16_ms"] = t_a * 1e3

# (b) dequant then GEMM
buf_gu = torch.empty(NE, 1024, H, device=dev, dtype=bf16)
buf_d = torch.empty(NE, H, 512, device=dev, dtype=bf16)


def path_b():
    buf_gu.copy_(deq(qgu, sgu)); buf_d.copy_(deq(qd, sd))
    torch.bmm(X, buf_gu.transpose(1, 2)); torch.bmm(hh, buf_d.transpose(1, 2))


t_b = timeit(path_b)
print(f"  (b) int8 HBM -> dequant -> GEMM : {t_b*1e3:6.2f} ms   (+{(t_b/t_a-1)*100:.0f}%)", flush=True)
res["b_dequant_gemm_ms"] = t_b * 1e3

# dequant only (into preallocated buffer, no alloc)
t_dq = timeit(lambda: (buf_gu.copy_(deq(qgu, sgu)), buf_d.copy_(deq(qd, sd))))
print(f"      of which dequant alone     : {t_dq*1e3:6.2f} ms", flush=True)
res["dequant_only_ms"] = t_dq * 1e3

n = NE * (1024 * H + H * 512)
print(f"      int8 bytes {n/1e9:.2f} GB, bf16 bytes {2*n/1e9:.2f} GB", flush=True)
print(f"      -> extra HBM write+read = {4*n/1e9:.2f} GB at ~640 GB/s = {4*n/640e9*1e3:.1f} ms", flush=True)

# (c) H2D of the int8 weights from pinned host
host = torch.empty(n, dtype=torch.uint8).pin_memory()
gdev = torch.empty(n, dtype=torch.uint8, device=dev)
t_c = timeit(lambda: gdev.copy_(host, non_blocking=True))
print(f"  (c) int8 stream over PCIe      : {t_c*1e3:6.2f} ms  ({n/1e9/t_c:.2f} GB/s)", flush=True)
res["c_stream_ms"] = t_c * 1e3

print(f"\n  VERDICT: path (b) costs {(t_b-t_a)*1e3:+.1f} ms/layer vs (a)."
      f" A fused kernel recovers most of it. Per 40-layer step that is "
      f"{(t_b-t_a)*40:.2f} s of a {max(t_b*40, 2.75):.2f} s step.", flush=True)
print(f"  Also: (c) {t_c*1e3:.1f} ms stream vs {t_a*1e3:.1f} ms GEMM -> transfer is "
      f"{t_c/t_a:.2f}x the compute for one pass, so 2 passes need the attention FLOPs to cover it.", flush=True)
res["verdict_ms_per_layer"] = (t_b - t_a) * 1e3
with open("/data/train35b/bench/bench7.json", "w") as f:
    json.dump(res, f, indent=1)
