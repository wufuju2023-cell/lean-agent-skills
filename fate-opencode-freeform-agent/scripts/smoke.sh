#!/usr/bin/env bash
# smoke.sh — 三层自检：vLLM + tool parser + Lean 项目
# env: PORT(8001) MODEL(qwen3.5-0.8b) PROJ(/data/WSP/lean/proj) OPENCODE_PROBE=1
set -uo pipefail
PORT=${PORT:-8001}
MODEL=${MODEL:-qwen3.5-0.8b}
PROJ=${PROJ:-/data/WSP/lean/proj}
BASE="http://127.0.0.1:${PORT}/v1"
fail=0

echo "== 1. vLLM =="
if curl -s -m 3 "$BASE/models" | grep -q "$MODEL"; then
  echo "  ok: $MODEL"
else
  echo "  FAIL: $MODEL not served on :$PORT"; fail=1
fi

echo "== 2. tool parser (critical) =="
python3 - "$BASE" "$MODEL" <<'PY' || fail=1
import json, sys, urllib.request
base, model = sys.argv[1], sys.argv[2]
tools=[{"type":"function","function":{"name":"write_file","description":"write",
  "parameters":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},
  "required":["path","content"]}}}]
p={"model":model,"messages":[{"role":"user","content":"Use write_file to write 42 to a.txt"}],
   "tools":tools,"tool_choice":"auto","temperature":0,"max_tokens":128,
   "chat_template_kwargs":{"enable_thinking":False}}
r=urllib.request.Request(base+"/chat/completions",data=json.dumps(p).encode(),
                         headers={"Content-Type":"application/json"})
d=json.loads(urllib.request.urlopen(r,timeout=120).read())
tc=d["choices"][0]["message"].get("tool_calls")
if tc:
    print("  ok: tool_calls ->", tc[0]["function"]["name"])
else:
    print("  FAIL: tool_calls is null  (wrong --tool-call-parser? use qwen3_xml)")
    print("  raw content:", repr((d["choices"][0]["message"].get("content") or "")[:200]))
    sys.exit(1)
PY

echo "== 3. Lean project =="
if [ -f "$PROJ/lean-toolchain" ]; then
  out=$(cd "$PROJ" && PATH=$HOME/.elan/bin:$PATH MATHLIB_CACHE_DIR=/data/lean-fate-related/cache/mathlib \
        lake env lean Wsplean/Basic.lean 2>&1)
  if [ -z "$out" ]; then echo "  ok: $PROJ compiles"; else echo "  FAIL:"; echo "$out" | head -5; fail=1; fi
else
  echo "  FAIL: no lean-toolchain in $PROJ"; fail=1
fi

if [ "${OPENCODE_PROBE:-0}" = "1" ] && [ -d "$PROJ" ]; then
  echo "== 4. OpenCode free-form probe (m001) =="
  cd "$PROJ"
  out=$(env PWD=$PWD ~/.opencode2/bin/opencode run --standalone --auto \
        --agent leanwsp --model local08b/qwen3.5-0.8b --format json \
        "Call lean-goal on tasks/m001/Problem.lean line 9 and print the goal." 2>&1 | head -40)
  echo "$out" | grep -q 'lean-goal' && echo "  ok: model called lean-goal" || { echo "  FAIL: no lean-goal call"; fail=1; }
fi

echo
[ "$fail" = "0" ] && echo "SMOKE OK" || echo "SMOKE FAILED"
exit "$fail"
