"""count_as_listed — Dashboard 计数的单一入口。

## 为什么需要这个文件

A-002 的现场：同一个实体，Dashboard 显示 11045、列表页显示 11036。
根因不是"少算/多算"，而是**两处各写了一套查询**：

    Dashboard：`ResearchGoal.objects.count()`            ← 裸 count，什么都没过滤
    列表页   ：`apply_public_visibility(...)` + list action 的 status 过滤

## 各实体的列表口径**本来就不一致**（2026-11-18 实测归因）

| 实体 | 列表端点实际过滤 | 差值来源 |
|---|---|---|
| ResearchGoal  | fixture（staff 仍看全量） | 9 条 fixture |
| Application   | fixture（staff 仍看全量） | 6 条 fixture |
| Method        | fixture + status（方案 B，2026-10-26） | 3 条 draft |
| Protocol      | fixture + status（方案 B，2026-10-26） | 88 条 draft |

⇒ 所以这里**按模型分流**，而不是追求"四实体哲学统一"：
   拿掉列表页已有的 status 过滤是行为回退（运营会看不到草稿）；
   给 Goals/Applications 加 status 过滤同样会改变运营可见面。
   本函数只保证 **Dashboard 与它对应的列表页永远同源**，不动任何列表行为。

## 纪律

任何新增的"总数"展示，都必须调本模块。禁止再写 `Model.objects.count()`。
"""

from apps.knowledge.api.v1.fixture_visibility import (
    apply_public_visibility,
    include_unpublished,
    public_statuses,
)

# 采用「方案 B」的实体：列表端点对 staff 也默认过滤 status。
# 2026-10-26 用户拍板，见 fixture_visibility.py 文件头。改动此集合等于改行为，需拍板。
_LIST_FILTERS_STATUS = {'method', 'protocol'}


def list_visible_queryset(qs, model, request):
    """列表端点口径的 queryset（供 ViewSet 与 Dashboard 共用，防止再次漂移）。

    对 `_LIST_FILTERS_STATUS` 里的模型追加 status 公开态过滤；其余仅走
    统一的夹具/可见性入口。`?include_unpublished=1` 时 staff 可看全量。
    """
    qs = apply_public_visibility(qs, model, request)
    if model.__name__.lower() in _LIST_FILTERS_STATUS and not include_unpublished(request):
        statuses = public_statuses(model)
        if statuses:
            qs = qs.filter(status__in=statuses)
    return qs


def count_as_listed(model, request=None, base_qs=None):
    """Dashboard 用：返回「该实体列表页此刻会显示多少条」。

    参数:
        model: 知识实体模型类
        request: 列表端点的 request（staff / 匿名口径由此决定）；None 视为匿名
        base_qs: 可选，替换 `model.objects.all()`（如 Goals 需带 prefetch/order）
    """
    qs = base_qs if base_qs is not None else model.objects.all()
    return list_visible_queryset(qs, model, request).count()
