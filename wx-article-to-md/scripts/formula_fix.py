#!/usr/bin/env python3
"""Replace WXMATHTOKEN<i>END placeholders with $...$ / $$...$$ LaTeX."""
import json, re, sys

md_path, fj = sys.argv[1], sys.argv[2]
formulas = json.load(open(fj, encoding="utf-8")) if fj != "-" else []
md = open(md_path, encoding="utf-8").read()

def rep(m):
    i = int(m.group(1))
    if i >= len(formulas):
        return m.group(0)
    tex = formulas[i]["tex"].strip()
    if formulas[i]["disp"]:
        return "\n\n$$\n" + tex + "\n$$\n\n"
    return "$" + tex + "$"

md, n = re.subn(r"WXMATHTOKEN(\d+)END", rep, md)
md = re.sub(r"\n{3,}", "\n\n", md)
open(md_path, "w", encoding="utf-8").write(md)
print(f"formulas substituted: {n}")
