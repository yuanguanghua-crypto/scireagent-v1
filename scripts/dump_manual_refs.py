#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把说明书里每条 `file:line` 引用的**目标行原文**打出来，供人逐条判断语义是否匹配。

用法：
  python scripts/dump_manual_refs.py            # 全部
  python scripts/dump_manual_refs.py --grep COA # 只看含某关键词的
"""
import io
import os
import re
import sys
import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, 'docs', 'e2e', 'SITE_ROLE_OPERATION_MANUAL.md')

BASES = [
    'frontend/src/views', 'frontend/src/views/workspace', 'frontend/src/views/admin',
    'frontend/src/views/po', 'frontend/src/components', 'frontend/src/components/cards',
    'frontend/src/utils', 'frontend/src/stores', 'frontend/src/api', 'frontend/src/router',
    'frontend/src', 'frontend', 'backend/apps', 'backend', '',
]
PAT = re.compile(r'([A-Za-z0-9_/\-]+\.(?:vue|py|js|cjs|json|md)):(\d+)(?:[-,](\d+))?')


def resolve(name):
    direct = os.path.join(ROOT, name)
    if os.path.exists(direct):
        return direct
    for base in BASES:
        p = os.path.join(ROOT, base, name) if base else os.path.join(ROOT, name)
        if os.path.exists(p):
            return p
    for p in glob.glob(os.path.join(ROOT, 'backend', 'apps', '*', name)):
        return p
    for p in glob.glob(os.path.join(ROOT, 'backend', 'apps', '*', 'api', 'v1', name)):
        return p
    hits = [h for h in glob.glob(os.path.join(ROOT, '**', os.path.basename(name)), recursive=True)
            if 'node_modules' not in h and '/venv/' not in h]
    return hits[0] if hits else None


def main():
    kw = None
    if '--grep' in sys.argv:
        kw = sys.argv[sys.argv.index('--grep') + 1]
    text = io.open(DOC, encoding='utf-8').read()
    lines = text.split('\n')

    # 文档行号 → 该行的引用
    rows = []
    for i, l in enumerate(lines, 1):
        for m in PAT.finditer(l):
            rows.append((i, m.group(1), int(m.group(2)), m.group(3)))

    seen = set()
    for docln, name, start, end in rows:
        key = (name, start, end)
        if key in seen:
            continue
        seen.add(key)
        if kw and kw not in text.split('\n')[docln - 1]:
            continue
        path = resolve(name)
        if not path:
            print(f'✗ doc:{docln}  {name}:{start}  [解析失败]')
            continue
        src = io.open(path, encoding='utf-8', errors='replace').read().split('\n')
        rel = os.path.relpath(path, ROOT).replace('\\', '/')
        print(f'── doc:{docln}  {rel}:{start}{"-"+end if end else ""}')
        # 引用上下文：文档里那句话（截断）
        claim = lines[docln - 1].strip()
        print(f'   主张: {claim[:150]}')
        a = max(1, start - 1)
        b = min(len(src), int(end) if end else start + 1)
        for n in range(a, b + 1):
            mark = '>>' if n == start else '  '
            print(f'   {mark}{n:>5}: {src[n-1].rstrip()[:130]}')
        print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
