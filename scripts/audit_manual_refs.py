#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""审计 SITE_ROLE_OPERATION_MANUAL.md 里所有 `file:line` 引用是否真实存在。

只解决一件事：**引用的文件在不在、行号在不在范围内、那一行是什么**。
不判断语义是否匹配（那要人读），但把"行号溢出/文件不存在/解析到多个候选"这三类硬错误一次扫出来。
"""
import io
import os
import re
import sys
import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, 'docs', 'e2e', 'SITE_ROLE_OPERATION_MANUAL.md')

# 引用里的文件名可能是"裸文件名"，按这些前缀依次尝试解析
BASES = [
    'frontend/src/views',
    'frontend/src/views/workspace',
    'frontend/src/views/admin',
    'frontend/src/views/po',
    'frontend/src/components',
    'frontend/src/components/cards',
    'frontend/src/utils',
    'frontend/src/stores',
    'frontend/src/api',
    'frontend/src/router',
    'frontend/src',
    'frontend',
    'backend/apps',
    'backend',
    '',
]

PAT = re.compile(r'([A-Za-z0-9_/\-]+\.(?:vue|py|js|cjs|json|md)):(\d+)(?:[-,](\d+))?')


def resolve(name):
    """返回 (path, candidates)"""
    cands = []
    # 1) 已经是相对仓库根的路径
    direct = os.path.join(ROOT, name)
    if os.path.exists(direct):
        return direct, [direct]
    # 2) 按前缀找
    for base in BASES:
        p = os.path.join(ROOT, base, name) if base else os.path.join(ROOT, name)
        if os.path.exists(p):
            cands.append(p)
    # 2b) backend/apps/<app>/ 下（app 名未写全的情况，如 models.py / services.py / views.py）
    if not cands:
        for p in glob.glob(os.path.join(ROOT, 'backend', 'apps', '*', name)):
            cands.append(p)
        for p in glob.glob(os.path.join(ROOT, 'backend', 'apps', '*', 'api', 'v1', name)):
            cands.append(p)
    if len(cands) == 1:
        return cands[0], cands
    if len(cands) > 1:
        return None, cands
    # 3) 全局兜底：按文件名搜
    hits = glob.glob(os.path.join(ROOT, '**', os.path.basename(name)), recursive=True)
    hits = [h for h in hits if 'node_modules' not in h and '/venv/' not in h]
    if len(hits) == 1:
        return hits[0], hits
    return None, hits


def main():
    text = io.open(DOC, encoding='utf-8').read()
    lines = text.split('\n')

    # 先算每个引用出现在文档第几行（便于回改）
    doc_lineno = {}
    for i, l in enumerate(lines, 1):
        for m in PAT.finditer(l):
            doc_lineno.setdefault(m.group(0), []).append(i)

    missing = []
    overflow = []
    ambiguous = []
    ok = 0

    seen = set()
    for m in PAT.finditer(text):
        name, start, end = m.group(1), int(m.group(2)), m.group(3)
        key = (name, start, end)
        if key in seen:
            continue
        seen.add(key)
        path, cands = resolve(name)
        if path is None:
            (ambiguous if cands else missing).append((name, start, cands[:3], doc_lineno.get(m.group(0))))
            continue
        try:
            n = len(io.open(path, encoding='utf-8', errors='replace').read().split('\n'))
        except Exception as exc:                                   # noqa: BLE001
            missing.append((name, start, [f'读失败:{exc}'], doc_lineno.get(m.group(0))))
            continue
        if start > n or (end and int(end) > n):
            overflow.append((name, start, end, n, doc_lineno.get(m.group(0))))
        else:
            ok += 1

    print(f'唯一引用 {len(seen)} 条：解析成功 {ok}')
    print(f'\n[A] 文件找不到 {len(missing)} 条')
    for x in missing:
        print(f'   {x[0]}:{x[1]}  文档行{x[3]}  候选{x[2]}')
    print(f'\n[B] 行号越界 {len(overflow)} 条')
    for x in overflow:
        print(f'   {x[0]}:{x[1]}{"-"+x[2] if x[2] else ""}  文件仅{x[3]}行  文档行{x[4]}')
    print(f'\n[C] 有歧义（同名文件多处） {len(ambiguous)} 条')
    for x in ambiguous:
        print(f'   {x[0]}:{x[1]}  文档行{x[3]}  候选{len(x[2])}: {[os.path.relpath(c, ROOT) for c in x[2]]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
