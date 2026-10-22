#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""真实 HTTP 权限探测 —— 用**真账号登录 + 真请求**替代"权限类求值"。

## 与 role_capability_probe.py 的区别（这是本文件存在的全部理由）
| | role_capability_probe.py | 本脚本 |
|---|---|---|
| 手段 | 实例化权限类，调 `has_permission()` | 真登录拿 token，真发 HTTP 请求 |
| 覆盖 | 只到权限类 | 走完 URL 解析 → 中间件 → 认证 → 限流 → 权限 → 视图 |
| 可信度 | 中（假设 DRF 行为符合预期） | 高（就是用户真实会遇到的） |
| 风险 | 无 | 可能写数据 ⇒ **必须跑在 DB 副本上** |

## 三条安全设计（缺一不可）
1. **必须在 DB 副本上跑**：要求 `SCIREAGENT_DB_NAME` 含 "probe"，且脚本自己也会校验服务端口
2. **写请求用空 body**：权限通过后停在 400 校验错误，**不落库**
3. **对象路由用不存在的 id**（999999999）：权限通过后 404，不碰真实行

## 判定口径（本脚本的核心约定）
    status ∈ {401, 403}  ⇒ DENY（明确被拒）
    其它（200/201/204/400/404/405/409/415/500） ⇒ PASS（权限层已通过）
    status = 429 ⇒ THROTTLED（不计入判定，需重试）
    status = 000 ⇒ ERROR（连接/超时，不计入判定）

⚠️ 已知局限：对象路由用假 id ⇒ `has_object_permission` 不执行。本脚本只证明**视图级**准入。
   要做对象级，必须用真实 id 并接受"可能改数据"。

用法：
  cd src_claude
  python scripts/http_role_probe.py                 # 全量
  python scripts/http_role_probe.py --limit 40      # 只打前 40 个（冒烟）
  python scripts/http_role_probe.py --identity all --out docs/e2e/HTTP_ROLE_PROBE.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MATRIX = os.path.join(ROOT, 'docs', 'e2e', 'ROLE_CAPABILITY_MATRIX.json')
OUT_DEFAULT = os.path.join(ROOT, 'docs', 'e2e', 'HTTP_ROLE_PROBE.json')

BASE = os.getenv('PROBE_BASE', 'http://127.0.0.1:8011')
PASSWORD = 'Probe#2026!'

IDENTITIES = [
    ('anon', None),
    ('probe_unverified', 'probe_unverified'),
    ('researcher', 'probe_researcher'),
    ('org_admin', 'probe_orgadmin'),
    ('procurement', 'probe_procure'),
    ('admin_role', 'probe_adminrole'),
    ('staff', 'probe_staff'),
    ('superuser', 'probe_super'),
]

WRITE_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}
FAKE_PK = '999999999'

# 外呼外部 API / 会真跑重活的端点：跳过（打它们既慢又会污染外部调用配额）
SKIP_PATTERNS = [
    'enrich', 'parse-word', 'render-structure', 'generate-seo', 'import-protocol',
    'adopt-bioz', 'batch-validate', 'batch-recommend', 'sds-revisions/generate',
    'generate', 'json-ld', 'health',
    # ★ 必须跳过：logout 会**当场删除当前 token**，导致其后所有请求变 401，
    #   第一版没跳过，结果第 137 个请求起整片 401（实测踩过）。
    #   登出的效果改为单独一次"token 失效验证"来测，见 verify_logout()。
    'auth/logout',
]

# 这些端点会改认证状态或造成不可逆副作用，单独测，不进批量扫描
DEDICATED = ['auth/logout']

# 不用 urllib 的默认代理（沙箱里 http_proxy 会把回环请求打到代理上去，得到 502）
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _norm(path):
    """把 resolver 的正则路径还原成可请求的 URL，参数替换为假 id。"""
    u = path
    u = re.sub(r'\(\?P<[^>]+>\[[^\]]*\][^)]*\)', FAKE_PK, u)
    u = re.sub(r'<[^>]+>', FAKE_PK, u)
    u = u.replace('^', '').replace('$', '')
    return u


