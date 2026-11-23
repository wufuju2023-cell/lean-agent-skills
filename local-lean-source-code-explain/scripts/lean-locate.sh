#!/usr/bin/env bash
# lean-locate.sh — show what is around a given file:line, plus its nearest heading.
#
# usage:
#   lean-locate.sh <file>:<line> [context_lines]
#   lean-locate.sh <file> <line> [context_lines]
#
# examples:
#   scripts/lean-locate.sh ~/lean-4.28-reap/elab-walkthrough/TacticBasic/Ch05.md:88
#   scripts/lean-locate.sh ../Lean-basic/LeanBasic/Ch01.md 120 30
#
# output:
#   FILE   absolute path
#   LINE   requested line
#   HEAD   nearest preceding markdown heading (with its line number)
#   ----   113 | ...   (target line marked with '>')
#
# read-only; never writes to the corpus.

set -uo pipefail

if (($# < 2)); then
  sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
  exit 2
fi

arg1="$1"

if [[ "$arg1" == *:* && "$arg1" != *://* ]]; then
  file="${arg1%:*}"
  line="${arg1##*:}"
  ctx="${2:-12}"
else
  file="$arg1"
  line="$2"
  ctx="${3:-12}"
fi

[[ -f "$file" ]] || { echo "error: no such file: $file" >&2; exit 3; }
[[ "$line" =~ ^[0-9]+$ ]] || { echo "error: line is not a number: $line" >&2; exit 3; }
[[ "$ctx" =~ ^[0-9]+$ ]] || { echo "error: context is not a number: $ctx" >&2; exit 3; }

abs=$(readlink -f -- "$file")
total=$(wc -l < "$abs")
start=$(( line - ctx )); ((start < 1)) && start=1
end=$(( line + ctx ));   ((end > total)) && end=$total

head_line=$(awk -v L="$line" '
  NR <= L && /^#{1,6} / { n = NR; t = $0 }
  END { if (n) printf "%d\t%s\n", n, t }
' "$abs")

printf 'FILE  %s\n' "$abs"
printf 'LINE  %s (file has %s lines)\n' "$line" "$total"
if [[ -n "$head_line" ]]; then
  hl="${head_line%%$'\t'*}"
  ht="${head_line#*$'\t'}"
  printf 'HEAD  %s  (line %s)\n' "$ht" "$hl"
else
  printf 'HEAD  (no markdown heading before this line)\n'
fi
printf -- '----\n'

awk -v s="$start" -v e="$end" -v t="$line" '
  NR >= s && NR <= e {
    mark = (NR == t) ? ">" : " "
    printf "%s %5d | %s\n", mark, NR, $0
  }
' "$abs"
