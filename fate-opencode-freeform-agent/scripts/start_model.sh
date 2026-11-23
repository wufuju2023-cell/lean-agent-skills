#!/usr/bin/env bash
# start_model.sh [SIZE|DIR] — 起一个本地 vLLM 实例给 OpenCode 用
#   SIZE: 0.8B | 4B | 9B-AWQ | 或直接给模型目录
#   env:  PORT(8001) UTIL CTX(65536) NAME MAXSEQ
# 只杀本端口的实例，不影响其它端口。
set -uo pipefail

ARG=${1:-0.8B}
case "$ARG" in
  0.8B)   DIR=${DIR:-/data/models/Qwen3.5-0.8B};      NAME=${NAME:-qwen3.5-0.8b}; UTIL=${UTIL:-0.22} ;;
  4B)     DIR=${DIR:-/data/models/Qwen3.5-4B};        NAME=${NAME:-qwen3.5-4b};   UTIL=${UTIL:-0.60} ;;
  9B-AWQ) DIR=${DIR:-/data/models/Qwen3.5-9B-AWQ-4bit}; NAME=${NAME:-qwen3.5-9b}; UTIL=${UTIL:-0.92} ;;
  *)      DIR=$ARG; NAME=${NAME:-$(basename "$DIR" | tr 'A-Z' 'a-z')}; UTIL=${UTIL:-0.60} ;;
esac
PORT=${PORT:-8001}
CTX=${CTX:-65536}
MAXSEQ=${MAXSEQ:-16}

[ -d "$DIR" ] || { echo "model dir not found: $DIR" >&2; exit 1; }

# 只杀监听该端口的进程
pid=$(ss -ltnp 2>/dev/null | awk -v p=":$PORT" '$4 ~ p' | grep -oE 'pid=[0-9]+' | head -1 | cut -d= -f2 || true)
[ -n "${pid:-}" ] && { echo "killing pid $pid on :$PORT"; kill "$pid" 2>/dev/null || true; sleep 3; }

source /data/qwen35-9b-throughput/env.sh >/dev/null 2>&1

setsid nohup vllm serve "$DIR" \
  --served-model-name "$NAME" \
  --max-model-len "$CTX" --gpu-memory-utilization "$UTIL" \
  --max-num-seqs "$MAXSEQ" --kv-cache-dtype int8_per_token_head \
  --enable-prefix-caching --enable-chunked-prefill --language-model-only \
  --reasoning-parser qwen3 \
  --enable-auto-tool-choice --tool-call-parser qwen3_xml \
  --default-chat-template-kwargs '{"enable_thinking": false}' \
  --speculative-config '{"method":"mtp","num_speculative_tokens":2}' \
  --host 127.0.0.1 --port "$PORT" \
  > /data/WSP/logs/serve_${PORT}.log 2>&1 < /dev/null &
disown

for i in $(seq 1 60); do
  curl -s -m 2 "http://127.0.0.1:${PORT}/v1/models" >/dev/null \
    && { echo "ready :$PORT  $NAME  <- $DIR"; exit 0; }
  sleep 3
done
echo "TIMEOUT; tail of log:" >&2
tail -30 /data/WSP/logs/serve_${PORT}.log >&2
exit 1
