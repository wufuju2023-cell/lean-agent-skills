#!/usr/bin/env bash
# Markdown -> EPUB for the math-ai-base-data library.
#
# Runs locally on this Linux machine. The library is normally mounted at
# /data/projects/math-ai-base-data.
#
# Usage:
#   md2epub.sh "<rel-md-path-under-hot-paper-md>" [more .md paths...]
# Example:
#   md2epub.sh "2026.3.16ai/Mastering Atari Games with Limited Data.md"
#
# Env overrides:
#   MINERU_ROOT (default /data/projects/math-ai-base-data)
#   PANDOC_PATH (default: pandoc from PATH)
set -euo pipefail

ROOT="${MINERU_ROOT:-/data/projects/math-ai-base-data}"
PANDOC_PATH="${PANDOC_PATH:-pandoc}"

if [ "$#" -lt 1 ]; then
  echo "usage: md2epub.sh <relative-md-path-under-hot-paper-md> [more...]" >&2
  exit 2
fi

if [ ! -d "$ROOT" ]; then
  echo "ERR: MinerU root not found: $ROOT" >&2
  echo "Mount the data disk or set MINERU_ROOT." >&2
  exit 2
fi

cd "$ROOT"

if ! command -v "$PANDOC_PATH" >/dev/null 2>&1; then
  echo "ERR: pandoc not found. Install it: sudo apt-get install -y pandoc" >&2
  exit 2
fi

PY=./.venv-linux/bin/python
if [ ! -x "$PY" ]; then
  echo "ERR: .venv-linux missing (see mineru_pdf2md.sh header)." >&2
  exit 2
fi

if [ ! -w "$ROOT" ]; then
  echo "WARN: $ROOT is not writable. EPUB output will fail." >&2
  echo "      If NTFS is dirty, run chkdsk /f on Windows, then mount read-write." >&2
fi

args=()
for m in "$@"; do
  args+=(--md-path "$m")
done

exec "$PY" scripts/convert_d_hot_paper_md_to_epub.py \
  --source-root "$ROOT/hot-paper-md" \
  --output-root "$ROOT/hot-paper-epub" \
  --cache-root "$ROOT/cache/hot_paper_epub/md_to_epub" \
  --state-path "$ROOT/cache/hot_paper_epub/md_to_epub/d_state.json" \
  --lock-path "$ROOT/cache/hot_paper_epub/md_to_epub/d.lock" \
  --log-path "$ROOT/logs/md_to_epub.log" \
  --pandoc-executable "$(command -v "$PANDOC_PATH")" \
  "${args[@]}"
