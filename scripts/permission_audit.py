#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""L7 权限闸门 —— 枚举**全站每个端点实际生效的权限类**（2026-10-21）

## 为什么需要它
本仓库 **没有** 在 settings 里声明 `DEFAULT_PERMISSION_CLASSES` ⇒ DRF 落回默认
`AllowAny`。也就是说：**任何一个忘记写 `permission_classes` 的视图 = 匿名可访问**。
这不是假设，已真实发生过：`commerce/api/v1/views.py` 的 `SKUViewSet` 曾因此
「匿名可写 SKU」，靠人工发现才补上（见该文件 2026-09-24 的注释）。

grep 数 `permission_classes` 出现次数**证明不了安全**：
  · 写在 `@action(permission_classes=[...])` 里（grep 得到，但归属要算到具体方法）
  · 写在 `get_permissions()` 里动态返回（grep 得到，但静态读不出结果）
  · 视图通过 `as_view()` 的 initkwargs 传（grep 完全看不见）
  · `permission_classes = []`（空列表在 DRF 里等价于"没有任何限制"⇒ 放行）
所以本脚本**实例化真实视图类**去读 `get_permissions()`，而不是看图源文本。

## 判据
- **P0**：`AllowAny`（含 `[]`、含未声明）且接受**写方法**（POST/PUT/PATCH/DELETE）
  ⇒ 匿名可写。这是能直接出事的。
- **P1**：`AllowAny` 但只读（GET/HEAD/OPTIONS）
  ⇒ 需人工确认"它本来就该公开"（商品目录、搜索等确实该公开）。
- **INFO**：需要认证的端点，仅列出便于核对。

## 动态权限
`get_permissions()` 无法静态求值时会标 `dynamic`，并**强制要求**在
`docs/e2e/PERMISSION_BASELINE.json` 里人工签名（`reviewed` 字段），
否则 CI FAIL —— 避免"读不出就当没问题"。

## 用法
  python scripts/permission_audit.py                  # 审计并打印
  python scripts/permission_audit.py --json out.json  # 落盘
  python scripts/permission_audit.py --update         # 刷新基线（会保留已有 reviewed 签名）
  python scripts/permission_audit.py --check          # CI 模式：新增 P0/P1 即 FAIL
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
BACKEND = os.path.join(PROJECT_ROOT, 'backend')
BASELINE = os.path.join(PROJECT_ROOT, 'docs', 'e2e', 'PERMISSION_BASELINE.json')

WRITE_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}
READ_METHODS = {'GET', 'HEAD', 'OPTIONS'}

# "没有任何限制"的权限类名（DRF 里 AllowAny 恒返回 True）
UNRESTRICTED = {'AllowAny', 'ScopedRateThrottle'}


def _setup_django():
    sys.path.insert(0, BACKEND)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
    import django
    django.setup()


def _perm_names(perms) -> list[str]:
    out = []
    for p in perms or []:
        if isinstance(p, str):
            out.append(p)
        else:
            out.append(getattr(p, '__name__', p.__class__.__name__))
    return out


def _is_unrestricted(names: list[str]) -> bool:
    """空列表 = 无任何 permission ⇒ DRF 视为全放行；全是 AllowAny 同理。"""
    if not names:
        return True
    return all(n.split('.')[-1] in UNRESTRICTED for n in names)


def _resolve_view(callback):
    """从 URL callback 取出 (view_cls, actions, initkwargs)。"""
    cls = getattr(callback, 'cls', None)
    actions = getattr(callback, 'actions', None)
    initkwargs = getattr(callback, 'initkwargs', None) or {}
    return cls, actions, initkwargs


def _implemented_methods(cls) -> list[str]:
    """类**真正实现**了哪些方法。

    ★ 这是本脚本最容易出错的地方（第一版就在这里过度上报）：
      `http_method_names` 只是"**允许**哪些方法"，DRF `dispatch()` 的逻辑是
      `handler = getattr(self, method.lower(), self.http_method_not_allowed)`
      —— 类里**没写** `put` ⇒ 恒 405，**与权限无关**。
      只看 http_method_names 会把"只实现 post 的登录页"报成 4 个匿名可写端点。
      ⇒ 必须 `hasattr(cls, method)`。
    """
    if cls is None:
        return []
    allowed = getattr(cls, 'http_method_names', None) or [
        'get', 'post', 'put', 'patch', 'delete', 'head', 'options'
    ]
    out = []
    for m in allowed:
        if m in ('options', 'trace', 'head'):
            continue                       # OPTIONS/TRACE/HEAD 由 DRF 自动生成，不反映业务写口
        if hasattr(cls, m):
            out.append(m.upper())
    return sorted(out)


