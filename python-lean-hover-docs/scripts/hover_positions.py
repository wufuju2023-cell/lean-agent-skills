#!/usr/bin/env python3
"""hover_positions.py — 一次算好两套悬停坐标（避免"点错列"的返工）。

实测背景：同一位置两套坐标不同 ——
  · hover_client / LSP：列 = 字符数（UTF-16 码元）
  · nvim 光标（nvim_win_set_cursor）：列 = 字节数
行首有中文时差异巨大（实测同一位置 35 vs 55），用错列会出现"未找到浮窗"
或悬停到隔壁符号（实测点到 `raw` 而不是 `strip`）。

用法:
  python3 hover_positions.py FILE NEEDLE [--nth N] [--token SUBSTR]
    · NEEDLE：单行内的一段文本（整行片段也行）
    · --nth ：找第几次出现（默认 1）
    · --token：NEEDLE 内想瞄准的子串（默认瞄 NEEDLE 起点）
输出：hover_client 的 (line0, char0) 与 nvim 的 (line1, byte1)。
"""
from __future__ import annotations

import argparse
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("needle")
    ap.add_argument("--nth", type=int, default=1)
    ap.add_argument("--token", default=None)
    args = ap.parse_args()

    if "\n" in args.needle:
        sys.exit("✗ NEEDLE 必须是单行文本")

    text = open(args.file, encoding="utf-8", newline="").read()
    if "\r\n" in text:
        print("⚠ 文件是 CRLF 行尾：字节列会额外多出 \\r 的偏移，请以实测为准")

    idx = -1
    for _ in range(args.nth):
        idx = text.find(args.needle, idx + 1)
        if idx == -1:
            sys.exit(f"✗ 第 {args.nth} 次未找到 NEEDLE：{args.needle!r}")

    token = args.token if args.token is not None else args.needle
    off = args.needle.find(token)
    if off == -1:
        sys.exit(f"✗ token {token!r} 不在 NEEDLE 内")
    pos = idx + off

    line0 = text.count("\n", 0, pos)
    line_start = text.rfind("\n", 0, pos) + 1
    prefix = text[line_start:pos]
    char0 = len(prefix.encode("utf-16-le")) // 2          # LSP / hover_client 口径
    byte1 = len(prefix.encode("utf-8")) + 1               # nvim 光标口径（1-based）
    line_text = text[line_start:text.find("\n", line_start)]

    print(f"行内容：{line_text}")
    print(f"hover_client: line0={line0} char0={char0}")
    print(f"nvim (K)    : line1={line0 + 1} byte1={byte1}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
