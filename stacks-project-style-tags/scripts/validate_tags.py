#!/usr/bin/env python3
"""Validate Stacks-Project-style tags. See SKILL.md for the convention.

Usage: python3 validate_tags.py <root-dir>

Checks:
  1. Prose item tags 【Env num｜TYPE-doccode.sec.item】 are unique across the tree.
  2. Within each document, non-proof items in a section are numbered 1..n in order.
  3. In-text references 【Env doccode.sec.item】 resolve to a defined item
     (references and examples inside inline code spans / fenced blocks are ignored).
  4. Notebooks: file tag 【notebook｜N-NN】 present; every code cell starts with
     a 【N-NN.cK】 tag.
  5. Code files (*.py, *.sh): exactly one file tag 【源代码｜F-...】 / 【脚本｜F-...】.
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

PROSE_TYPES = {"D", "T", "P", "L", "C", "E", "R", "A", "Cd", "Ex"}
ITEM_LINE = re.compile(r"【[^｜】\n]+｜([A-Za-z]+)-([0-9A-Za-z]+)\.(\d+)\.(\d+)】")
REF = re.compile(r"【[A-Za-z\u4e00-\u9fff]+ ([0-9A-Za-z]+\.\d+\.\d+)】")
INLINE_CODE = re.compile(r"`[^`\n]*`")
DOC_TAG = re.compile(r"【文档｜(DOC-[A-Za-z0-9_-]+)】")
FILE_TAG_F = re.compile(r"【(?:源代码|脚本)｜(F-[A-Za-z0-9_.\-]+)】")
NB_FILE_TAG = re.compile(r"【notebook｜(N-\d\d)】")


def scan_md(text: str):
    """Yield (lineno, line) for markdown with fenced code removed and inline code stripped."""
    in_fence = False
    for lineno, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        yield lineno, INLINE_CODE.sub("", line)


def main(root_arg: str) -> int:
    root = Path(root_arg)
    errors, warns = [], []
    tag_owner = defaultdict(list)
    item_nums = set()
    per_file = {}
    doc_tags = defaultdict(list)
    f_tags = defaultdict(list)
    n_tags = defaultdict(list)

    md_files = sorted(root.rglob("*.md"))
    for md in md_files:
        text = md.read_text(encoding="utf-8", errors="replace")
        rel = str(md.relative_to(root))
        items = []
        for lineno, line in scan_md(text):
            for m in ITEM_LINE.finditer(line):
                typ, doc, sec, it = m.group(1), m.group(2), int(m.group(3)), int(m.group(4))
                if typ not in PROSE_TYPES and typ != "Pf":
                    continue
                tag = f"{typ}-{doc}.{sec}.{it}"
                tag_owner[tag].append(rel)
                items.append((typ, doc, sec, it, lineno))
                if typ != "Pf":
                    item_nums.add(f"{doc}.{sec}.{it}")
            for m in DOC_TAG.finditer(line):
                doc_tags[m.group(1)].append(rel)
        per_file[md] = items

    for tag, files in sorted(tag_owner.items()):
        if len(files) > 1:
            errors.append(f"duplicate tag {tag} in {files}")

    for md, items in per_file.items():
        seq = defaultdict(list)
        for typ, doc, sec, it, ln in items:
            if typ == "Pf":
                continue
            seq[(doc, sec)].append(it)
        for (doc, sec), nums in seq.items():
            if nums != list(range(1, len(nums) + 1)):
                errors.append(
                    f"{md.relative_to(root)}: section {doc}.{sec} numbering not 1..n: {nums}"
                )

    for md in md_files:
        for lineno, line in scan_md(md.read_text(encoding="utf-8", errors="replace")):
            for m in REF.finditer(line):
                num = m.group(1)
                if num not in item_nums:
                    errors.append(
                        f"{md.relative_to(root)}:{lineno}: unresolved reference 【… {num}】"
                    )

    for key, files in sorted(doc_tags.items()):
        if len(files) > 1:
            errors.append(f"duplicate DOC tag {key} in {files}")

    for nb in sorted(root.rglob("*.ipynb")):
        rel = str(nb.relative_to(root))
        try:
            data = json.loads(nb.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{rel}: invalid JSON: {exc}")
            continue
        raw = json.dumps(data, ensure_ascii=False)
        m = NB_FILE_TAG.search(raw)
        if not m:
            warns.append(f"{rel}: missing notebook file tag 【notebook｜N-NN】")
        else:
            n_tags[m.group(1)].append(rel)
        k = 0
        for idx, cell in enumerate(data.get("cells", []), 1):
            if cell.get("cell_type") != "code":
                continue
            k += 1
            src = "".join(cell.get("source", [])).strip()
            first = src.splitlines()[0] if src else ""
            if "【N-" not in first:
                warns.append(f"{rel}: code cell #{idx} (code index {k}) missing leading tag comment")

    for key, files in sorted(n_tags.items()):
        if len(files) > 1:
            errors.append(f"duplicate notebook tag {key} in {files}")

    for code in sorted([*root.rglob("*.py"), *root.rglob("*.sh")]):
        rel = str(code.relative_to(root))
        hits = FILE_TAG_F.findall(code.read_text(encoding="utf-8", errors="replace"))
        if len(hits) > 1:
            errors.append(f"{rel}: multiple file tags {hits}")
        elif not hits:
            warns.append(f"{rel}: missing file tag 【源代码｜F-...】")
        else:
            f_tags[hits[0]].append(rel)

    for key, files in sorted(f_tags.items()):
        if len(files) > 1:
            errors.append(f"duplicate code file tag {key} in {files}")

    print(f"errors: {len(errors)}; warnings: {len(warns)}")
    for e in errors[:200]:
        print("ERROR", e)
    for w in warns[:200]:
        print("WARN ", w)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
