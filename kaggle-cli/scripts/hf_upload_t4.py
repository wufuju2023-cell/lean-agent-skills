"""Upload speed test: Kaggle T4 -> HuggingFace.

Requires the HF_TOKEN Kaggle Secret to be ATTACHED to this notebook
(Add-ons -> Secrets -> toggle on), then Save Version -> Save & Run All.

Prints MB/s and writes /kaggle/working/hf_upload_result.json.
"""

import json
import os
import subprocess
import time

REPO = "YOUR_USERNAME/kaggle-speedtest-t4"
SIZE_MB = 256


def sh(cmd, timeout=900):
    t0 = time.time()
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    return (r.stdout or "") + (r.stderr or ""), time.time() - t0


print("gpu:", sh("nvidia-smi -L")[0])

token = os.getenv("HF_TOKEN")
source = "env"
if not token:
    from kaggle_secrets import UserSecretsClient

    token = UserSecretsClient().get_secret("HF_TOKEN")
    source = "kaggle_secret"

cache = os.path.expanduser("~/.cache/huggingface")
os.makedirs(cache, exist_ok=True)
p = os.path.join(cache, "token")
with open(p, "w") as f:
    f.write(token)
os.chmod(p, 0o600)
os.environ["HF_TOKEN"] = token

print("token source:", source, "| length:", len(token))
print(sh("hf auth whoami")[0])

path = "/tmp/hfup.bin"
sh(f"head -c {SIZE_MB * 1024 * 1024} /dev/urandom > {path}")

out, dt = sh(
    f"hf upload {REPO} {path} blob.bin --type model --private "
    "--commit-message 'T4 upload speed test'"
)
print(out[-400:])

size = os.path.getsize(path)
res = {
    "gpu": sh("nvidia-smi --query-gpu=name --format=csv,noheader")[0].strip().splitlines(),
    "bytes": size,
    "seconds": round(dt, 2),
    "mbps": round(size / dt / 1e6, 2),
    "token_source": source,
}
print(json.dumps(res, indent=2))
with open("/kaggle/working/hf_upload_result.json", "w") as f:
    json.dump(res, f, indent=2)
