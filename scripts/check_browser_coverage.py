#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""精确计算：52 个路由页里，有多少页在真实浏览器里跑过（加载级）。

覆盖来源：
  frontend/e2e/responsive.spec.cjs        —— 3 视口 × 页面清单「加载不崩」
  frontend/e2e/manual-facts-probe*.spec.cjs —— 8+3+1 个事实核验用例
"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
E2E = os.path.join(ROOT, 'frontend', 'e2e')


def routes():
    r = io.open(os.path.join(ROOT, 'frontend', 'src', 'router', 'index.js'), encoding='utf-8').read()
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


# manual-pages-smoke.spec.cjs 是数据驱动的（cases 数组 + 动态 id），
# 正则抓不到，这里显式登记它覆盖的页（改动该 spec 时必须同步维护）
PAGES_SMOKE = [
    '/about', '/privacy', '/terms', '/verify-email', '/wishlist',
    '/applications/:id', '/applications/classes/:class_id',
    '/methods/:id', '/protocols/:id',
    '/research-goals/:id', '/research-goals/classes/:class_id',
    '/ops/inventory', '/workspace/products/:id/edit',
    '/orders/:id', '/po/orders/:id',
]


def spec_paths():
    got = set()
    resp = io.open(os.path.join(E2E, 'responsive.spec.cjs'), encoding='utf-8').read()
    got |= set(re.findall(r"path:\s*'([^']+)'", resp))
    for f in ('manual-facts-probe.spec.cjs', 'manual-facts-probe2.spec.cjs',
              'manual-facts-probe3.spec.cjs'):
        p = os.path.join(E2E, f)
        if not os.path.exists(p):
            continue
        txt = io.open(p, encoding='utf-8').read()
        got |= set(re.findall(r'\$\{BASE\}(/[A-Za-z0-9/_:\-.]*)', txt))
        got |= set(re.findall(r'\$\{BASE\}(/[A-Za-z0-9/_:\-.]*\$\{[^}]*\}[A-Za-z0-9/_:\-.]*)', txt))
    got |= set(PAGES_SMOKE)
    return got


def norm(p, allp):
    if p in allp:
        return p
    for x in allp:
        # 先把动态段换成占位，再转义，最后把占位还原成正则
        tpl = x.replace(':class_id', '\x00').replace(':id', '\x01')
        rx = '^' + re.escape(tpl).replace('\x00', '[^/]+').replace('\x01', '[^/]+') + '$'
        if re.match(rx, p):
            return x
    return None


def main():
    allp = routes()
    raw = spec_paths()
    cov = set()
    unknown = []
    for p in raw:
        n = norm(p, allp)
        if n:
            cov.add(n)
        else:
            unknown.append(p)
    print('不同 URL 页数：%d' % len(allp))
    print('spec 里出现的路径（原始）：%d' % len(raw))
    print('能对上路由的：%d' % len(cov))
    print('对不上的（多为跳转后地址或子串）：%s' % sorted(unknown)[:8])
    print('\n=== 未在浏览器里跑过的页（%d）===' % (len(allp) - len(cov)))
    for p in allp:
        if p not in cov:
            print('  ', p)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
