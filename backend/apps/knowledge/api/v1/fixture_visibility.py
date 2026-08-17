"""S1 — 测试夹具实体的对外可见性判定。

统一入口，避免各端点自行拼 filter 造成遗漏。默认一律排除；只有 staff 显式
传 ``?include_test_fixtures=1`` 时才放行（用于人工清理残骸）。
"""

_TRUTHY = {'1', 'true', 'yes', 'on'}


def include_test_fixtures(request) -> bool:
    """staff + 显式 opt-in 才返回 True。匿名/普通用户永远 False。"""
    if request is None:
        return False
    user = getattr(request, 'user', None)
    if not (user is not None and user.is_authenticated and user.is_staff):
        return False
    params = getattr(request, 'query_params', None) or getattr(request, 'GET', {})
    return str(params.get('include_test_fixtures', '')).lower() in _TRUTHY


def apply_fixture_filter(qs, request):
    """按可见性规则过滤 queryset（qs 需为 TestFixtureQuerySet）。"""
    if include_test_fixtures(request):
        return qs
    return qs.filter(is_test_fixture=False)
