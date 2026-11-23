#!/usr/bin/env bash
# Check MinerU API tokens in the math-ai-base-data library and optionally
# delete expired ones.
#
# A token is "expired" when POST /api/v4/file-urls/batch returns HTTP 401 with
# msgCode A0202 (user authenticate failed). The probe only asks for upload URLs
# for a fake file; nothing is uploaded, no quota is consumed.
#
# Usage:
#   mineru_token_check.sh            # report status of minerU-api-token*.md
#   mineru_token_check.sh --delete-expired   # additionally remove expired files
#   mineru_token_check.sh --refresh-from-local-cache
#                                     # write the local cached token into
#                                     # minerU-api-token.md
#
# Env overrides: MINERU_ROOT (default /data/projects/math-ai-base-data),
#                TOKEN_GET (default <secret-store>/get-secret.sh).
set -euo pipefail

ROOT="${MINERU_ROOT:-/data/projects/math-ai-base-data}"
TOKEN_GET="${TOKEN_GET:-}"
MODE="${1:-check}"

case "$MODE" in
  check) DELETE=0; REFRESH=0 ;;
  --delete-expired) DELETE=1; REFRESH=0 ;;
  --refresh-from-local-cache) DELETE=0; REFRESH=1 ;;
  *) echo "usage: mineru_token_check.sh [--delete-expired|--refresh-from-local-cache]" >&2; exit 2 ;;
esac

if [ ! -d "$ROOT" ]; then
  echo "ERR: MinerU root not found: $ROOT" >&2
  echo "Mount the data disk or set MINERU_ROOT." >&2
  exit 2
fi

cd "$ROOT"

if [ "$REFRESH" = "1" ]; then
  TOK="$("$TOKEN_GET" mineru 2>/dev/null || true)"
  if [ -z "$TOK" ]; then
    echo "ERR: no cached 'mineru' secret ($TOKEN_GET mineru)" >&2
    exit 2
  fi
  tmp="$(mktemp "$ROOT/.mineru-token.XXXXXX")"
  trap 'rm -f "$tmp"' EXIT
  chmod 600 "$tmp"
  printf '%s\n' "$TOK" > "$tmp"
  mv -f "$tmp" "$ROOT/minerU-api-token.md"
  chmod 600 "$ROOT/minerU-api-token.md" 2>/dev/null || true
  echo REFRESHED
  exit 0
fi

shopt -s nullglob
for f in minerU-api-token*.md; do
  tok="$(grep -oE '[A-Za-z0-9._-]{20,}' "$f" | head -1)"
  if [ -z "$tok" ]; then echo "$f: NO_TOKEN"; continue; fi
  out="$(mktemp)"
  code="$(curl -s -o "$out" -w '%{http_code}' -X POST "https://mineru.net/api/v4/file-urls/batch" \
    -H "Authorization: Bearer $tok" -H "Content-Type: application/json" \
    -d '{"enable_formula": true, "model_version": "vlm", "files": [{"name": "probe.pdf", "is_ocr": true}]}')"
  msg="$(head -c 120 "$out" | tr -d '\n')"
  rm -f "$out"
  echo "$f: HTTP $code | $msg"
  if [ "$DELETE" = "1" ] && [ "$code" = "401" ]; then
    rm -f "$f" && echo "  deleted expired: $f"
  fi
done
