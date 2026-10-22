#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""角色能力探针 —— 用**真实权限类**对**真实端点**求值，产出「身份 × 端点」判定矩阵（2026-10-22）

## 为什么不能用 curl 逐个试
本仓库有 335 个 path×method。用 HTTP 试要造 token、要保证 FK 存在（否则 403/404 分不清）、
还要对付 `ALLOWED_HOSTS`、`EnvelopeRenderer`、分页等噪音。一次跑完 8 个身份 × 335 端点
= 2680 次请求，且**结论会被数据状态污染**（对象不存在时 404 看起来像"权限过了"）。

本脚本改为**在权限层求值**：
  对每个端点，实例化真实视图 → `get_permissions()` 拿到**真实权限类实例**
  → 用伪造的 `request`（`method` + `user`）调用每个实例的 `has_permission()`
  → 全部通过 = 该身份可调用。

## 它证明什么、不证明什么
**证明**：`has_permission` 层（视图级）的准入判定 —— 也就是 403 与"进得去"的分界。
**不证明**：
  ① `has_object_permission`（对象级，如 `AddressPermission` 的机构隔离）—— 需真实对象，本脚本标 `obj_level`
  ② queryset 收窄（`get_queryset` 按 `organization_id` 过滤）—— 权限过了但**看不到数据**
  ③ 前端守卫 —— 那是另一层，见 `frontend/src/utils/internalAccess.js`
  ④ 业务前置条件（比如 checkout 要购物车非空）—— 权限过了仍可能 400

⇒ 所以本脚本的输出是**上界**：说"可调用"不代表"能成功"，只说"不会被 403 挡在门外"。
   反过来，"被拒"是**确定**的（权限类不通过，后面什么都发生不了）。

## 用法
  python scripts/role_capability_probe.py                 # 打印矩阵摘要
  python scripts/role_capability_probe.py --json out.json # 落盘，供文档引用
  python scripts/role_capability_probe.py --identity procurement --denied   # 看某身份被拒清单
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
BACKEND = os.path.join(PROJECT_ROOT, 'backend')
OUT_DEFAULT = os.path.join(PROJECT_ROOT, 'docs', 'e2e', 'ROLE_CAPABILITY_MATRIX.json')

WRITE_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}


def _setup_django():
    sys.path.insert(0, BACKEND)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
    import django
    django.setup()


# ---------------------------------------------------------------- 身份定义
# 每个身份只设**数据库里真实存在**的字段组合；不臆造字段。
IDENTITIES = [
    ('anon',         dict(anonymous=True)),
    ('unverified',   dict(role='researcher', email_verified=False)),
    ('researcher',   dict(role='researcher', email_verified=True)),
    ('org_admin',    dict(role='researcher', email_verified=True, is_org_admin=True)),
    ('procurement',  dict(role='procurement', email_verified=True, is_staff=False)),
    ('admin_role',   dict(role='admin', email_verified=True, is_staff=False)),
    ('staff',        dict(role='researcher', email_verified=True, is_staff=True)),
    ('superuser',    dict(role='admin', email_verified=True, is_staff=True, is_superuser=True)),
]


def _make_user(spec):
    from django.contrib.auth.models import AnonymousUser
    if spec.get('anonymous'):
        return AnonymousUser()
    from apps.accounts.models import User
    u = User(
        username='probe',
        email='probe@example.com',
        role=spec.get('role', 'researcher'),
        email_verified=spec.get('email_verified', True),
        is_org_admin=spec.get('is_org_admin', False),
        is_staff=spec.get('is_staff', False),
        is_superuser=spec.get('is_superuser', False),
        is_active=True,
    )
    return u


# ---------------------------------------------------------------- 端点枚举
def _perm_instances(view):
    """返回 (instances, dynamic)。走真实 get_permissions()，拿实例不是名字。"""
    try:
        perms = view.get_permissions()
        return list(perms), False
    except Exception:                                  # noqa: BLE001
        return [], True


def collect():
    """返回 [{path, method, view, permissions:[名], unrestricted, dynamic}]"""
    from django.urls import get_resolver, URLPattern, URLResolver
    from rest_framework.test import APIRequestFactory
    from django.contrib.auth.models import AnonymousUser

    factory = APIRequestFactory()
    rows = []

    def walk(patterns, prefix=''):
        for p in patterns:
            if isinstance(p, URLResolver):
                walk(p.url_patterns, prefix + str(p.pattern))
                continue
            if not isinstance(p, URLPattern):
                continue
            callback = p.callback
            cls = getattr(callback, 'cls', None)
            if cls is None:
                continue                                   # 非 DRF 视图（admin/static）不在权限体系内
            actions = getattr(callback, 'actions', None)
            initkwargs = getattr(callback, 'initkwargs', None) or {}
            route = '/' + (prefix + str(p.pattern)).lstrip('/')

            init_perms = initkwargs.get('permission_classes')

            def build(act=None):
                if init_perms is not None:
                    return [c() if isinstance(c, type) else c for c in init_perms], False
                try:
                    view = cls()
                    view.request = factory.get('/')
                    view.request.user = AnonymousUser()
                    view.kwargs = {}
                    view.format_kwarg = None
                    if act is not None:
                        view.action = act
                    return _perm_instances(view)
                except Exception:                          # noqa: BLE001
                    declared = getattr(cls, 'permission_classes', None) or []
                    return [c() if isinstance(c, type) else c for c in declared], True

            if actions:
                for method, act in sorted(actions.items()):
                    insts, dyn = build(act)
                    rows.append({
                        'path': route, 'method': method.upper(),
                        'view': f'{cls.__module__}.{cls.__name__}', 'action': act,
                        'permissions': [i.__class__.__name__ for i in insts],
                        'dynamic': dyn, 'instances': insts,
                    })
            else:
                insts, dyn = build(None)
                allowed = getattr(cls, 'http_method_names', None) or [
                    'get', 'post', 'put', 'patch', 'delete', 'head', 'options']
                for m in allowed:
                    if m in ('options', 'trace', 'head'):
                        continue
                    if not hasattr(cls, m):
                        continue                            # 没实现 ⇒ 405，与权限无关
                    rows.append({
                        'path': route, 'method': m.upper(),
                        'view': f'{cls.__module__}.{cls.__name__}', 'action': None,
                        'permissions': [i.__class__.__name__ for i in insts],
                        'dynamic': dyn, 'instances': insts,
                    })

    walk(get_resolver().url_patterns)

    seen, out = set(), []
    for r in sorted(rows, key=lambda x: (x['path'], x['method'])):
        key = (r['path'], r['method'])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


