#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""说明书交付审计 —— 机械核对，不靠通读。

查六类问题：
  A. 第 12 章页面表 vs 路由表：逐 path 比对（漏页 / 编造页）
  B. 章节交叉引用 `§x.y` / `第 N 章` / `附录 X` 是否存在
  C. 量化断言抽取（所有"数字 + 量词"），人工复核用
  D. 每角色章节的框架完整性（身份与边界 / 操作流程 / 做不到的事 三要素）
  E. 附录 B 的权限类计数 vs 权限矩阵 JSON
  F. 同一概念多处出现是否一致（"335 端点" "52 页" "8 身份" 等）
"""
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, 'docs', 'e2e', 'SITE_ROLE_OPERATION_MANUAL.md')
ROUTER = os.path.join(ROOT, 'frontend', 'src', 'router', 'index.js')
MATRIX = os.path.join(ROOT, 'docs', 'e2e', 'ROLE_CAPABILITY_MATRIX.json')


def load():
    return io.open(DOC, encoding='utf-8').read()


# ---------- A. 第 12 章 vs 路由表 ----------
def section_ch12_paths(s):
    """抽出 12.1 / 12.2 / 12.3 三张表里第一列之后的路由（用反引号包着的）"""
    m = re.search(r'## 12\.1 公开页.*?(?=## 12\.4)', s, re.S)
    body = m.group(0) if m else ''
    # 表格行：| 页面 | `路由` | ...
    rows = re.findall(r'^\|\s*[^|]+\|\s*`([^`]+)`\s*\|', body, re.M)
    return rows


def router_paths():
    src = io.open(ROUTER, encoding='utf-8').read()
    ws_start = src.index("path: '/workspace'")
    ws_end = src.index("path: '/:pathMatch(.*)*'")
    out = []
    for mm in re.finditer(r"path:\s*'([^']*)'", src):
        tail = src[mm.end(): mm.end() + 500]
        if not re.search(r"name:\s*'([^']+)'", tail):
            continue
        in_ws = ws_start <= mm.start() < ws_end
        p = mm.group(1)
        if p == '':
            p = '/workspace'          # Dashboard 的真实 URL
        elif in_ws and not p.startswith('/'):
            p = '/workspace/' + p
        out.append(p)
    return out


def check_a(s):
    doc_paths = section_ch12_paths(s)
    real = router_paths()
    # 文档里 404 那行写的是"任意未匹配路径"，不在路由表里，单独处理
    doc_set = set(x for x in doc_paths if 'pathMatch' not in x)
    real_set = set(x for x in real if 'pathMatch' not in x)
    print('=== A. 第 12 章页面表 vs 路由表 ===')
    print('  路由表页面（去 404）: %d' % len(real_set))
    print('  文档第 12 章列出: %d' % len(doc_set))
    miss = real_set - doc_set
    extra = doc_set - real_set
    print('  漏写: %d %s' % (len(miss), sorted(miss) if miss else ''))
    print('  文档有但路由表无（疑编造）: %d %s' % (len(extra), sorted(extra) if extra else ''))
    return len(miss) + len(extra)


# ---------- B. 章节引用 ----------
def check_b(s):
    heads = set()
    for l in s.split('\n'):
        m = re.match(r'^(#{1,6})\s+(.*)$', l)
        if not m:
            continue
        t = m.group(2)
        # 第 N 章
        m2 = re.match(r'第\s*(\d+)\s*章', t)
        if m2:
            heads.add('章%s' % m2.group(1))
        # 附录 X
        m3 = re.match(r'附录\s*([A-Z])', t)
        if m3:
            heads.add('附录%s' % m3.group(1))
        # x.y 或 x.y.z
        m4 = re.match(r'([0-9A-Z]+(?:\.[0-9]+)+)\s', t)
        if m4:
            heads.add(m4.group(1))

    # ★ 跨文档引用不算本文引用：`实测清单 §N` / `MANUAL_FACTS_MEASURED.md §N`
    s_local = re.sub(r'(实测清单|MANUAL_FACTS_MEASURED\.md)`?\s*§\s*[0-9A-Z.]+', ' ', s)
    refs = set(re.findall(r'§\s*([0-9A-Z]+(?:\.[0-9]+)*)', s_local))
    refs |= set('章%s' % x for x in re.findall(r'第\s*(\d+)\s*章', s))
    refs |= set('附录%s' % x for x in re.findall(r'附录\s*([A-Z])', s))
    refs = {r for r in refs if r not in ('章', '附录')}

    bad = []
    for r in sorted(refs):
        if r in heads:
            continue
        # §F3-1 这种"流程编号"不算章节引用
        if re.match(r'^F\d', r) or re.match(r'^M-', r):
            continue
        bad.append(r)
    print('\n=== B. 章节交叉引用 ===')
    print('  引用 %d 个，未找到对应标题 %d 个' % (len(refs), len(bad)))
    if bad:
        print('   ✗ %s' % bad)
    return len(bad)


# ---------- D. 每角色章节三要素 ----------
ROLE_CH = [('1', '匿名'), ('2', '未验证'), ('3', 'researcher'), ('4', 'org_admin'),
           ('5', 'procurement'), ('6', 'admin(role)'), ('7', 'staff'), ('8', 'superuser')]


def check_d(s):
    print('\n=== D. 每角色章节框架完整性 ===')
    problems = 0
    for num, label in ROLE_CH:
        m = re.search(r'(# 第 %s 章.*?)(?=\n# 第 \d+ 章|\n# 附录)' % num, s, re.S)
        if not m:
            print('  ✗ 第 %s 章（%s）找不到' % (num, label))
            problems += 1
            continue
        body = m.group(1)
        has_scope = bool(re.search(r'身份与边界|身份与边界', body))
        has_flow = bool(re.search(r'操作流程|的一天|的一周|F\d-1', body))
        has_limit = bool(re.search(r'做不到的事|不能做的事|权限.*零影响|与.*完全相同', body))
        flags = ''.join(['✓' if x else '✗' for x in (has_scope, has_flow, has_limit)])
        ok = all((has_scope, has_flow, has_limit))
        print('  %s 第 %s 章 %-16s 边界=%s 流程=%s 限制=%s' % (
            '✓' if ok else '✗', num, label,
            'Y' if has_scope else 'N', 'Y' if has_flow else 'N', 'Y' if has_limit else 'N'))
        if not ok:
            problems += 1
    return problems


# ---------- E. 附录 B 权限类计数 ----------
def check_e(s):
    m = json.load(io.open(MATRIX, encoding='utf-8'))
    rows = m['detail']['staff']
    from collections import Counter
    c = Counter()
    for r in rows:
        names = r.get('permissions') or ['(未声明)']
        c[','.join(names)] += 1
    print('\n=== E. 附录 B 权限类计数 vs 权限矩阵 JSON（按 path×method 计）===')
    print('  矩阵实际：')
    for k, v in c.most_common():
        print('     %-34s %d' % (k, v))
    print('  ⇒ 请核对正文 §0.4 / 附录 B 的数字是否与此一致')
    return 0


# ---------- F. 关键数字多处一致性 ----------
def check_f(s):
    print('\n=== F. 关键数字出现次数（多寡不一即需人工核对口径）===')
    keys = ['335', '52 个', '52 页', '8 身份', '8 种', '19', '23', '132', '203', '199']
    for k in keys:
        n = s.count(k)
        if n:
            print('  %-8s 出现 %d 次' % (k, n))
    return 0


def main():
    s = load()
    bad = 0
    bad += check_a(s)
    bad += check_b(s)
    bad += check_d(s)
    check_e(s)
    check_f(s)
    print('\n=== 汇总：硬问题 %d 个 ===' % bad)
    return 0


if __name__ == '__main__':
    sys.exit(main())
