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


# ---------------------------------------------------------------------------
# P0 — status 可见性统一收口（用户拍板 2026-09-07）：
# 公开读（匿名/非 staff）一律只见公开态；staff 在 API 读面看全量。
# D2：graph 端点一律公开口径（request 传 None 即不放行 staff）。
# ---------------------------------------------------------------------------

def is_staff_request(request) -> bool:
    """staff 判定（与 include_test_fixtures 同口径，但不要求 opt-in 参数）。"""
    if request is None:
        return False
    user = getattr(request, 'user', None)
    return user is not None and user.is_authenticated and user.is_staff


def public_statuses(model):
    """模型 → 公开态集合；无 status 字段的模型返回 None（不过滤）。

    Protocol 用 published（自有 PublicationStatus），其余知识实体用 active。
    """
    name = model.__name__.lower()
    if name in {'researchgoal', 'application', 'method'}:
        return ['active']
    if name == 'protocol':
        return ['published']
    if name == 'product':
        return ['active', 'published']
    return None


def apply_public_visibility(qs, model, request):
    """统一公开读入口：夹具过滤 ∪ status 公开态过滤，staff 绕过 status 过滤。

    对无 status 字段的模型（如 Reference）等价于 apply_fixture_filter。
    """
    if hasattr(model, 'is_test_fixture'):
        qs = apply_fixture_filter(qs, request)
    statuses = public_statuses(model)
    if statuses and not is_staff_request(request):
        qs = qs.filter(status__in=statuses)
    return qs