# ---------------------------------------------------------------- 求值
def evaluate(rows, user, method):
    """对某身份求值一个端点。返回 (allowed, blocker)。"""
    from rest_framework.test import APIRequestFactory
    req = APIRequestFactory().generic(method, '/')
    req.user = user
    insts = rows['instances']
    if not insts:
        return True, None                                  # 未声明 ⇒ DRF 默认 AllowAny
    for inst in insts:
        try:
            ok = inst.has_permission(req, None)
        except Exception as exc:                            # noqa: BLE001
            return None, f'{inst.__class__.__name__}:EXC({exc.__class__.__name__})'
        if not ok:
            return False, inst.__class__.__name__
    return True, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', nargs='?', const=OUT_DEFAULT, default=None)
    ap.add_argument('--identity', default=None, help='只看某身份')
    ap.add_argument('--denied', action='store_true', help='列出被拒端点')
    args = ap.parse_args()

    _setup_django()
    rows = collect()

    users = {name: _make_user(spec) for name, spec in IDENTITIES}
    results = {}
    for name, _spec in IDENTITIES:
        u = users[name]
        per = []
        for r in rows:
            ok, blocker = evaluate(r, u, r['method'])
            per.append({
                'path': r['path'], 'method': r['method'], 'view': r['view'],
                'permissions': r['permissions'], 'dynamic': r['dynamic'],
                'allowed': ok, 'blocker': blocker,
                'write': r['method'] in WRITE_METHODS,
            })
        results[name] = per

    # 汇总
    summary = {}
    for name, _spec in IDENTITIES:
        per = results[name]
        write = [x for x in per if x['write']]
        read = [x for x in per if not x['write']]
        blocked_by = {}
        for x in per:
            if x['allowed'] is False and x['blocker']:
                blocked_by[x['blocker']] = blocked_by.get(x['blocker'], 0) + 1
        summary[name] = {
            'total': len(per),
            'read_ok': sum(1 for x in read if x['allowed'] is True),
            'read_total': len(read),
            'write_ok': sum(1 for x in write if x['allowed'] is True),
            'write_total': len(write),
            'unknown': sum(1 for x in per if x['allowed'] is None),
            'blocked_by': dict(sorted(blocked_by.items(), key=lambda kv: -kv[1])),
        }

    # 打印
    hdr = f"{'身份':<12}{'总端点':>7}{'读通过':>10}{'写通过':>10}{'未知':>6}"
    print(hdr)
    print('-' * len(hdr))
    for name, _ in IDENTITIES:
        s = summary[name]
        print(f"{name:<12}{s['total']:>7}"
              f"{s['read_ok']:>5}/{s['read_total']:<4}"
              f"{s['write_ok']:>5}/{s['write_total']:<4}"
              f"{s['unknown']:>6}")

    print('\n各身份被拒的主因（权限类: 端点数）')
    for name, _ in IDENTITIES:
        s = summary[name]
        if s['blocked_by']:
            top = ', '.join(f'{k}:{v}' for k, v in list(s['blocked_by'].items())[:5])
            print(f'  {name:<12} {top}')
        else:
            print(f'  {name:<12} (无被拒)')

    if args.identity:
        name = args.identity
        if name not in results:
            print(f'!! 未知身份 {name}，可选：{", ".join(n for n, _ in IDENTITIES)}')
            return 2
        print(f'\n=== {name} 明细 ===')
        for x in results[name]:
            if args.denied and x['allowed'] is not False:
                continue
            mark = {True: 'PASS', False: 'DENY', None: '????'}[x['allowed']]
            why = f"  <- {x['blocker']}" if x['blocker'] else ''
            print(f"  {mark}  {x['method']:<6}{x['path']}{why}")

    if args.json:
        payload = {
            'generated_at': __import__('datetime').datetime.now().isoformat(timespec='seconds'),
            'note': 'has_permission 层求值；不含 has_object_permission / queryset 收窄 / 前端守卫',
            'endpoint_count': len(rows),
            'identities': {n: s for n, s in summary.items()},
            'detail': {n: results[n] for n, _ in IDENTITIES},
        }
        os.makedirs(os.path.dirname(args.json), exist_ok=True)
        with open(args.json, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f'\n已写入 {args.json}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
