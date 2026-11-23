#!/usr/bin/env python3
"""build_typings.py — 生成「教学版 stubs」：官方文档 backfill + 中文讲解【追加】。

机制（已在 this machine 实测：basedpyright 1.40 / Python 3.14 / nvim 0.12）：

  · 仓库根放 `pyrightconfig.json`：`{"stubPath": "typings"}`；nvim + basedpyright
    会把 `typings/` 下的存根「遮蔽」到同名标准库模块之上（悬停显示我们的文本）；
  · 遮蔽是「整模块替换」：stub 里没有的内容会消失 ⇒ 必须从 basedpyright 自带
    typeshed **完整复制**（签名/类型逐字不动）；
  · basedpyright 默认会给标准库补「运行时文档」（例：`os.getenv`）；遮蔽后这份
    内容会丢 ⇒ 对 stub 里缺 docstring 的函数/类，从 Python 运行时取 `__doc__`
    补回（backfill，保证官方内容不丢）；
  · 中文教学文案（`study-tools/hover_texts.py`）只【追加】在官方文档下方，绝不替换。

用法:
  python3 study-tools/build_typings.py             # 重建 <repo>/typings/（幂等）
  python3 study-tools/build_typings.py --dry-run   # 只统计、不写盘
环境变量:
  LMC_TYPESHED   自定义 typeshed-fallback 路径（默认自动探测 basedpyright 自带）
"""
from __future__ import annotations

import argparse
import ast
import importlib
import inspect
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hover_texts  # noqa: E402  （同目录的文案注册表）


def find_typeshed() -> Path:
    cands: list[Path] = []
    if os.environ.get("LMC_TYPESHED"):
        cands.append(Path(os.environ["LMC_TYPESHED"]))
    cands.append(Path("/usr/local/lib/node_modules/basedpyright/dist/typeshed-fallback"))
    cands.append(Path("/usr/lib/node_modules/basedpyright/dist/typeshed-fallback"))
    which = shutil.which("basedpyright-langserver") or shutil.which("basedpyright")
    if which:
        p = Path(which).resolve()
        for up in p.parents:
            cands.append(up / "lib" / "node_modules" / "basedpyright" / "dist" / "typeshed-fallback")
    for c in cands:
        if (c / "stdlib").is_dir():
            return c
    raise SystemExit("✗ 找不到 typeshed-fallback（可设 LMC_TYPESHED 环境变量）")


def format_doc_block(doc: str, body_indent: str) -> list[str]:
    """把一段文档格式化为 docstring 行（含缩进）；短单行保持单行。

    注意：文档里的反斜杠（转义序列字面量）必须再转义一层写入，
    否则写进 stub 的普通字符串会触发 Python 转义解析、破坏语法。
    """
    def safe(s: str) -> str:
        return s.replace("\\", "\\\\")

    if "\n" not in doc and not doc.endswith('"') and len(doc) + len(body_indent) + 6 <= 100:
        return [body_indent + '"""' + safe(doc) + '"""']
    out = [body_indent + '"""']
    for ln in doc.split("\n"):
        out.append(body_indent + safe(ln) if ln.strip() else "")
    out.append(body_indent + '"""')
    return out


def get_docstring(node: ast.AST) -> ast.Expr | None:
    body = getattr(node, "body", None) or []
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        return body[0]
    return None


def resolve_runtime(mod, dotted: str):
    obj = mod
    try:
        for part in dotted.split("."):
            obj = getattr(obj, part)
    except Exception:
        return None
    return obj


def collect_defs(tree: ast.AST) -> list[tuple[ast.AST, str]]:
    """收集所有 def/class（含 if/try 块内的，如平台开关里的定义）。

    类要递归进去（收集方法）；函数体不递归（stub 里极少有嵌套定义）。
    """
    out: list[tuple[ast.AST, str]] = []

    def walk(parent: ast.AST, prefix: tuple[str, ...]) -> None:
        for child in ast.iter_child_nodes(parent):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out.append((child, ".".join(prefix + (child.name,))))
            elif isinstance(child, ast.ClassDef):
                dotted = prefix + (child.name,)
                out.append((child, ".".join(dotted)))
                walk(child, dotted)
            else:
                walk(child, prefix)

    walk(tree, ())
    dedup: dict[int, tuple[ast.AST, str]] = {}
    for node, dotted in out:
        dedup.setdefault(id(node), (node, dotted))
    return list(dedup.values())


