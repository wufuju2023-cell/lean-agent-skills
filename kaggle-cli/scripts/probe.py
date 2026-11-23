import subprocess


def run(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return (r.stdout or "") + (r.stderr or "")


print("=== nvidia-smi ===")
print(run("nvidia-smi"))

print("=== torch ===")
try:
    import torch

    print("torch:", torch.__version__)
    print("cuda:", torch.cuda.is_available(), "| devices:", torch.cuda.device_count())
    for i in range(torch.cuda.device_count()):
        p = torch.cuda.get_device_properties(i)
        print(f"gpu{i}: {torch.cuda.get_device_name(i)} | {p.total_memory / 1e9:.1f} GB | cc {p.major}.{p.minor}")
except Exception as e:
    print("torch check failed:", repr(e))

print("=== cpu / ram ===")
print(run("nproc; free -g | head -2"))

print("=== disks ===")
print(run("df -h /kaggle/working /kaggle/input /dev/shm /tmp 2>&1"))

print("=== mounts ===")
print(run("mount | grep -E 'kaggle|overlay|tmpfs|gcsfuse' | head -15"))

print("=== env ===")
import os

print("KAGGLE_USERNAME:", os.getenv("KAGGLE_USERNAME"))
print("KAGGLE_KEY set:", bool(os.getenv("KAGGLE_KEY")))
print("internet check:", run("curl -s -o /dev/null -w '%{http_code}' --max-time 10 https://huggingface.co"))
