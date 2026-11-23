"""Kaggle T4 instance transfer benchmark.

Run inside a GPU kernel with internet enabled and a dataset attached
(edit DATASET_SLUG below, or leave empty to skip the dataset-read test).

Writes /kaggle/working/speedtest_results.json.
"""

import json
import os
import subprocess
import time

DATASET_SLUG = ""  # e.g. "fujuwu/kaggle-speedtest-data"
RESULTS = {}


def sh(cmd, timeout=600):
    t0 = time.time()
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or ""), time.time() - t0
    except subprocess.TimeoutExpired:
        return 124, "timeout", time.time() - t0


print("=== disks ===")
print(sh("df -h /kaggle/working /dev/shm /tmp 2>&1")[1])

print("=== local fs 1 GiB ===")
for path in ["/kaggle/working", "/tmp", "/dev/shm"]:
    if not os.path.isdir(path):
        continue
    fn = os.path.join(path, "bench.bin")
    rc, _, dt = sh(f"dd if=/dev/zero of={fn} bs=1M count=1024 conv=fdatasync status=none", 300)
    w = 1024 / dt if rc == 0 else 0
    rc2, _, dt2 = sh(f"dd if={fn} of=/dev/null bs=1M iflag=direct status=none", 300)
    if rc2 != 0:
        rc2, _, dt2 = sh(f"dd if={fn} of=/dev/null bs=1M status=none", 300)
    r = 1024 / dt2 if rc2 == 0 else 0
    RESULTS[f"disk_{path}"] = {"write_mbps": round(w, 2), "read_mbps": round(r, 2)}
    print(f"{path}: write {w:.1f} MB/s | read {r:.1f} MB/s")
    os.remove(fn)

if DATASET_SLUG:
    print("=== kaggle dataset read ===")
    cands = []
    for root, _, files in os.walk("/kaggle/input"):
        for f in files:
            p = os.path.join(root, f)
            cands.append((os.path.getsize(p), p))
    if cands:
        size, path = max(cands)
        rc, _, dt = sh(f"dd if='{path}' of=/dev/null bs=1M iflag=direct status=none", 300)
        if rc != 0:
            rc, _, dt = sh(f"dd if='{path}' of=/dev/null bs=1M status=none", 300)
        print(path, "->", f"{size / dt / 1e6:.1f} MB/s")
        RESULTS["kaggle_dataset_read_mbps"] = round(size / dt / 1e6, 2)

print("=== network ===")
urls = {
    "github": "https://github.com/torvalds/linux/archive/refs/heads/master.tar.gz",
    "huggingface": "https://huggingface.co/openai-community/gpt2/resolve/main/pytorch_model.bin",
}
for name, url in urls.items():
    out = f"/tmp/{name}.bin"
    rc, res, _ = sh(
        f"curl -sL --max-time 240 -o {out} -w '%{{http_code}} %{{size_download}} %{{speed_download}}' '{url}'",
        300,
    )
    print(name, res)
    parts = res.split()
    if len(parts) >= 3 and parts[0] == "200":
        RESULTS[name] = {"bytes": int(parts[1]), "mbps": round(int(parts[2]) / 1e6, 2)}
    try:
        os.remove(out)
    except OSError:
        pass

with open("/kaggle/working/speedtest_results.json", "w") as f:
    json.dump(RESULTS, f, indent=2)
print(json.dumps(RESULTS, indent=2))
