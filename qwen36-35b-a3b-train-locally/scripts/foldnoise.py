"""The go/no-go experiment for FULL-PARAMETER training with quantized master weights.

Setup: master weight W is stored quantized (int8 / int4, per-group scale). GaLore accumulates
the update in a low-rank factor and periodically FOLDS it into the quantized store.
Question: at realistic Adam step sizes, how much error does folding inject, and how often
may we fold?

Metric that matters is functional: ||(W_q - W_ref) x|| / ||W_ref x|| on the matrix's own
input distribution (isotropic proxy), reported as a per-element and per-output SNR.
Also tests stochastic rounding (SR) and error feedback across folds.
"""
import torch, json, sys, glob, time

torch.manual_seed(0)
dev = "cuda" if torch.cuda.is_available() else "cpu"
res = {}


def quantize(W, bits, group, sr=False):
    """per-group absmax symmetric quantization; returns (codes, scale) with group along last dim"""
    assert W.shape[-1] % group == 0
    n = W.shape[-1] // group
    Wg = W.view(*W.shape[:-1], n, group)
    amax = Wg.abs().amax(dim=-1, keepdim=True).clamp_min(1e-12)
    qmax = 2 ** (bits - 1) - 1
    scale = amax / qmax
    if sr:
        x = (Wg / scale).clamp(-qmax - 0.5, qmax + 0.5)
        fl = torch.floor(x)
        codes = fl + (torch.rand_like(x) < (x - fl)).to(x.dtype)
    else:
        codes = torch.round(Wg / scale).clamp(-qmax, qmax)
    return codes.to(torch.int8), scale.squeeze(-1)


def dequantize(codes, scale, group):
    q = codes.to(torch.float32)                      # (..., n, group)
    return (q * scale.unsqueeze(-1)).reshape(*codes.shape[:-2], codes.shape[-2] * group)


def load_expert(path, idx=0):
    from safetensors import safe_open
    with safe_open(path, framework="pt") as g:
        keys = [k for k in g.keys() if "mlp.experts" in k]
        if not keys:
            return None, None
        k = sorted(keys)[0]
        sl = g.get_slice(k)
        # take expert 0 of the [NE, H, I] batched tensor -> [H, I]
        w = sl[0]
        return k, w.float()


# ---------------- try real weights, else synthetic ----------------
cands = sorted(glob.glob("/data/models/Qwen3.6-35B-A3B/*.safetensors"))
key = None
W = None
for f in cands:
    key, W = load_expert(f)
    if W is not None:
        print(f"loaded REAL expert tensor: {key}  shape={tuple(W.shape)} from {f.split('/')[-1]}", flush=True)
        break
if W is None:
    H, I = 2048, 512
    W = torch.randn(H, I) * 0.02
    print(f"no expert tensor downloaded yet -> SYNTHETIC W {tuple(W.shape)} std={W.std():.4e}", flush=True)

if W.shape[-1] < 256:      # pick a slice with a sensible last dim
    W = W.reshape(-1, W.shape[-1])
W = W.to(dev)
sigma_W = W.std().item()
print(f"  W: {tuple(W.shape)}  std={sigma_W:.4e}  absmax={W.abs().max():.4e}", flush=True)
res["W_shape"] = list(W.shape)
res["sigma_W"] = sigma_W

rms = lambda x: x.pow(2).mean().sqrt().item()

print("\n=== 1. static quantization error (no training, just store/restore) ===", flush=True)
for bits in [8, 4]:
    for group in [32, 64, 128]:
        if W.shape[-1] % group:
            continue
        c, s = quantize(W, bits, group)
        Wq = dequantize(c, s, group)
        err = rms(Wq - W) / sigma_W
        print(f"  int{bits} group{group:3d}: rel RMS err = {err*100:7.3f}%  (bytes/param {bits/8 + 4/group:.3f})", flush=True)
        res[f"static_int{bits}_g{group}"] = err

print("\n=== 2. folding noise: accumulate F steps of Adam-sized updates, fold, repeat ===", flush=True)
# Adam update per step has RMS ~= lr (order of magnitude). Sweep realistic lr for a 35B finetune.
G = W.shape[-1]
x = torch.randn(G, 4096, device=dev)
ref_out = W @ x

for bits, group in [(8, 32), (8, 64), (4, 32), (4, 64)]:
    print(f"\n  --- int{bits} group{group} ---", flush=True)
    for lr in [3e-4, 1e-4, 2e-5]:
        for k in [10, 50, 200]:
            for sr in [False, True]:
                W_ref = W.clone()
                c, s = quantize(W_ref, bits, group, sr)
                W_q = dequantize(c, s, group)
                folds = 20
                for fi in range(folds):
                    dW = torch.randn_like(W_ref) * lr          # rank-r proxy: isotropic small step
                    W_ref += dW
                    target = dequantize(c, s, group) + dW      # fold into the quantized store
                    c, s = quantize(target, bits, group, sr)
                    W_q = dequantize(c, s, group)
                e = rms(W_q - W_ref) / rms(W_ref)
                out_q = W_q @ x
                ferr = rms(out_q - (W_ref @ x)) / rms(W_ref @ x)
                tag = f"int{bits}_g{group}_lr{lr:g}_k{k}_sr{int(sr)}"
                res[tag] = {"weight_rel": e, "func_rel": ferr}
                if k in (50,) and lr in (1e-4,):
                    print(f"    lr={lr:.0e} fold_every={k:4d} SR={int(sr)}: weight err {e*100:6.2f}%  "
                          f"functional err {ferr*100:6.2f}%", flush=True)

# summary table: weight error after 20 folds, fold every 50
print("\n=== summary: functional error after 20 folds, fold every 50 steps, lr=1e-4 ===", flush=True)
for bits in [8, 4]:
    for group in [32, 64]:
        for sr in [0, 1]:
            t = f"int{bits}_g{group}_lr0.0001_k50_sr{sr}"
            if t in res:
                print(f"  int{bits} g{group} SR={sr}: {res[t]['func_rel']*100:6.2f}%", flush=True)

with open("/data/train35b/bench/foldnoise.json", "w") as f:
    json.dump(res, f, indent=1)
print("\nwrote bench/foldnoise.json", flush=True)