def inject_file(path: Path, mod_name: str, texts: dict, report: dict, dry: bool) -> None:
    raw = path.read_bytes()
    eol = "\r\n" if b"\r\n" in raw[:4096] else "\n"
    src = raw.decode("utf-8").replace("\r\n", "\n")
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        report["errors"].append(f"{path}: 解析失败: {exc}")
        return
    lines = src.split("\n")

    if path.name == "__init__.pyi":
        rt_name = mod_name
    elif path.stem == mod_name:  # 单文件模块：subprocess.pyi → subprocess
        rt_name = mod_name
    else:
        rt_name = f"{mod_name}.{path.stem}"
    try:
        runtime_mod = importlib.import_module(rt_name)
    except Exception:
        runtime_mod = None  # 运行时没有对应模块（如平台限制）：只做教学注入

    edits: list[tuple[int, int, list[str], str]] = []

    derived = {(mod, sym + ".__init__"): t for (mod, sym), t in texts.items()}

    for node, dotted in collect_defs(tree):
        obj = resolve_runtime(runtime_mod, dotted) if runtime_mod else None
        runtime_doc = None
        if obj is not None and isinstance(getattr(obj, "__doc__", None), str):
            doc = inspect.cleandoc(obj.__doc__)
            if doc and '"""' not in doc:
                runtime_doc = doc

        d = get_docstring(node)

        teaching = texts.get((mod_name, dotted))
        if teaching is None:
            # 类悬停实测优先显示 __init__ 的 docstring：类的教学同步作用于其
            # __init__（仅在 hover 仍能保留官方内容——源码或运行时至少一份官方
            # 文档——时才动；否则保持原样走「类文档」通道，避免挤掉官方内容）。
            teaching = derived.get((mod_name, dotted))
            if teaching is not None and d is None and runtime_doc is None:
                teaching = None
        if teaching and '"""' in teaching:
            report["warnings"].append(f"跳过（含三引号）: {mod_name}.{dotted}")
            continue
        if not teaching and runtime_doc is None:
            continue

        body_indent = " " * (node.col_offset + 4)

        if d is not None:
            if not teaching:
                continue  # 官方已有文档且无需追加：逐字保持原样
            combined = inspect.cleandoc(d.value.value) + "\n\n" + teaching
            if d.lineno == node.lineno:
                head = lines[d.lineno - 1][: d.col_offset].rstrip()
                edits.append(
                    (d.lineno, d.end_lineno, [head] + format_doc_block(combined, body_indent),
                     f"append {mod_name}.{dotted}")
                )
            else:
                edits.append(
                    (d.lineno, d.end_lineno, format_doc_block(combined, body_indent),
                     f"append {mod_name}.{dotted}")
                )
            continue

        text = runtime_doc or ""
        if teaching:
            text = (text + "\n\n" + teaching) if text else teaching

        first = node.body[0] if getattr(node, "body", None) else None
        if first is None:
            continue

        is_ellipsis = (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and first.value.value is Ellipsis
        )
        if is_ellipsis:
            line = lines[first.lineno - 1]
            if line.strip() == "...":
                # 独占一行的 `...`：整行换成 docstring
                edits.append(
                    (first.lineno, first.end_lineno, format_doc_block(text, body_indent),
                     f"insert {mod_name}.{dotted}")
                )
            else:
                # 与签名同行（单行 `def f(): ...`，或多行签名的收尾行
                # `) -> T: ...`）：只替换行尾的 `: ...`，绝不能整行替换！
                idx = line.rfind(": ...")
                if idx == -1:
                    report["warnings"].append(f"跳过（无法定位 `: ...`）: {mod_name}.{dotted}")
                    continue
                edits.append(
                    (first.lineno, first.end_lineno,
                     [line[:idx] + ":"] + format_doc_block(text, body_indent),
                     f"insert {mod_name}.{dotted}")
                )
        elif isinstance(first, ast.Pass):
            orig = lines[first.lineno - 1]
            edits.append(
                (first.lineno, first.lineno,
                 format_doc_block(text, body_indent) + [orig],
                 f"insert {mod_name}.{dotted}")
            )
        elif first.lineno == node.lineno:
            report["warnings"].append(f"跳过（同行复杂 body）: {mod_name}.{dotted}")
        else:
            # 通用插入：docstring 放到「头部行」之后。
            # 绝不能放在首条语句之前——首条语句自己可能也有编辑（如同体行 `: ...`
            # 拼接），两条编辑会踩到同一行相互破坏（Event 类事故复盘）。
            boundary = first.lineno
            for dec in getattr(first, "decorator_list", []):
                boundary = min(boundary, dec.lineno)
            h_idx = node.lineno - 1  # 0-based；至少是 def/class 所在行
            for i in range(boundary - 2, node.lineno - 2, -1):
                if i >= 0 and lines[i].strip():
                    h_idx = i
                    break
            edits.append(
                (h_idx + 1, h_idx + 1,
                 [lines[h_idx]] + format_doc_block(text, body_indent),
                 f"insert {mod_name}.{dotted}")
            )

    edits.sort(key=lambda e: (e[0], e[1]))
    for prev, cur in zip(edits, edits[1:]):
        if cur[0] <= prev[1]:  # 编辑范围重叠 → 拒绝写盘（防相互破坏）
            report["errors"].append(
                f"{path}: 编辑范围重叠（{prev[3]} vs {cur[3]}），已回滚")
            return
    for start, end, new_lines, kind in reversed(edits):
        if not dry:
            lines[start - 1 : end] = new_lines
        report["applied"].append(kind)

    if not dry and edits:
        new_src = "\n".join(lines)
        try:
            ast.parse(new_src)  # 写盘前自检：注入后必须是合法 Python
        except SyntaxError as exc:
            report["errors"].append(f"{path}: 注入后语法错误，已回滚（{exc}）")
            return
        path.write_text(new_src, encoding="utf-8", newline=eol)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    repo: Path = args.repo.resolve()
    typings = repo / "typings"
    ts = find_typeshed()
    texts = hover_texts.TEXTS

    report: dict = {"applied": [], "warnings": [], "errors": []}
    print(f"typeshed: {ts}")
    print(f"repo    : {repo}")
    print(f"modules : {', '.join(hover_texts.MODULES)}")

    if not args.dry_run:
        if typings.exists():
            shutil.rmtree(typings)
        typings.mkdir(parents=True)

    for mod in hover_texts.MODULES:
        src_dir = ts / "stdlib" / mod
        src_file = ts / "stdlib" / f"{mod}.pyi"
        if src_dir.is_dir():
            src, dst = src_dir, typings / mod
        elif src_file.is_file():
            src, dst = src_file, typings / f"{mod}.pyi"
        else:
            report["errors"].append(f"{mod}: typeshed 里找不到 {src_dir} 或 {src_file}")
            continue
        if not args.dry_run:
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
        scope = dst if not args.dry_run else src
        files = sorted(scope.rglob("*.pyi")) if scope.is_dir() else [scope]
        before = len(report["applied"])
        for f in files:
            inject_file(f, mod, texts, report, args.dry_run)
        print(f"  {mod:12s} 注入 {len(report['applied']) - before} 处")

    hits = report["applied"]
    for (mod, sym) in texts:
        if not any(k.endswith(f"{mod}.{sym}") for k in hits):
            report["warnings"].append(f"注册了但 stub 里没找到符号: {mod}.{sym}")

    print()
    print(f"总计注入: {len(hits)} 处")
    for w in report["warnings"]:
        print(f"  [warn] {w}")
    for e in report["errors"]:
        print(f"  [error] {e}")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
