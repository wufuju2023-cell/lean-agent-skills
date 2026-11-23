#!/usr/bin/env python3
"""find_symbols.py — 在 typeshed 里定位符号"真身"（模块 / 类 / 重载数），供写 hover_texts 注册键用。

为什么需要：stubPath 的注册键 (模块, 符号) 必须对准"真身"——写错不会报错，只会静默跳过：
  · os.path.isdir / isfile  → 真身在 genericpath.pyi（os/path.pyi 只是转口）
  · os.path.join            → 真身在 posixpath.pyi（Windows 上对应 ntpath.pyi）
  · io.StringIO             → 真身在 _io.pyi
  · 类的继承方法（如 StringIO.readline）→ 注册在"定义它的基类"上（_io._TextIOBase.readline）

用法:
  python3 find_symbols.py NAME [NAME ...] [--typeshed TS]
    NAME = `listdir`            列出所有同名定义点（含建议注册键与重载数）
    NAME = `StringIO.readline`  解析类的继承链，指出 hover 实际命中的方法
  --typeshed 缺省自动探测 basedpyright 自带的 typeshed-fallback。
"""
from __future__ import annotations

import argparse
import ast
import os
import shutil
from pathlib import Path


def find_typeshed(explicit: str | None) -> Path:
    cands: list[Path] = []
    if explicit:
        cands.append(Path(explicit))
    if os.environ.get("LMC_TYPESHED"):
        cands.append(Path(os.environ["LMC_TYPESHED"]))
    cands += [
        Path("/usr/local/lib/node_modules/basedpyright/dist/typeshed-fallback"),
        Path("/usr/lib/node_modules/basedpyright/dist/typeshed-fallback"),
    ]
    which = shutil.which("basedpyright-langserver") or shutil.which("basedpyright")
    if which:
        p = Path(which).resolve()
        for up in p.parents:
            cands.append(up / "lib" / "node_modules" / "basedpyright" / "dist" / "typeshed-fallback")
    for c in cands:
        if (c / "stdlib").is_dir():
            return c
    raise SystemExit("✗ 找不到 typeshed-fallback（用 --typeshed 指定）")


def mod_name(rel: Path) -> str:
    parts = list(rel.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) if parts else rel.stem


def base_name(node: ast.expr) -> str | None:
    """从基类表达式里取最右边的名字（处理 Name / Attribute / Subscript）。"""
    while True:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        if isinstance(node, ast.Subscript):
            node = node.value
            continue
        return None


class Index:
    def __init__(self) -> None:
        self.defs: dict[str, list[tuple[str, str, int, int]]] = {}   # name -> (mod, rel, lineno, n)
        self.classes: dict[str, list[dict]] = {}                     # name -> {mod, rel, lineno, bases, methods}

    def scope(self, stmts: list[ast.stmt], mod: str, rel: str) -> None:
        counters: dict[str, int] = {}
        for node in stmts:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                counters[node.name] = counters.get(node.name, 0) + 1
                self.defs.setdefault(node.name, []).append((mod, rel, node.lineno, counters[node.name]))
            elif isinstance(node, ast.ClassDef):
                methods: dict[str, list[int]] = {}   # 方法名 -> [首次定义行号, 定义次数(含重载)]
                for sub in ast.walk(node):
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and sub is not node:
                        rec = methods.setdefault(sub.name, [sub.lineno, 0])
                        rec[1] += 1
                self.classes.setdefault(node.name, []).append({
                    "mod": mod, "rel": rel, "lineno": node.lineno,
                    "bases": [b for b in (base_name(x) for x in node.bases) if b],
                    "methods": methods,
                })
                self.scope([n for n in node.body if isinstance(n, ast.ClassDef)], mod, rel)
            elif isinstance(node, (ast.If, ast.Try, ast.For, ast.While, ast.With)):
                self.scope(node.body, mod, rel)
                self.scope(getattr(node, "orelse", []), mod, rel)
                self.scope(getattr(node, "finalbody", []), mod, rel)
                for handler in getattr(node, "handlers", []):
                    self.scope(handler.body, mod, rel)


