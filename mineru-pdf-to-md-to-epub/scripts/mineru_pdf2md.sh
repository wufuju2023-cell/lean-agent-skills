#!/usr/bin/env bash
# MinerU PDF -> Markdown backfill for the math-ai-base-data library.
#
# Runs locally on this Linux machine. The library is normally mounted at
# /data/projects/math-ai-base-data.
#
# Usage:
#   mineru_pdf2md.sh "<rel-pdf-path-under-hot_papers>" [more paths...]
# Example:
#   mineru_pdf2md.sh "2026.3.16ai/Mastering Atari Games with Limited Data.pdf"
#
# Env overrides:
#   MINERU_ROOT   (default /data/projects/math-ai-base-data)
#   MINERU_CONFIG (default config/hot_paper_epub.json)
set -euo pipefail

ROOT="${MINERU_ROOT:-/data/projects/math-ai-base-data}"
CONFIG="${MINERU_CONFIG:-config/hot_paper_epub.json}"

if [ "$#" -lt 1 ]; then
  echo "usage: mineru_pdf2md.sh <relative-pdf-path-under-hot_papers> [more...]" >&2
  exit 2
fi

if [ ! -d "$ROOT" ]; then
  echo "ERR: MinerU root not found: $ROOT" >&2
  echo "Mount the data disk or set MINERU_ROOT." >&2
  exit 2
fi

cd "$ROOT"

# Token: first 20+ char token-like string in the token file (never echoed).
TOK="$(grep -oE '[A-Za-z0-9._-]{20,}' minerU-api-token.md 2>/dev/null | head -1 || true)"
if [ -z "$TOK" ]; then
  echo "ERR: no token found in $PWD/minerU-api-token.md" >&2
  exit 2
fi
export MINERU_API_TOKEN="$TOK"

PY=./.venv-linux/bin/python
if [ ! -x "$PY" ]; then
  echo "ERR: .venv-linux missing. Create it once:" >&2
  echo "  python3 -m venv .venv-linux && .venv-linux/bin/pip install requests pymupdf" >&2
  exit 2
fi

if [ ! -w "$ROOT" ]; then
  echo "WARN: $ROOT is not writable. The pipeline will fail when it writes output." >&2
  echo "      If NTFS is dirty, run chkdsk /f on Windows, then mount read-write." >&2
fi

args=()
for p in "$@"; do
  args+=(--pdf-path "$p")
done

exec "$PY" hot_paper_md_backfill.py --config "$CONFIG" "${args[@]}"
