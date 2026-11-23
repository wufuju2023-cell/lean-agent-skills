#!/usr/bin/env python3
# postprocess.py <raw.md> <meta.json> <out.md>
# Clean pandoc output and prepend YAML frontmatter.

import json
import os
import re
import sys


def yaml_quote(v):
    v = (v or '').strip()
    return '"' + v.replace('\\', '\\\\').replace('"', '\\"') + '"'


def main():
    raw_path, meta_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    md = open(raw_path, encoding='utf-8').read()

    lines = []
    for l in md.split('\n'):
        if re.match(r'^\s*(?:[-*+]|\d+\.)?\s*:{3,}\s*\S*\s*$', l):
            continue
        if l.strip() == '\\':
            lines.append('')
            continue
        lines.append(l)
    md = '\n'.join(lines)

    md = md.replace('\\operatorname{}', '')
    md = re.sub(r'\)\{\.rich_pages[^}]*\}', ')', md)
    md = re.sub(r'\n{3,}', '\n\n', md)
    md = md.strip() + '\n'

    meta = {}
    if meta_path and os.path.exists(meta_path):
        try:
            meta = json.load(open(meta_path, encoding='utf-8'))
        except Exception:
            meta = {}
    title = meta.get('title') or '公众号文章'
    header = (
        '---\n'
        f'title: {yaml_quote(title)}\n'
        f'account: {yaml_quote(meta.get("account", ""))}\n'
        f'date: {yaml_quote(meta.get("date", ""))}\n'
        f'source: {yaml_quote(meta.get("url", ""))}\n'
        '---\n\n'
        f'# {title}\n\n'
    )
    open(out_path, 'w', encoding='utf-8').write(header + md)
    print(f'wrote {out_path} ({len(header + md)} chars)')


if __name__ == '__main__':
    main()
