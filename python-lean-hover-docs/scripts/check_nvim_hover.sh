#!/usr/bin/env bash
# check_nvim_hover.sh —— 用 headless nvim 实测「按 K 的悬停效果」并打印浮窗内容。
#
# 用法:  check_nvim_hover.sh <file> <line(1-based)> <col(1-based)> [nvim-init]
# 例:    bash study-tools/check_nvim_hover.sh lmc/session.py 78 25
#
# 说明:
#   - 用你本地环境的 nvim 配置启动（默认 ~/.config/nvim/init.lua）；
#   - 文件必须位于 git 仓库内（你 nvim 的 root_markers 是 pyproject.toml/.git）；
#   - 需要 basedpyright-langserver 已在 PATH（或 ~/.local/bin）。
set -u
FILE="$(readlink -f "$1")"
LINE="${2:?用法: check_nvim_hover.sh <file> <line> <col> [nvim-init]}"
COL="${3:?用法: check_nvim_hover.sh <file> <line> <col> [nvim-init]}"
INIT="${4:-$HOME/.config/nvim/init.lua}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export PATH="$HOME/.local/bin:$PATH"
export HOVER_LINE="$LINE" HOVER_COL="$COL"

timeout "${HOVER_TIMEOUT:-120}" nvim --headless -u "$INIT" \
  -c "luafile $DIR/nvim_hover_check.lua" "$FILE" 2>&1 | tail -60