def build_index(stdlib: Path) -> Index:
    idx = Index()
    for path in sorted(stdlib.rglob("*.pyi")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n"))
        except SyntaxError:
            continue
        idx.scope(tree.body, mod_name(path.relative_to(stdlib)), str(path.relative_to(stdlib)))
    return idx


def approx_chain(idx: Index, cls: str) -> list[str]:
    """近似 MRO：BFS 展开基类名（按简单名解析；足够定位"谁定义了方法"）。"""
    order: list[str] = []
    seen: set[str] = set()
    queue = [cls]
    while queue:
        name = queue.pop(0)
        if name in seen:
            continue
        seen.add(name)
        order.append(name)
        for entry in idx.classes.get(name, []):
            for b in entry["bases"]:
                if b not in seen:
                    queue.append(b)
    return order


def query_plain(idx: Index, name: str) -> None:
    hit = False
    for mod, rel, lineno, n in idx.defs.get(name, []):
        extra = f"  重载/定义 ×{n}" if n > 1 else ""
        print(f'  def {name}: ("{mod}", "{name}")  {rel}:{lineno}{extra}  → 注册键 ("{mod}", "{name}")')
        hit = True
    for entry in idx.classes.get(name, []):
        bases = ", ".join(entry["bases"]) or "-"
        print(f'  class {name}: ("{entry["mod"]}", "{name}")  {entry["rel"]}:{entry["lineno"]}  bases=[{bases}]')
        hit = True
    if not hit:
        print(f"  （没有任何 def/class 叫 {name}）")


def query_method(idx: Index, cls: str, meth: str) -> None:
    classes = idx.classes.get(cls)
    if not classes:
        print(f"  未找到类 `{cls}`。")
        print(f"  提示：链式属性（如 {cls}.{meth}）请直接查末段名字 `{meth}`：")
        query_plain(idx, meth)
        return
    for entry in classes:
        bases = ", ".join(entry["bases"]) or "-"
        print(f'  类 {cls}: ("{entry["mod"]}", "{cls}")  {entry["rel"]}:{entry["lineno"]}  bases=[{bases}]')
        own = entry["methods"].get(meth)
        if own:
            print(f"  自身定义 {meth}: 是 ×{own[1]}（{entry['rel']}:{own[0]}）")
        else:
            print(f"  自身定义 {meth}: 否")
    chain = approx_chain(idx, cls)
    print(f"  继承链（近似）：{' → '.join(chain)}")
    hit = None
    for cname in chain:
        for entry in idx.classes.get(cname, []):
            rec = entry["methods"].get(meth)
            if rec:
                hit = (cname, entry, rec)
                break
        if hit:
            break
    if hit:
        cname, entry, (mline, mcount) = hit
        extra = f" ×{mcount}" if mcount > 1 else ""
        print(f'  ★ hover 命中: ("{entry["mod"]}", "{cname}.{meth}")  {entry["rel"]}:{mline}{extra}'
              f'  → 注册键 ("{entry["mod"]}", "{cname}.{meth}")')
    else:
        print(f"  ★ 继承链上没有任何类定义 {meth}")
    others = sorted({
        cname for cname in idx.classes
        if cname not in chain and any(meth in e["methods"] for e in idx.classes[cname])
    })
    if others:
        shown = ", ".join(others[:8])
        more = f" …等 {len(others)} 个" if len(others) > 8 else ""
        print(f"  （其他类也定义同名方法，仅供参考）: {shown}{more}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="+", help="符号名；类方法写成 Class.method")
    ap.add_argument("--typeshed", default=None)
    args = ap.parse_args()

    stdlib = find_typeshed(args.typeshed) / "stdlib"
    print(f"typeshed: {stdlib}")
    idx = build_index(stdlib)
    for name in args.names:
        print(f"== {name} ==")
        if "." in name:
            cls, meth = name.rsplit(".", 1)
            query_method(idx, cls, meth)
        else:
            query_plain(idx, name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
