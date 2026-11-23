#!/usr/bin/env bash
# Regenerate the Lean / Mathlib inventory for the lean-mathlib-local-path skill.
# Usage: inventory.sh [--md|--tsv]
#   --md   markdown tables (default)
#   --tsv  tab separated, one row per item
set -uo pipefail

FMT="${1:---md}"
ELAN_ROOT="$(readlink -f "${ELAN_ROOT:-$HOME/.elan}")"
CORPORA=(
  "/data/projects/lean/mathlib"
  "/data/projects/lean-corpus/mathlib4"
)
# Non-Mathlib Lean corpora worth locating (path -> reported in its own table).
LEAN_CORPORA=(
  "~/lean-4.28-reap/formalpedia"
  "/data/axiom-repos/Stacks"
)

# ---------- helpers ----------
lean_ver() {  # $1 = toolchain dir
  "$1/bin/lean" --version 2>/dev/null | sed -E 's/^Lean \(version ([^,]+),.*commit ([0-9a-f]+).*/\1 \2/'
}
short_rev() { git -C "$1" rev-parse --short=8 HEAD 2>/dev/null; }
rev_date()  { git -C "$1" log -1 --format='%ad' --date=short 2>/dev/null; }
tag_of()    { git -C "$1" describe --tags --exact-match 2>/dev/null; }
olean_count() { find "$1/.lake/build/lib/lean" -name '*.olean' 2>/dev/null | wc -l; }
size_of()   { du -sh "$1" 2>/dev/null | cut -f1; }

# ---------- toolchains ----------
toolchains() {
  local t name info ver commit
  for t in "$ELAN_ROOT"/toolchains/*/; do
    [ -x "$t/bin/lean" ] || continue
    name="$(basename "$t")"
    info="$(lean_ver "$t")"
    ver="${info%% *}"; commit="${info##* }"
    printf '%s\t%s\t%s\t%s\n' "$name" "$ver" "$commit" "$(size_of "$t")"
  done
}

# ---------- mathlib checkouts ----------
mathlib_dirs() {
  local d
  for d in "${CORPORA[@]}"; do [ -d "$d" ] && printf '%s\n' "$d"; done
  find "$HOME" -maxdepth 6 -type d \
    \( -path '*/.lake/packages/mathlib' -o -name 'mathlib4-*' \) 2>/dev/null
}

mathlibs() {
  local d tc rev date tag oleans size
  mathlib_dirs | sort -u | while IFS= read -r d; do
    [ -f "$d/lean-toolchain" ] || continue
    tc="$(cat "$d/lean-toolchain" 2>/dev/null | tr -d '\r')"
    rev="$(short_rev "$d")"
    date="$(rev_date "$d")"
    tag="$(tag_of "$d")"
    oleans="$(olean_count "$d")"
    size="$(size_of "$d")"
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$d" "${rev:-—}" "${tag:-—}" "${date:-—}" "${tc:-—}" "${oleans:-0}" "${size:-—}"
  done
}

# ---------- non-Mathlib Lean corpora ----------
lean_corpora() {
  local d
  for d in "${LEAN_CORPORA[@]}"; do
    [ -d "$d" ] || continue
    printf '%s\t%s\t%s\t%s\t%s\n' \
      "$d" "$(short_rev "$d")" "$(rev_date "$d")" \
      "$(find "$d" -name '*.lean' 2>/dev/null | wc -l)" "$(size_of "$d")"
  done
}

# ---------- caches ----------
caches() {
  local c
  for c in "$HOME/.cache/mathlib" "$HOME/.opencode2/cache/mathlib"; do
    [ -d "$c" ] || continue
    printf '%s\t%s\t%s\n' "$c" "$(find "$c" -maxdepth 1 -name '*.ltar' | wc -l)" "$(size_of "$c")"
  done
}

# ---------- output ----------
case "$FMT" in
  --tsv)
    printf 'TOOLCHAINS\n'; toolchains
    printf 'MATHLIB\n';    mathlibs
    printf 'CORPORA\n';    lean_corpora
    printf 'CACHES\n';     caches
    ;;
  *)
    echo "### Toolchains (\`$ELAN_ROOT/toolchains\`)"
    echo
    echo "| dir | lean | commit | size |"
    echo "|---|---|---|---|"
    toolchains | awk -F'\t' '{printf "| `%s` | %s | `%s` | %s |\n",$1,$2,$3,$4}'
    echo
    echo "### Mathlib checkouts"
    echo
    echo "| path | rev | tag | date | lean-toolchain | oleans | size |"
    echo "|---|---|---|---|---|---|---|"
    mathlibs | awk -F'\t' '{printf "| `%s` | `%s` | %s | %s | `%s` | %s | %s |\n",$1,$2,$3,$4,$5,$6,$7}'
    echo
    echo "### Lean corpora (non-Mathlib)"
    echo
    echo "| path | rev | date | .lean files | size |"
    echo "|---|---|---|---|---|"
    lean_corpora | awk -F'\t' '{printf "| `%s` | `%s` | %s | %s | %s |\n",$1,$2,$3,$4,$5}'
    echo
    echo "### Cache dirs"
    echo
    echo "| path | .ltar files | size |"
    echo "|---|---|---|"
    caches | awk -F'\t' '{printf "| `%s` | %s | %s |\n",$1,$2,$3}'
    ;;
esac
