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
# status 可见性统一收口
#
# 历史（2026-09-07 用户拍板）：公开读（匿名/非 staff）一律只见公开态；
# **staff 在 API 读面看全量**。
#
# ★ 2026-10-26 变更（用户拍板方案 B，勿改回去）：
#   上述"staff 无条件看全量"造成同一个用户看到两个矛盾数字 ——
#   首页统计写死 active（Methods 93），而 /methods 列表对 staff 返回 47,927
#   （差 47,834 个 draft），点"Browse 93 →"进去显示"Total 47927"，看起来像故障。
#   现改为：**只在列表端点（list action）**让 staff 也默认过滤 status，
#   需显式 `?include_unpublished=1` 才看全量。见 MethodViewSet / ProtocolViewSet 的
#   get_queryset。本函数保持"staff 绕过"不变 —— 因为它同时服务详情/搜索/管理动作，
#   在那里把 staff 挡住会让后台看不到草稿，直接影响运营（实测会挂掉 40+ 用例）。
# ---------------------------------------------------------------------------

def is_staff_request(request) -> bool:
    """staff 判定（与 include_test_fixtures 同口径，但不要求 opt-in 参数）。"""
    if request is None:
        return False
    user = getattr(request, 'user', None)
    return user is not None and user.is_authenticated and user.is_staff


def include_unpublished(request) -> bool:
    """staff + 显式 opt-in 才返回 True（用于后台审草稿）。匿名/普通用户永远 False。"""
    if not is_staff_request(request):
        return False
    params = getattr(request, 'query_params', None) or getattr(request, 'GET', {})
    return str(params.get('include_unpublished', '')).lower() in _TRUTHY


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
    """统一公开读入口：夹具过滤 ∪ status 公开态过滤。

    对无 status 字段的模型（如 Reference）等价于 apply_fixture_filter。
    staff 默认与访客同口径（见文件头 2026-10-26 变更说明）。
    """
    if hasattr(model, 'is_test_fixture'):
        qs = apply_fixture_filter(qs, request)
    statuses = public_statuses(model)
    if statuses and not is_staff_request(request):
        qs = qs.filter(status__in=statuses)
    return qs
