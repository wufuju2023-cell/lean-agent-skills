#!/usr/bin/env bash
# Minimal tmux harness for OpenCode TUI E2E tests.
#
#   tui-e2e.sh start <session> <dir> [width] [height]
#   tui-e2e.sh send  <session> <text>          # literal text + Enter
#   tui-e2e.sh key   <session> <tmux-key>...   # e.g. Enter, C-u, Escape
#   tui-e2e.sh read  <session> [lines]         # rendered screen, tail N lines
#   tui-e2e.sh wait  <session> <regex> [secs]  # poll the screen until regex matches
#   tui-e2e.sh stop  <session>
#
# Env:
#   OC  path to the v2 binary (default ~/.opencode2/bin/opencode)
#
# Never use `tmux kill-server`: it kills the user's sessions too.

set -euo pipefail

OC=${OC:-~/.opencode2/bin/opencode}
cmd=${1:-}
[ -n "$cmd" ] || { sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }
shift

case "$cmd" in
  start)
    name=${1:?session name}; dir=${2:?directory}; w=${3:-200}; h=${4:-50}
    if tmux has-session -t "$name" 2>/dev/null; then
      echo "session already exists: $name" >&2
      exit 1
    fi
    [ -d "$dir" ] || { echo "no such directory: $dir" >&2; exit 1; }
    tmux new-session -d -s "$name" -x "$w" -y "$h" \
      "cd '$dir' && exec '$OC'; echo EXIT=\$?; sleep 86400"
    tmux set-option -t "$name" window-size manual
    echo "started $name ($w x $h) in $dir"
    ;;
  send)
    name=${1:?session name}; text=${2-}
    tmux send-keys -t "$name" -l "$text"
    tmux send-keys -t "$name" Enter
    ;;
  key)
    name=${1:?session name}; shift
    [ $# -gt 0 ] || { echo "no keys given" >&2; exit 2; }
    tmux send-keys -t "$name" "$@"
    ;;
  read)
    name=${1:?session name}; lines=${2:-80}
    tmux capture-pane -p -t "$name" | tail -n "$lines"
    ;;
  wait)
    name=${1:?session name}; re=${2:?regex}; timeout=${3:-120}
    deadline=$((SECONDS + timeout))
    while (( SECONDS < deadline )); do
      tmux has-session -t "$name" 2>/dev/null || { echo "session died: $name" >&2; exit 1; }
      if tmux capture-pane -p -t "$name" | grep -qE "$re"; then
        echo "matched: /$re/"
        exit 0
      fi
      sleep 2
    done
    echo "timeout after ${timeout}s waiting for /$re/" >&2
    tmux capture-pane -p -t "$name" | tail -n 40 >&2 || true
    exit 1
    ;;
  stop)
    name=${1:?session name}
    tmux kill-session -t "$name" 2>/dev/null || true
    echo "stopped $name"
    ;;
  *)
    echo "unknown command: $cmd" >&2
    exit 2
    ;;
esac
