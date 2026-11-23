#!/usr/bin/env python3
"""Source-only index for AxiomMath/Stacks.

Scans the checkout, extracts Stacks/EGA/SGA attributes and declaration names,
and writes stats.json + TSVs + INDEX.md under the output directory.

Usage:
    python3 index_stacks.py /data/axiom-repos/Stacks \
        -o /data/axiom-repos/index
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

DECL_KINDS = (
    "theorem", "lemma", "def", "abbrev", "instance", "structure",
    "class", "inductive", "opaque",
)
# Attributes may span several lines; we only need to spot the tag line and then
# look ahead for the declaration it decorates.
RE_STACKS = re.compile(r"@\[\s*stacks\s+([0-9A-Z]{4})\b")
RE_ADD_STACKS = re.compile(r"\badd_to_stacks\s+([0-9A-Z]{4})\b")
RE_EGA = re.compile(r'@\[\s*ega\s+"([^"]+)"')
RE_SGA = re.compile(r'@\[\s*sga\s+"([^"]+)"')
RE_DECL_LINE = re.compile(
    r"^\s*(?:@\[[^\]]*\]\s*)*"
    r"(?:(?:private|protected|noncomputable|partial|unsafe|nonrec)\s+)*"
    r"(" + "|".join(DECL_KINDS) + r")\s+([A-Za-z_][\w'.]*)"
)
RE_ANY_DECL = re.compile(
    r"^\s*(?:(?:private|protected|noncomputable|partial|unsafe|nonrec)\s+)*"
    r"(?:" + "|".join(DECL_KINDS) + r")\b",
    re.MULTILINE,
)
RE_SORRY = re.compile(r"\bsorry\b")


def _strip_line_chars(line: str, depth: int) -> tuple[str, int]:
    """Strip block/line comments from one line; strings are left alone."""
    out: list[str] = []
    i, n = 0, len(line)
    while i < n:
        c = line[i]
        nxt = line[i + 1] if i + 1 < n else ""
        if depth > 0:
            if c == "/" and nxt == "-":
                depth += 1
                out.append("  ")
                i += 2
            elif c == "-" and nxt == "/":
                depth -= 1
                out.append("  ")
                i += 2
            else:
                out.append("\n" if c == "\n" else " ")
                i += 1
        else:
            if c == "-" and nxt == "-":
                out.append(" " * (n - i))
                i = n
            elif c == "/" and nxt == "-":
                depth = 1
                out.append("  ")
                i += 2
            else:
                out.append(c)
                i += 1
    return "".join(out), depth


def strip_comments(text: str) -> str:
    """Blank out Lean comments, preserving line numbers. Fast path per line."""
    out: list[str] = []
    depth = 0
    for line in text.splitlines(keepends=True):
        if depth == 0 and "/-" not in line and "--" not in line:
            out.append(line)
        else:
            stripped, depth = _strip_line_chars(line, depth)
            out.append(stripped)
    return "".join(out)


def declaration_after(lines: list[str], start: int, lookahead: int = 25) -> tuple[str, str]:
    for j in range(start, min(start + lookahead, len(lines))):
        m = RE_DECL_LINE.match(lines[j])
        if m:
            return m.group(1), m.group(2)
    return "", ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", nargs="?", default="/data/axiom-repos/Stacks")
    ap.add_argument("-o", "--out", default="/data/axiom-repos/index")
    args = ap.parse_args()

    repo = os.path.abspath(args.repo)
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)

    files_total = lines_total = bytes_total = 0
    decl_total = 0
    sorry_total = 0
    trees: dict[str, dict[str, int]] = collections.defaultdict(
        lambda: {"files": 0, "lines": 0, "bytes": 0}
    )
    dirs: collections.Counter[str] = collections.Counter()

    tag_rows: list[tuple[str, str, int, str, str, str]] = []
    ega_rows: list[tuple[str, str, int, str, str]] = []
    sga_rows: list[tuple[str, str, int, str, str]] = []
    tag_counter: collections.Counter[str] = collections.Counter()
    unique_tags: set[str] = set()

    lean_files: list[str] = []
    for root, _dirnames, filenames in os.walk(repo):
        if ".git" in root.split(os.sep):
            continue
        for name in filenames:
            if name.endswith(".lean"):
                lean_files.append(os.path.join(root, name))
    lean_files.sort()

    for path in lean_files:
        rel = os.path.relpath(path, repo)
        top = rel.split(os.sep)[0]
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError as exc:
            print(f"skip {rel}: {exc}", file=sys.stderr)
            continue
        lines = strip_comments(text).splitlines()
        nlines = text.count("\n") + (0 if text.endswith("\n") else 1)
        nbytes = len(text.encode("utf-8", errors="replace"))
        files_total += 1
        lines_total += nlines
        bytes_total += nbytes
        trees[top]["files"] += 1
        trees[top]["lines"] += nlines
        trees[top]["bytes"] += nbytes
        if "/" in rel:
            dirs[rel.split(os.sep)[0] + "/" + rel.split(os.sep)[1]] += 1
        clean = "\n".join(lines)
        decl_total += len(RE_ANY_DECL.findall(clean))
        sorry_total += len(RE_SORRY.findall(clean))

        for lineno, line in enumerate(lines, 1):
            for m in RE_STACKS.finditer(line):
                tag = m.group(1)
                kind, decl = declaration_after(lines, lineno)
                tag_rows.append((tag, rel, lineno, kind, decl, "attribute"))
                tag_counter[tag] += 1
                unique_tags.add(tag)
            for m in RE_ADD_STACKS.finditer(line):
                tag = m.group(1)
                tag_rows.append((tag, rel, lineno, "", "", "add_to_stacks"))
                tag_counter[tag] += 1
                unique_tags.add(tag)
            for m in RE_EGA.finditer(line):
                kind, decl = declaration_after(lines, lineno)
                ega_rows.append((m.group(1), rel, lineno, kind, decl))
            for m in RE_SGA.finditer(line):
                kind, decl = declaration_after(lines, lineno)
                sga_rows.append((m.group(1), rel, lineno, kind, decl))

    try:
        rev = subprocess.check_output(
            ["git", "-C", repo, "rev-parse", "HEAD"], text=True
        ).strip()
        subject = subprocess.check_output(
            ["git", "-C", repo, "log", "-1", "--format=%cI %s"], text=True
        ).strip()
    except Exception:
        rev, subject = "", ""

    stats = {
        "repo": repo,
        "rev": rev,
        "commit": subject,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files_total": files_total,
        "lines_total": lines_total,
        "bytes_total": bytes_total,
        "declarations_total": decl_total,
        "sorry_occurrences": sorry_total,
        "tags": {
            "unique": len(unique_tags),
            "occurrences": len(tag_rows),
            "attribute": sum(1 for r in tag_rows if r[5] == "attribute"),
            "add_to_stacks": sum(1 for r in tag_rows if r[5] == "add_to_stacks"),
            "top20": tag_counter.most_common(20),
        },
        "ega": {"occurrences": len(ega_rows), "unique": len({r[0] for r in ega_rows})},
        "sga": {"occurrences": len(sga_rows), "unique": len({r[0] for r in sga_rows})},
        "trees": dict(trees),
        "top_dirs": dirs.most_common(30),
    }
    with open(os.path.join(out, "stats.json"), "w", encoding="utf-8") as fh:
        json.dump(stats, fh, ensure_ascii=False, indent=2)

    with open(os.path.join(out, "stacks_tags.tsv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["tag", "file", "line", "kind", "decl", "source"])
        w.writerows(sorted(tag_rows))
    with open(os.path.join(out, "ega_sga.tsv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["ref", "file", "line", "kind", "decl", "series"])
        for ref, rel, lineno, kind, decl in sorted(ega_rows):
            w.writerow([ref, rel, lineno, kind, decl, "ega"])
        for ref, rel, lineno, kind, decl in sorted(sga_rows):
            w.writerow([ref, rel, lineno, kind, decl, "sga"])

    mb = bytes_total / 1e6
    core = trees.get("StacksCore", {"files": 0, "lines": 0, "bytes": 0})
    frontier = trees.get("StacksFrontier", {"files": 0, "lines": 0, "bytes": 0})
    index_md = f"""# AxiomMath/Stacks — source index

