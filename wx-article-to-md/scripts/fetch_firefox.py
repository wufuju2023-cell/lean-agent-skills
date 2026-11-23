#!/usr/bin/env python3
"""Fetch a WeChat article with real Firefox + WebDriver BiDi.

Reuses the wx-article-to-md convert.js in-page (MathJax SVG -> MathML).
Usage: fetch_firefox.py <url> <out.html> [out-meta.json]
Exit codes: 0 ok, 3 no #js_content, 1 other error.
"""
import json
import os
import sys
import time

sys.path.insert(0, "/data/projects/ai-agent-gui/linux-version/routes/python")
from agentgui.webbidi import Bidi  # noqa: E402

CONVERT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "convert_formula.js")
B64 = ""


def connect(retries=6):
    last = None
    for _ in range(retries):
        try:
            return Bidi("ws://127.0.0.1:9222", timeout=25.0)
        except Exception as exc:  # session busy
            last = exc
            time.sleep(1.5)
    raise RuntimeError(f"cannot connect BiDi: {last}")


def main():
    url, out_html = sys.argv[1], sys.argv[2]
    out_meta = sys.argv[3] if len(sys.argv) > 3 else None
    if "#wechat_redirect" in url:
        url = url.split("#")[0]
    src = open(CONVERT, encoding="utf-8").read()

    b = connect()
    ctx = None
    try:
        ctx = b.create_tab()
        b.set_viewport(ctx, 1280, 900)
        try:
            b.navigate(ctx, url, wait="complete", timeout=60)
        except Exception:
            pass

        deadline = time.time() + 25
        info = {}
        while time.time() < deadline:
            try:
                raw = b.evaluate(
                    ctx,
                    "JSON.stringify({t:document.title,rs:document.readyState,"
                    "has:!!document.getElementById('js_content'),"
                    "math:document.querySelectorAll('[data-owc-math]').length})",
                )
                info = json.loads(raw) if raw else {}
            except Exception:
                info = {}
            if info.get("has"):
                break
            time.sleep(1)

        if not info.get("has"):
            print(
                f"ERROR: #js_content not found (title={info.get('t','')!r}, "
                f"readyState={info.get('rs')})",
                file=sys.stderr,
            )
            sys.exit(3)

        # wait for formula containers to settle (math articles need a moment)
        for _ in range(20):
            if info.get("math", 0) > 0:
                break
            time.sleep(0.5)
            raw = b.evaluate(
                ctx,
                "JSON.stringify({t:document.title,rs:document.readyState,has:true,"
                "math:document.querySelectorAll('[data-owc-math]').length})",
            )
            info = json.loads(raw) if raw else info

        res = b.evaluate(ctx, src, await_promise=False)
        if isinstance(res, dict) and res.get("err"):
            print(f"ERROR: convert failed: {res['err']}", file=sys.stderr)
            sys.exit(3)

        meta_raw = b.evaluate(ctx, "JSON.stringify(window.__wx.meta || {})")
        fraw = b.evaluate(ctx, "JSON.stringify(window.__wx.formulas || [])")
        b64 = b.evaluate(ctx, "window.__wx.b64")
        import base64

        html = base64.b64decode(b64)
        open(out_html, "wb").write(html)
        meta = json.loads(meta_raw) if meta_raw else {}
        formulas = json.loads(fraw) if fraw else []
        if out_meta:
            json.dump(meta, open(out_meta, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        fpath = (out_meta or out_html) + ".formulas.json"
        json.dump(formulas, open(fpath, "w", encoding="utf-8"), ensure_ascii=False)
        print(
            json.dumps(
                {
                    "title": meta.get("title"),
                    "account": meta.get("account"),
                    "date": meta.get("date"),
                    "math_containers": info.get("math"),
                    "formulas": len(formulas),
                    "htmlBytes": len(html),
                },
                ensure_ascii=False,
            )
        )
    finally:
        try:
            if ctx:
                b.close_tab(ctx)
        except Exception:
            pass
        try:
            b.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