def _effective_permissions(cls, initkwargs, actions_subset=None):
    """实例化视图读 get_permissions()；失败则退回类属性。返回 (names, dynamic)。"""
    dynamic = False
    # 1) as_view(permission_classes=[...]) 优先（DRF ViewSetMixin.setup 会覆盖）
    init_perms = initkwargs.get('permission_classes')
    if init_perms is not None:
        return _perm_names(init_perms), False

    if cls is None:
        return [], True

    # 2) 类属性（含 @action(permission_classes=...) 由 ViewSetMixin 注入到 self.permission_classes）
    declared = getattr(cls, 'permission_classes', None)

    # 3) 是否覆写了 get_permissions —— 覆写则必须实际调用
    #    ★ 不能只看 `cls.__dict__`：override 可能写在**父类**里（本仓库的 EnvelopeMixin 就是混入基类）。
    try:
        from rest_framework.views import APIView as _DRFAPIView
        base_impl = _DRFAPIView.get_permissions
    except Exception:                          # noqa: BLE001
        base_impl = None
    has_override = getattr(cls, 'get_permissions', None) is not base_impl

    if not has_override:
        if declared is None:
            return [], False       # 未声明 ⇒ Django/DRF 默认 AllowAny
        return _perm_names(declared), False

    # 实际实例化，调用 get_permissions()。需要伪造最少的 request。
    try:
        from rest_framework.test import APIRequestFactory
        from django.contrib.auth.models import AnonymousUser

        factory = APIRequestFactory()
        request = factory.get('/')
        view = cls()
        view.request = request
        view.request.user = AnonymousUser()
        view.kwargs = {}
        view.format_kwarg = None
        if actions_subset is not None:
            view.action = actions_subset
        perms = view.get_permissions()
        return _perm_names(perms), False
    except Exception as exc:                     # noqa: BLE001
        # 读不出来不是"没问题"，必须转成 dynamic 让人签字
        names = _perm_names(declared) if declared is not None else []
        _ = exc
        dynamic = True
        return names, dynamic


def collect():
    from django.urls import get_resolver, URLPattern, URLResolver

    rows = []

    def walk(patterns, prefix=''):
        for p in patterns:
            if isinstance(p, URLResolver):
                walk(p.url_patterns, prefix + str(p.pattern))
                continue
            if not isinstance(p, URLPattern):
                continue
            callback = p.callback
            cls, actions, initkwargs = _resolve_view(callback)
            if cls is None:
                # 普通函数视图（如 admin、static）—— 不属 DRF 权限体系，跳过
                continue
            route = '/' + (prefix + str(p.pattern)).lstrip('/')

            if actions:
                for method in sorted(actions.keys()):
                    action_name = actions[method]
                    names, dynamic = _effective_permissions(cls, initkwargs, action_name)
                    rows.append({
                        'path': route,
                        'method': method.upper(),
                        'view': f'{cls.__module__}.{cls.__name__}',
                        'action': action_name,
                        'permissions': names,
                        'dynamic': dynamic,
                        'unrestricted': _is_unrestricted(names),
                    })
            else:
                names, dynamic = _effective_permissions(cls, initkwargs)
                for method in _implemented_methods(cls):
                    rows.append({
                        'path': route,
                        'method': method,
                        'view': f'{cls.__module__}.{cls.__name__}',
                        'action': None,
                        'permissions': names,
                        'dynamic': dynamic,
                        'unrestricted': _is_unrestricted(names),
                    })

    walk(get_resolver().url_patterns)
    # 去重 + 稳定排序
    seen, out = set(), []
    for r in sorted(rows, key=lambda x: (x['path'], x['method'])):
        key = (r['path'], r['method'])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def classify(rows):
    for r in rows:
        if r['unrestricted'] and r['method'] in WRITE_METHODS:
            r['severity'] = 'P0'
        elif r['unrestricted']:
            r['severity'] = 'P1'
        elif r['dynamic']:
            r['severity'] = 'DYNAMIC'
        else:
            r['severity'] = 'INFO'
    return rows


def _load_baseline():
    if os.path.exists(BASELINE):
        with open(BASELINE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'reviewed': {}, 'note': ''}