Generated: {stats["generated_at"]}
Source: `{repo}`
Commit: `{rev}` ({subject})

## Counts

| Metric | Value |
|---|---|
| Lean files | {files_total:,} |
| Lines of Lean | {lines_total:,} |
| Source size | {mb:,.1f} MB |
| Declarations (heuristic) | {decl_total:,} |
| `sorry` occurrences (code only) | {sorry_total:,} |
| Stacks tags (unique) | {len(unique_tags):,} |
| Stacks tag occurrences | {len(tag_rows):,} |
| EGA references | {len(ega_rows):,} |
| SGA references | {len(sga_rows):,} |

## Trees

| Tree | Files | Lines | Size |
|---|---:|---:|---:|
| StacksCore | {core["files"]:,} | {core["lines"]:,} | {core["bytes"]/1e6:,.1f} MB |
| StacksFrontier | {frontier["files"]:,} | {frontier["lines"]:,} | {frontier["bytes"]/1e6:,.1f} MB |

## Files

- `stats.json` — all counts and per-tree stats
- `stacks_tags.tsv` — `tag, file, line, kind, decl, source`
- `ega_sga.tsv` — `ref, file, line, kind, decl, series`

## Notes

- `StacksCore` is built (445 oleans, ~400 MB); `import StacksCore` works.
- `StacksFrontier` is not built; `import Stacks` needs all 62,527 Frontier modules.
- Toolchain: Lean `v4.35.0`; Mathlib `v4.35.0`.
- Refreshing: `git -C {repo} pull --ff-only && python3 {os.path.abspath(__file__)} {repo} -o {out}`
"""
    with open(os.path.join(out, "INDEX.md"), "w", encoding="utf-8") as fh:
        fh.write(index_md)

    print(json.dumps({k: stats[k] for k in (
        "files_total", "lines_total", "declarations_total", "sorry_occurrences"
    )}, ensure_ascii=False))
    print(f"tags: {len(unique_tags)} unique / {len(tag_rows)} occurrences")
    print(f"ega: {len(ega_rows)}  sga: {len(sga_rows)}")
    print(f"out: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
