#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""核算 E2E 覆盖：78 个 spec 到底访问了说明书里的哪些页面。

方法：扫描 `frontend/e2e/*.spec.cjs` 里的导航语句，抓路径 → 归一化到 52 个路由 → 统计。
抓三种写法：
  page.goto('${BASE}/products')
  page.goto(BASE_URL + '/orders')
  page.goto('/login')            （少数用相对路径）
  page.locator('a[href="/x"]').click()  （不作为主判据）

输出：每页被哪些 spec 访问 + 未覆盖清单。
"""
import io
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
E2E = os.path.join(ROOT, 'frontend', 'e2e')
ROUTER = os.path.join(ROOT, 'frontend', 'src', 'router', 'index.js')


def routes():
    r = io.open(ROUTER, encoding='utf-8').read()
    a = r.index("path: '/workspace'")
    b = r.index("path: '/:pathMatch(.*)*'")
    out = []
    for m in re.finditer(r"path:\s*'([^']*)'", r):
        if not re.search(r"name:\s*'", r[m.end():m.end() + 500]):
            continue
        p = m.group(1)
        inp = a <= m.start() < b
        if p == '':
            p = '/workspace'
        elif inp and not p.startswith('/'):
            p = '/workspace/' + p
        if 'pathMatch' in p:
            continue
        out.append(p)
    return sorted(set(out))


NAV_PATTERNS = [
    # 直连式
    re.compile(r"goto\(\s*`\$\{(?:BASE|BASE_URL|base)\}([^`]*)`"),
    re.compile(r"goto\(\s*(?:BASE|BASE_URL|base)\s*\+\s*'([^']*)'"),
    re.compile(r"goto\(\s*'([^']*)'"),
    # 数据驱动式（responsive.spec 用 `path:` 字段）
    re.compile(r"path:\s*'([^']+)'"),
    # 数据驱动式（manual-pages-smoke 用 visit(page, '/x') 与 cases 数组）
    re.compile(r"visit\(\s*page\s*,\s*'([^']+)'"),
    re.compile(r"`([/][a-z0-9/:._-]*)`", re.I),
]


def norm(p, allp):
    if not p.startswith('/'):
        p = '/' + p
    p = p.split('?')[0].split('#')[0]
    if len(p) > 1 and p.endswith('/'):
        p = p[:-1]
    if p in allp:
        return p
    for x in allp:
        tpl = x.replace(':class_id', '\x00').replace(':id', '\x01')
        rx = '^' + re.escape(tpl).replace('\x00', '[^/]+').replace('\x01', '[^/]+') + '$'
        if re.match(rx, p):
            return x
    return None


def main():
    allp = routes()
    hits = defaultdict(set)
    files = sorted(f for f in os.listdir(E2E) if f.endswith('.spec.cjs'))
    for f in files:
        txt = io.open(os.path.join(E2E, f), encoding='utf-8').read()
        for pat in NAV_PATTERNS:
            for m in pat.finditer(txt):
                p = m.group(1)
                if not p or '${' in p:
                    continue
                r = norm(p, allp)
                if r:
                    hits[r].add(f)

    # manual-pages-smoke 的页面清单是数据驱动的字符串数组，正则抓不全 ⇒ 直接用它自己的清单
    try:
        sys.path.insert(0, HERE)
        from check_browser_coverage import PAGES_SMOKE
        for p in PAGES_SMOKE:
            hits[p].add('manual-pages-smoke.spec.cjs')
    except Exception:                                             # noqa: BLE001
        print('!! 未能读取 PAGES_SMOKE，覆盖率可能偏低')

    print('=== E2E 页面覆盖（%d 个 spec）===' % len(files))
    covered = [p for p in allp if p in hits]
    uncovered = [p for p in allp if p not in hits]
    print('覆盖 %d/%d 页，未覆盖 %d' % (len(covered), len(allp), len(uncovered)))
    print('\n--- 未覆盖 ---')
    for p in uncovered:
        print('  ', p)
    print('\n--- 覆盖明细（页 ← spec 数）---')
    for p in covered:
        print('  %-40s %d 个 spec：%s' % (p, len(hits[p]), ', '.join(sorted(hits[p])[:3])))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
