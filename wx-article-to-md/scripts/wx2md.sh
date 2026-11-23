#!/usr/bin/env bash
# wx2md.sh — 微信公众号文章 → Markdown（公式还原为 LaTeX 源码）
# Usage: wx2md.sh <mp.weixin.qq.com article url> [output.md]
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

URL="${1:-}"
OUT="${2:-}"
if [[ -z "$URL" ]]; then
  echo "Usage: $0 <mp.weixin.qq.com article url> [output.md]" >&2
  exit 2
fi
for bin in node pandoc python3; do
  command -v "$bin" >/dev/null 2>&1 || { echo "ERROR: missing $bin" >&2; exit 1; }
done

TMP="$(mktemp -d "${TMPDIR:-/tmp}/wx2md.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

echo "[1/4] headless fetch + formula rebuild ..."
node "$DIR/fetch_page.js" "$URL" "$TMP/content.html" "$TMP/meta.json"

TITLE="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1],encoding="utf-8")).get("title",""))' "$TMP/meta.json")"
if [[ -z "$OUT" ]]; then
  SAFE="$(TITLE="$TITLE" python3 -c 'import os,re;t=os.environ.get("TITLE","").strip();t=re.sub(r"[/\\:*?\"<>|\n\r\t]+","_",t)[:120];print(t or "wechat-article")')"
  OUT="$(pwd)/$SAFE.md"
fi
mkdir -p "$(dirname "$OUT")"

echo "[2/4] pandoc -> markdown ..."
pandoc -f html -t markdown --wrap=none --lua-filter="$DIR/unwrap.lua" "$TMP/content.html" -o "$TMP/raw.md"

echo "[3/4] postprocess + frontmatter ..."
python3 "$DIR/postprocess.py" "$TMP/raw.md" "$TMP/meta.json" "$OUT"

echo "[4/4] verify ..."
python3 - "$OUT" <<'PY'
import subprocess, sys
path = sys.argv[1]
md = open(path, encoding='utf-8').read()
html = subprocess.run(['pandoc', '-f', 'markdown', '-t', 'html', '--mathjax', path],
                      capture_output=True, text=True).stdout
inline = html.count('math inline')
display = html.count('math display')
bad = md.count(']{.math')
print(f'OK {path}')
print(f'formulas: {inline} inline / {display} display' + ('  [WARN: fallback blocks present]' if bad else ''))
PY
