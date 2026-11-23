#!/usr/bin/env bash
# lean-search.sh — search the six local Lean corpora with consistent excludes.
#
# usage:
#   lean-search.sh [options] <pattern> [extra rg args...]
#
# options:
#   -l, --files       list matching files with hit counts instead of lines
#   -F, --fixed       treat <pattern> as a literal string (no regex)
#       --md          only *.md   (讲义)
#       --lean        only *.lean (实验/笔记)
#       --with-out    include **/out/** (真实输出)
#       --with-fp-mp  include LmcStudy/FP-MP-source (书仓库, 2GB)
#       --root N      only root N (1..6); repeatable, e.g. --root 3 --root 4
#       --max N       max hits per file (default 3)
#   -h, --help        this help
#
# roots:
#   1 ~/lean-4.28-reap/runtime/LmcStudy
#   2 ~/Lean-source-code-learning-to-know-reap
#   3 ~/lean-4.28-reap/command-walkthrough
#   4 ~/lean-4.28-reap/elab-walkthrough
#   5 ~/lean-4.28-reap/Lean-basic
#   6 ~/lean-4.28-reap/Lean-math-formalization/leinster-n-cat/lean

set -uo pipefail

LMC=~/lean-4.28-reap/runtime/LmcStudy
LL=~/Lean-source-code-learning-to-know-reap
CMD=~/lean-4.28-reap/command-walkthrough
ELAB=~/lean-4.28-reap/elab-walkthrough
BASIC=~/lean-4.28-reap/Lean-basic
MATH=~/lean-4.28-reap/Lean-math-formalization/leinster-n-cat/lean

mode=content
include=""
with_out=0
with_fp_mp=0
fixed=0
max_per_file=3
roots=()

while (($#)); do
  case "$1" in
    -l|--files)   mode=files; shift ;;
    -F|--fixed)   fixed=1; shift ;;
    --md)         include='*.md'; shift ;;
    --lean)       include='*.lean'; shift ;;
    --with-out)   with_out=1; shift ;;
    --with-fp-mp) with_fp_mp=1; shift ;;
    --max)        max_per_file="$2"; shift 2 ;;
    --root)       roots+=("$2"); shift 2 ;;
    -h|--help)    sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    --)           shift; break ;;
    -*)           echo "unknown option: $1" >&2; exit 2 ;;
    *)            break ;;
  esac
done

if (($# == 0)); then
  echo "error: missing <pattern>" >&2
  echo "try: $0 --help" >&2
  exit 2
fi

pattern="$1"; shift

if ! command -v rg >/dev/null 2>&1; then
  echo "error: ripgrep (rg) not found" >&2
  exit 3
fi

glob_args=(
  --glob '!.lake/**'
  --glob '!_out/**'
  --glob '!**/__pycache__/**'
  --glob '!**/node_modules/**'
  --glob '!**/.git/**'
)
((with_out)) || glob_args+=(--glob '!**/out/**')

rg_args=(-n --no-heading --color never --with-filename --max-count "$max_per_file" "${glob_args[@]}")
((fixed)) && rg_args+=(-F)

wanted() {
  local n="$1"
  ((${#roots[@]} == 0)) && return 0
  local r
  for r in "${roots[@]}"; do [[ "$r" == "$n" ]] && return 0; done
  return 1
}

search_one() {
  local root="$1" label="$2"
  shift 2
  local targets=("$@")
  local -a existing=()
  local t
  for t in "${targets[@]}"; do [[ -e "$t" ]] && existing+=("$t"); done
  ((${#existing[@]})) || return 0

  local out
  local -a fixed_arg=()
  ((fixed)) && fixed_arg=(-F)
  if [[ "$mode" == files ]]; then
    out=$(rg -c --color never "${glob_args[@]}" "${fixed_arg[@]}" -e "$pattern" "${existing[@]}" 2>/dev/null)
  else
    out=$(rg "${rg_args[@]}" -e "$pattern" "${existing[@]}" 2>/dev/null)
  fi
  # --md / --lean: explicit file args bypass rg globs, so filter the result lines.
  if [[ -n "$out" && -n "$include" ]]; then
    out=$(printf '%s\n' "$out" | awk -F: -v e="${include#\*.}" \
      'substr($1, length($1) - length(e)) == "." e')
  fi
  if [[ -n "$out" ]]; then
    printf '### %s\n' "$label"
    printf '%s\n' "$out"
    printf '\n'
  fi
}

if wanted 1; then
  if ((with_fp_mp)); then
    search_one "$LMC" "[1] LmcStudy (full, incl. FP-MP-source)" "$LMC"
  else
    search_one "$LMC" "[1] LmcStudy (Notes / Experiments / preamble)" \
      "$LMC/Notes" "$LMC/Experiments" "$LMC/Notes.lean" \
      "$LMC/LmcPreamble.lean" "$LMC/Scratch.lean" "$LMC/README.md" \
      "$LMC/Functional-programming-in-lean"
  fi
fi

wanted 2 && search_one "$LL"    "[2] LL-01..LL-12 (Lean internals)" "$LL"
wanted 3 && search_one "$CMD"   "[3] command-walkthrough (Command.lean)" "$CMD"
wanted 4 && search_one "$ELAB"  "[4] elab-walkthrough (Elab/ 20 files)" "$ELAB"
wanted 5 && search_one "$BASIC" "[5] Lean-basic (List/String/Array)" "$BASIC"
wanted 6 && search_one "$MATH"  "[6] leinster-n-cat (strict n-category)" \
  "$MATH/StrictNCategory" "$MATH/Tests" "$MATH/explain" \
  "$MATH/README.md" "$MATH/ARCHITECTURE.md" "$MATH/SPEC.md" "$MATH/TASKS.md" \
  "$MATH/SNL/README.md" "$MATH/SNL/Generator.lean" \
  "$MATH/SNL/MathlibPilot.lean" "$MATH/SNL/ImportGraphPilot.lean"

exit 0
