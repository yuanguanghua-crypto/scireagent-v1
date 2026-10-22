#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""校验文档内锚点链接：目录里写的 #xxx 是否与某个标题的 slug 一致。

slug 规则按 GitHub：小写、空格→-、去掉标点（保留中文与字母数字），重复标题加 -1。
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, 'docs', 'e2e', 'SITE_ROLE_OPERATION_MANUAL.md')


def slug(title):
    t = title.strip().lower()
    # 去掉反引号、*、链接语法等
    t = re.sub(r'[`*]', '', t)
    t = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', t)
    # 去掉除中日韩、字母数字、空格、连字符之外的字符
    t = re.sub(r'[^\w\u4e00-\u9fff\- ]', '', t)
    t = t.replace(' ', '-')
    t = re.sub(r'-{2,}', '-', t).strip('-')
    return t


def main():
    s = io.open(DOC, encoding='utf-8').read()
    lines = s.split('\n')

    # 收集标题 slug
    slugs = set()
    for l in lines:
        m = re.match(r'^(#{1,6})\s+(.*)$', l)
        if m:
            slugs.add(slug(m.group(2)))

    # 收集文档内链接
    links = re.findall(r'\]\(#([^)]+)\)', s)
    bad = []
    for l in links:
        if l not in slugs:
            bad.append(l)

    print('标题数 %d，内部链接 %d，失效 %d' % (len(slugs), len(links), len(bad)))
    import difflib
    for b in sorted(set(bad)):
        near = difflib.get_close_matches(b, list(slugs), n=1, cutoff=0.4)
        print('  ✗ #%s   → 最近似: #%s' % (b, near[0] if near else '(无)'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
