#!/usr/bin/env bash
# check-refs.sh — validate absolute `path:line` citations in markdown files.
#
# usage:
#   check-refs.sh <file-or-dir> [more...]
#
# checks:
#   1. every `/.../*.lean:NNN` or `/.../*.md:NNN` citation points to a real file
#   2. the line number is within 1..<line count>
#   3. blockquote citations (`> ...`) do not use relative paths
#
# exit: 0 = all good, 1 = at least one problem, 2 = bad usage
# read-only.

set -uo pipefail

if (($# < 1)); then
  sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'
  exit 2
fi

files=()
for a in "$@"; do
  if [[ -d "$a" ]]; then
    while IFS= read -r f; do files+=("$f"); done < <(
      find "$a" -name '*.md' \
        -not -path '*/.lake/*' -not -path '*/_out/*' \
        -not -path '*/node_modules/*' -not -path '*/out/*' | sort
    )
  elif [[ -f "$a" ]]; then
    files+=("$a")
  else
    echo "warning: not found: $a" >&2
  fi
done

total=0
bad=0
relative=0

for f in "${files[@]}"; do
  while IFS= read -r ref; do
    [[ -z "$ref" ]] && continue
    total=$((total + 1))
    path="${ref%:*}"
    line="${ref##*:}"
    if [[ ! -f "$path" ]]; then
      echo "[FAIL] $f -> $ref (file missing)"
      bad=$((bad + 1))
      continue
    fi
    n=$(awk 'END { print NR }' "$path")
    if ((line < 1 || line > n)); then
      echo "[FAIL] $f -> $ref (file has $n lines)"
      bad=$((bad + 1))
    fi
  done < <(grep -oE '/home/[A-Za-z0-9_./+-]+\.(lean|md):[0-9]+' "$f" | sort -u)

  # relative citations inside blockquotes: `> Ch05.md:12`, `> ../x.lean:3`
  while IFS= read -r ln; do
    [[ -z "$ln" ]] && continue
    echo "[FAIL] $f:$ln (relative path in blockquote citation)"
    relative=$((relative + 1))
  done < <(grep -nE '^> +[^/[:space:]].*\.(lean|md):[0-9]+' "$f" | cut -d: -f1)
done

echo "---"
echo "files: ${#files[@]}  refs: $total  broken: $bad  relative: $relative"
((bad + relative == 0))
