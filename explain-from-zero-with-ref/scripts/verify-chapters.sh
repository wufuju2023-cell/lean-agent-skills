#!/usr/bin/env bash
# verify-chapters.sh — compile every Ch*.lean, save real output, run static checks.
#
# usage:
#   verify-chapters.sh <project-dir>
#
# does:
#   1. reads lean-toolchain -> picks the matching elan toolchain's lake
#   2. compiles every Ch*.lean with `lake env lean`, saves stdout+stderr to out/<name>.txt
#   3. checks markdown code fences are balanced
#   4. warns about `sorry`/`admit` in chapter experiments
#   5. warns about a .lean without a sibling .md (and vice versa)
#
# exit: 0 = all compiled + no blocking issue, 1 = at least one failure
# writes only inside <project-dir>/out/.

set -uo pipefail

if (($# < 1)); then
  sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'
  exit 2
fi

proj="$1"
[[ -d "$proj" ]] || { echo "error: no such directory: $proj" >&2; exit 2; }
proj=$(readlink -f -- "$proj")
cd "$proj" || exit 2

ver=""
if [[ -f lean-toolchain ]]; then
  ver=$(sed -n 's/^[[:space:]]*leanprover\/lean4://p' lean-toolchain | head -1)
fi

lake=""
if [[ -n "$ver" ]]; then
  tc="~/lean-4.28-reap/elan/toolchains/leanprover--lean4---$ver"
  [[ -x "$tc/bin/lake" ]] && lake="$tc/bin/lake"
fi
[[ -z "$lake" ]] && lake=$(command -v lake 2>/dev/null || true)
[[ -n "$lake" ]] || { echo "error: lake not found (lean-toolchain: ${ver:-missing})" >&2; exit 3; }

echo "project : $proj"
echo "lean    : ${ver:-<no lean-toolchain>}"
echo "lake    : $lake"
echo

mkdir -p out

pass=0
fail=0

printf '%-44s %-6s %s\n' "FILE" "EXIT" "OUT"
printf '%-44s %-6s %s\n' "--------------------------------------------" "------" "--------------------------------"

while IFS= read -r rel; do
  name=$(basename "$rel" .lean)
  out="out/$name.txt"
  if "$lake" env lean "$rel" > "$out" 2>&1; then
    rc=0
    pass=$((pass + 1))
  else
    rc=$?
    fail=$((fail + 1))
  fi
  printf '%-44s %-6s %s\n' "$rel" "$rc" "$out"
done < <(find . -path ./.lake -prune -o -name 'Ch*.lean' -print | sed 's|^\./||' | sort)

echo
echo "== static checks =="

md_bad=0
while IFS= read -r md; do
  c=$(grep -c '^```' "$md" || true)
  if ((c % 2 != 0)); then
    echo "[FAIL] unbalanced code fences ($c): $md"
    md_bad=$((md_bad + 1))
  fi
done < <(find . -path ./.lake -prune -o -name '*.md' -print | sed 's|^\./||' | sort)
((md_bad == 0)) && echo "[OK]   markdown fences balanced"

if find . -path ./.lake -prune -o -name 'Ch*.lean' -print0 |
   xargs -0 grep -nE '\b(sorry|admit)\b' 2>/dev/null; then
  echo "[WARN] sorry/admit found in the lines above (comments count too)"
else
  echo "[OK]   no sorry/admit in chapter experiments"
fi

missing_md=0
while IFS= read -r lean; do
  dir=$(dirname "$lean")
  base=$(basename "$lean")
  prefix=$(printf '%s' "$base" | grep -oE '^Ch[0-9]+')
  [[ -n "$prefix" ]] || continue
  [[ -f "$dir/$prefix.md" ]] || { echo "[WARN] no lecture file: $dir/$prefix.md"; missing_md=$((missing_md + 1)); }
done < <(find . -path ./.lake -prune -o -name 'Ch*.lean' -print | sed 's|^\./||' | sort)

missing_lean=0
while IFS= read -r md; do
  dir=$(dirname "$md")
  base=$(basename "$md")
  prefix=$(printf '%s' "$base" | grep -oE '^Ch[0-9]+')
  [[ -n "$prefix" ]] || continue
  if ! compgen -G "$dir/${prefix}_*.lean" >/dev/null && [[ ! -f "$dir/$prefix.lean" ]]; then
    echo "[WARN] no experiment file: $dir/${prefix}_*.lean"
    missing_lean=$((missing_lean + 1))
  fi
done < <(find . -path ./.lake -prune -o -name 'Ch*.md' -print | sed 's|^\./||' | sort)

echo
echo "---"
echo "compiled: $pass pass, $fail fail; md issues: $md_bad; missing .md: $missing_md; missing .lean: $missing_lean"
((fail == 0 && md_bad == 0))
