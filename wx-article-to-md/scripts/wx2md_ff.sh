#!/usr/bin/env bash
# wx2md_ff.sh — WeChat article -> Markdown via real Firefox + WebDriver BiDi.
# Same pandoc/postprocess pipeline as wx-article-to-md, but fetches through the
# agentgui Firefox (bypasses WeChat's headless-Chromium verification page).
# Usage: wx2md_ff.sh <url> <output.md>
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL="$HOME/.config/opencode/skills/wx-article-to-md/scripts"
URL="${1:?usage: wx2md_ff.sh <url> <out.md>}"
OUT="${2:?usage: wx2md_ff.sh <url> <out.md>}"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/wx2mdff.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$(dirname "$OUT")"

python3 "$HERE/fetch_firefox.py" "$URL" "$TMP/content.html" "$TMP/meta.json" > "$TMP/fetch.log" 2>&1 || {
  cat "$TMP/fetch.log" >&2; exit 3;
}

pandoc -f html -t markdown --wrap=none --lua-filter="$SKILL/unwrap.lua" "$TMP/content.html" -o "$TMP/raw.md"
python3 "$SKILL/postprocess.py" "$TMP/raw.md" "$TMP/meta.json" "$OUT"
python3 "$HERE/formula_fix.py" "$OUT" "$TMP/meta.json.formulas.json"

python3 - "$OUT" <<'PY'
import subprocess, sys
path = sys.argv[1]
md = open(path, encoding='utf-8').read()
html = subprocess.run(['pandoc', '-f', 'markdown', '-t', 'html', '--mathjax', path],
                      capture_output=True, text=True).stdout
inline = html.count('math inline'); display = html.count('math display')
bad = md.count(']{.math')
import re
print(f'OK {path}')
print(f'lines={md.count(chr(10))} chars={len(md)} formulas: {inline} inline / {display} display' + ('  [WARN: fallback blocks present]' if bad else ''))
PY