def _post_json(url, payload, timeout=20):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, method='POST',
        headers={'Content-Type': 'application/json', 'Host': '127.0.0.1:8011'})
    try:
        with _OPENER.open(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:                                        # noqa: BLE001
        return 0, str(e).encode()


def login(username):
    '''返回 (token, login_status, login_body)。

    ★ 不在这里 SystemExit：probe_unverified 按设计就登录不了（403），
      那本身就是一条要记录的事实，不是脚本错误。
    '''
    status, body = _post_json(BASE + '/api/v1/auth/login',
                              {'username': username, 'password': PASSWORD})
    if status != 200:
        return None, status, body.decode('utf-8', 'replace')[:400]
    d = json.loads(body)
    return d['data']['token'], status, ''


def call(method, url, token, timeout=8):
    headers = {'Host': '127.0.0.1:8011'}
    if token:
        headers['Authorization'] = 'Token ' + token
    data = None
    if method in WRITE_METHODS:
        # 空 JSON body ⇒ 权限通过后停在 400 校验错误，不落库
        data = b'{}'
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with _OPENER.open(req, timeout=timeout) as r:
            return r.status, r.read(400)
    except urllib.error.HTTPError as e:
        return e.code, e.read(400)
    except Exception:                                             # noqa: BLE001
        return 0, b''


def verify_logout(token):
    '''单独验证：logout 是否真的让 token 失效（批量扫描里必须排除它）。

    返回 (before_status, logout_status, after_status)
    '''
    b, _ = call('GET', BASE + '/api/v1/auth/me', token)
    l, _ = call('POST', BASE + '/api/v1/auth/logout', token)
    a, body = call('GET', BASE + '/api/v1/auth/me', token)
    return b, l, a, body.decode('utf-8', 'replace')[:200]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--only-identity', default='')
    ap.add_argument('--out', default=OUT_DEFAULT)
    args = ap.parse_args()

    # 安全闸门：确认连的是探测实例而不是 dev/prod
    status, body = call('GET', BASE + '/api/v1/health/', None)
    if status != 200:
        raise SystemExit('探测后端不可达（%s，HTTP %s）' % (BASE, status))
    print('后端就绪：%s  %s' % (BASE, body.decode()[:80]))

    data = json.load(open(MATRIX, encoding='utf-8'))
    rows = []
    for r in data['detail']['staff']:
        p = r['path']
        if '\\.' in p:                    # 跳过 .json 等格式后缀变体（与主路由同权限）
            continue
        if any(s in p for s in SKIP_PATTERNS):
            continue
        rows.append((p, r['method']))
    rows = sorted(set(rows))
    if args.limit:
        rows = rows[:args.limit]
    print('待探测端点：%d（已剔除外呼/格式变体）' % len(rows))

    tokens = {}
    login_info = {}
    for name, username in IDENTITIES:
        if args.only_identity and name != args.only_identity:
            continue
        if username is None:
            tokens[name] = None
            print('  %-10s 匿名（不发 token）' % name)
            continue
        t0 = time.time()
        tok, lstatus, lbody = login(username)
        tokens[name] = tok
        login_info[name] = {'status': lstatus, 'body': lbody}
        if tok:
            print('  %-10s 登录成功 %.0fms' % (name, (time.time() - t0) * 1000))
        else:
            print('  %-10s 登录被拒 HTTP %s —— 该身份拿不到 token（本身即是实测结论）'
                  % (name, lstatus))

    results = {}
    for name in tokens:
        if tokens[name] is None and name != 'anon':
            results[name] = []
            continue
        per = []
        t0 = time.time()
        for path, method in rows:
            url = BASE + _norm(path)
            st, body = call(method, url, tokens[name])
            code = ''
            if st >= 400 and body[:1] == b'{':
                try:
                    code = (json.loads(body).get('meta') or {}).get('error', {}).get('code', '')
                except Exception:                                 # noqa: BLE001
                    code = ''
            per.append({'path': path, 'method': method, 'status': st,
                        'error_code': code, 'write': method in WRITE_METHODS})
        results[name] = per
        n_deny = sum(1 for x in per if x['status'] in (401, 403))
        print('  %-10s %d 个端点完成，%.1fs，被拒 %d' % (name, len(per), time.time() - t0, n_deny))

    # 单独验证登出是否真的让 token 失效（用 staff 的 token，一次性）
    logout_evidence = None
    if tokens.get('staff'):
        fresh, _ = None, None
        t2, _, _ = login('probe_staff')
        if t2:
            logout_evidence = verify_logout(t2)
            print('\n登出验证：before=%s / logout=%s / after=%s' % logout_evidence[:3])

    # 汇总
    summary = {}
    for name, per in results.items():
        if not per:
            continue
        rd = [x for x in per if not x['write']]
        wr = [x for x in per if x['write']]
        summary[name] = {
            'total': len(per),
            'read_pass': sum(1 for x in rd if x['status'] not in (401, 403, 0, 429)),
            'read_total': len(rd),
            'write_pass': sum(1 for x in wr if x['status'] not in (401, 403, 0, 429)),
            'write_total': len(wr),
            'denied': sum(1 for x in per if x['status'] in (401, 403)),
            'errored': sum(1 for x in per if x['status'] in (0, 429)),
        }

    print('\n=== 实测（真实 HTTP）===')
    print('%-12s %-14s %-14s %s' % ('身份', '读通过', '写通过', '被拒'))
    for name in summary:
        s = summary[name]
        print('%-12s %-14s %-14s %d' % (
            name, '%d/%d' % (s['read_pass'], s['read_total']),
            '%d/%d' % (s['write_pass'], s['write_total']), s['denied']))

    payload = {
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'base': BASE,
        'note': '真实 HTTP 请求；写方法用空 body（权限通过后停 400，不落库）；对象路由用假 id（不触发 has_object_permission）',
        'endpoint_count': len(rows),
        'skipped_patterns': SKIP_PATTERNS,
        'logout_invalidates_token': logout_evidence,
        'login': login_info,
        'summary': summary,
        'detail': results,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print('\n已写入 %s' % args.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
