#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 flow_coverage_matrix.py 生成的矩阵表注入 GLOBAL_TEST_PLAN_V3.md 的 <<FLOW_MATRIX>> 占位处。"""
import io
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, 'docs', 'e2e', 'GLOBAL_TEST_PLAN_V3.md')


def main():
    out = subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', 'flow_coverage_matrix.py'), '--md'],
                         capture_output=True, text=True, encoding='utf-8')
    if out.returncode != 0:
        print('生成失败：', out.stderr[:400])
        return 2
    table = out.stdout.strip()

    s = io.open(DOC, encoding='utf-8').read()
    if '<<FLOW_MATRIX>>' not in s:
        print('文档里没有 <<FLOW_MATRIX>> 占位符（可能已注入过），跳过')
        return 0
    s = s.replace('<<FLOW_MATRIX>>', table)
    io.open(DOC, 'w', encoding='utf-8', newline='').write(s)
    print('已注入矩阵（%d 行）' % len(table.split('\n')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
