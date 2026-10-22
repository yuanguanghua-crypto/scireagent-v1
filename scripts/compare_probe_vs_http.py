#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""比对「静态权限求值」与「真实 HTTP 请求」的逐端点判定，找出不一致。

输入：
  docs/e2e/ROLE_CAPABILITY_MATRIX.json   权限类求值（allowed: true/false）
  docs/e2e/HTTP_ROLE_PROBE.json          真实 HTTP（status: 401/403 视为 DENY）

输出：每个身份的不一致清单 + 全局统计。
不一致有两类，含义完全不同：
  · eval=PASS / http=DENY  ⇒ 静态低估了限制（可能是对象级权限、或令牌/会话要求）
  · eval=DENY / http=PASS  ⇒ **静态高估了限制**（求值结论偏保守，或该方法根本没走到权限类）
"""
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL = os.path.join(ROOT, 'docs', 'e2e', 'ROLE_CAPABILITY_MATRIX.json')
HTTP = os.path.join(ROOT, 'docs', 'e2e', 'HTTP_ROLE_PROBE.json')
OUT = os.path.join(ROOT, 'docs', 'e2e', 'PROBE_VS_HTTP_DIFF.json')


def norm(p):
    u = p
    if u.startswith('/api/v1'):
        u = u[len('/api/v1'):]
    u = re.sub(r'\(\?P<[^>]+>\[[^\]]*\][^)]*\)', '*', u)
    u = re.sub(r'<[^>]+>', '*', u)
    u = u.replace('^', '').replace('$', '')
    if len(u) > 1 and u.endswith('/'):
        u = u[:-1]
    return u


def main():
    ev = json.load(io.open(EVAL, encoding='utf-8'))
    ht = json.load(io.open(HTTP, encoding='utf-8'))

    # 求值侧：{(身份, 归一化路径, method): allowed}
    ev_idx = {}
    for ident, rows in ev['detail'].items():
        for r in rows:
            ev_idx[(ident, norm(r['path']), r['method'])] = r['allowed']

    report = {}
    totals = {'compared': 0, 'agree': 0, 'eval_pass_http_deny': 0, 'eval_deny_http_pass': 0}

    for ident, rows in ht['detail'].items():
        if not rows:
            report[ident] = {'compared': 0, 'mismatch': [], 'note': '该身份未能登录，无 HTTP 数据'}
            continue
        mism = []
        compared = 0
        for r in rows:
            key = (ident, norm(r['path']), r['method'])
            if key not in ev_idx:
                continue
            compared += 1
            http_pass = r['status'] not in (401, 403, 0, 429)
            eval_pass = bool(ev_idx[key])
            if http_pass == eval_pass:
                totals['agree'] += 1
                continue
            kind = 'eval_pass_http_deny' if eval_pass else 'eval_deny_http_pass'
            totals[kind] += 1
            mism.append({
                'path': r['path'], 'method': r['method'],
                'eval': eval_pass, 'http_status': r['status'],
                'kind': kind, 'error_code': r.get('error_code', ''),
            })
        totals['compared'] += compared
        report[ident] = {'compared': compared, 'mismatch': mism}

    print('=== 静态求值 vs 真实 HTTP ===')
    print('可比对端点次数：%d  一致 %d  不一致 %d' % (
        totals['compared'], totals['agree'],
        totals['eval_pass_http_deny'] + totals['eval_deny_http_pass']))
    print('  · 求值说 PASS 但真打被拒：%d' % totals['eval_pass_http_deny'])
    print('  · 求值说 DENY 但真打通过：%d' % totals['eval_deny_http_pass'])

    for ident, r in report.items():
        n = len(r['mismatch'])
        print('\n%s：比对 %d，不一致 %d' % (ident, r['compared'], n))
        # 按类型分组展示前 8 条
        for kind in ('eval_pass_http_deny', 'eval_deny_http_pass'):
            sub = [m for m in r['mismatch'] if m['kind'] == kind]
            if not sub:
                continue
            print('   [%s] %d 条' % (kind, len(sub)))
            for m in sub[:8]:
                print('      %-6s %-52s http=%s %s' % (
                    m['method'], m['path'], m['http_status'], m['error_code']))

    json.dump({'totals': totals, 'by_identity': report},
              io.open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('\n已写入 %s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