def _save_baseline(data):
    os.makedirs(os.path.dirname(BASELINE), exist_ok=True)
    with open(BASELINE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write('\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', dest='json_out', default=None)
    ap.add_argument('--update', action='store_true', help='刷新基线（保留已签名的 reviewed）')
    ap.add_argument('--check', action='store_true', help='CI 模式：未签名的 P0/P1/DYNAMIC 即 FAIL')
    ap.add_argument('--verbose', action='store_true')
    args = ap.parse_args()

    _setup_django()
    rows = classify(collect())

    by_sev = {'P0': [], 'P1': [], 'DYNAMIC': [], 'INFO': []}
    for r in rows:
        by_sev[r['severity']].append(r)

    print('=' * 78)
    print('L7 权限审计 —— 全站端点实际生效的权限类')
    print('=' * 78)
    print(f'总端点数（path × method）：{len(rows)}')
    for sev in ('P0', 'P1', 'DYNAMIC', 'INFO'):
        print(f'  {sev:<8} {len(by_sev[sev])}')

    if by_sev['P0']:
        print('\n' + '-' * 78)
        print('P0 —— 匿名可写（能直接出事，必须逐条处置）')
        print('-' * 78)
        for r in by_sev['P0']:
            print(f"  {r['method']:<6} {r['path']:<52} {r['view'].split('.')[-1]}")

    if by_sev['P1']:
        print('\n' + '-' * 78)
        print('P1 —— 匿名可读（需确认"本来就该公开"）')
        print('-' * 78)
        for r in by_sev['P1']:
            print(f"  {r['method']:<6} {r['path']:<52} {r['view'].split('.')[-1]}")

    if by_sev['DYNAMIC']:
        print('\n' + '-' * 78)
        print('DYNAMIC —— get_permissions() 无法静态求值（必须人工签字）')
        print('-' * 78)
        for r in by_sev['DYNAMIC']:
            print(f"  {r['method']:<6} {r['path']:<52} {r['view'].split('.')[-1]}")

    if args.verbose:
        print('\n' + '-' * 78)
        print('INFO —— 需认证端点')
        print('-' * 78)
        for r in by_sev['INFO']:
            print(f"  {r['method']:<6} {r['path']:<52} {','.join(r['permissions'])}")

    baseline = _load_baseline()
    reviewed = baseline.get('reviewed', {})
    fp_of = lambda r: f"{r['method']} {r['path']}"        # noqa: E731

    # 需要盯的集合：P0 / P1 / DYNAMIC
    needs_sign = [r for r in rows if r['severity'] in ('P0', 'P1', 'DYNAMIC')]
    unsigned = [r for r in needs_sign if fp_of(r) not in reviewed]

    if args.update:
        new_reviewed = {}
        for r in needs_sign:
            k = fp_of(r)
            prev = reviewed.get(k, {})
            new_reviewed[k] = {
                'severity': r['severity'],
                'view': r['view'],
                # 保留既有签字：刷新基线不该把已核对过的结论抹成"未签字"
                'reviewed': prev.get('reviewed', False),
                'reason': prev.get('reason', ''),
            }
        _save_baseline({'reviewed': new_reviewed,
                        'note': 'P0/P1/DYNAMIC 端点基线。--check 只拦"新增"与"严重度升级"；'
                                '全部待办清单见 unsigned 计数。签字字段 reviewed/reason 由人填写。'})
        print(f'\n基线已刷新：{BASELINE}（{len(new_reviewed)} 条，'
              f'其中已签字 {sum(1 for v in new_reviewed.values() if v.get("reviewed"))}）')

    if args.json_out:
        with open(args.json_out, 'w', encoding='utf-8') as f:
            json.dump({'total': len(rows),
                       'summary': {k: len(v) for k, v in by_sev.items()},
                       'endpoints': rows}, f, ensure_ascii=False, indent=2)
        print(f'明细已写入：{args.json_out}')

    if args.check:
        print('\n' + '=' * 78)
        # ★ 闸门设计（棘轮，不是一次性大签字）
        #   为什么不要求"40 个端点全部 reviewed=true 才 PASS"：
        #   那样最省事的过法就是**批量把 reviewed 写成 true**，等于假签字，
        #   闸门退化成仪式。真实价值在于**拦住新增**：
        #     · 新出现的 P0（匿名可写）/ DYNAMIC（权限求值失败）⇒ FAIL
        #     · 已有端点**严重度升级**（如 P1→P0、INFO→P1）⇒ FAIL
        #   存量 P1/P0 作为可见债务列出，随处置逐条转 reviewed=true。
        _SEV_RANK = {'INFO': 0, 'P1': 1, 'P0': 2, 'DYNAMIC': 2}

        new_risky, escalated = [], []
        for r in needs_sign:
            k = fp_of(r)
            if k not in reviewed:
                # DYNAMIC 意味着"脚本读不出权限"，不能当没事 ⇒ 也算新增风险
                if r['severity'] in ('P0', 'DYNAMIC'):
                    new_risky.append(r)
                continue
            old_rank = _SEV_RANK.get(reviewed[k].get('severity', 'INFO'), 0)
            new_rank = _SEV_RANK.get(r['severity'], 0)
            if new_rank > old_rank:
                escalated.append((r, reviewed[k].get('severity')))

        unsigned_count = sum(1 for r in needs_sign if fp_of(r) not in reviewed)
        unreviewed = sum(1 for k, v in reviewed.items() if not v.get('reviewed'))

        if new_risky or escalated:
            print(f'FAIL —— 权限面出现新增风险')
            for r in new_risky:
                print(f"  [新增 {r['severity']}] {fp_of(r)}  ({r['view'].split('.')[-1]})")
            for r, old in escalated:
                print(f"  [升级 {old}→{r['severity']}] {fp_of(r)}  ({r['view'].split('.')[-1]})")
            print('\n处置：确认该端点确实该公开 → 在 PERMISSION_BASELINE.json 里登记并写 reason；')
            print('      不该公开 → 补 permission_classes 后重跑。')
            return 1

        print('PASS —— 无新增 P0/DYNAMIC、无严重度升级')
        print(f'  可见债务：基线内 {unreviewed} 条尚未人工签字'
              f'（其中 P0 {len(by_sev["P0"])} / P1 {len(by_sev["P1"])}）')
        if unsigned_count:
            print(f'  未纳入基线：{unsigned_count} 条 ⇒ 跑 --update 纳入后再逐条判定')
        return 0

    return 0


if __name__ == '__main__':
    sys.exit(main())
