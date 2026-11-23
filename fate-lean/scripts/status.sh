#!/usr/bin/env bash
# Report the local FATE / Mathlib environment: versions, commits, sizes, build state.
# Usage: status.sh [--tsv]
set -uo pipefail

ROOT=${FATE_ROOT:-/data/lean-fate-related}
MATHLIB="$ROOT/mathlib4"
TSV=0
[ "${1:-}" = "--tsv" ] && TSV=1

if [ ! -d "$ROOT" ]; then
  echo "missing: $ROOT" >&2
  exit 1
fi

if [ "$TSV" -eq 0 ]; then
  echo "# FATE 本地环境"
  echo
  echo "root: $ROOT"
  echo "disk: $(df -h "$ROOT" | awk 'NR==2 {print $4" free of "$2" ("$5" used)"}')"
  echo
  printf '%-8s %-10s %-44s %-10s %-8s %s\n' project lean mathlib-rev size oleans status
fi

reported_mathlib=0
for p in FATE-M FATE-H FATE-X; do
  dir="$ROOT/FATE/$p"
  if [ ! -d "$dir" ]; then
    [ "$TSV" -eq 0 ] && printf '%-8s %-10s %-44s %-10s %-8s %s\n' "$p" MISSING - - - -
    continue
  fi
  lean=$(tr -d '\n' < "$dir/lean-toolchain" 2>/dev/null || echo '?')
  rev=$(git -C "$MATHLIB" rev-parse --short=12 HEAD 2>/dev/null || echo '?')
  size=$(du -sh "$dir" 2>/dev/null | cut -f1)
  oleans=$(find "$dir/.lake/build/lib/lean" -name '*.olean' 2>/dev/null | wc -l)
  built=no
  [ "$oleans" -gt 0 ] && built=yes
  if [ "$TSV" -eq 1 ]; then
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$p" "$lean" "$rev" "$size" "$oleans" "$built"
  else
    printf '%-8s %-10s %-44s %-10s %-8s %s\n' "$p" "${lean#leanprover/lean4:}" "$rev" "$size" "$oleans" "$built"
  fi
  reported_mathlib=1
done

if [ "$TSV" -eq 0 ]; then
  echo
  echo "mathlib checkout: $MATHLIB ($(du -sh "$MATHLIB" 2>/dev/null | cut -f1))"
  echo "mathlib oleans:   $(find "$MATHLIB/.lake/build/lib/lean" -name '*.olean' 2>/dev/null | wc -l)"
  echo "ltar cache:       $ROOT/cache/mathlib ($(find "$ROOT/cache/mathlib" -maxdepth 1 -name '*.ltar' 2>/dev/null | wc -l) files, $(du -sh "$ROOT/cache/mathlib" 2>/dev/null | cut -f1))"
  echo "build-all.sh:     $([ -x "$ROOT/build-all.sh" ] && echo executable || echo 'missing/not executable')"
  echo "manifest backups: $(find "$ROOT/FATE" -maxdepth 2 -name 'lake-manifest.json.git-backup' 2>/dev/null | wc -l)/3"
fi

[ "$reported_mathlib" -eq 1 ] || exit 1
