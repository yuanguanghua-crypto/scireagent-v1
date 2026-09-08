"""canonical Method 解析 —— P1-1 修复 P0 方法可见性回归。

背景：生产 47,834 行 Method 是 T2 补链产生的 draft（application=X, status='draft'），
P0（apply_public_visibility）把它们挡在展示面外，导致 AP 详情 / 协议详情 / 图谱覆盖率骤降。

修复：建 canonical Method 实体（status='active', application=None, 名字=高频 draft 方法名），
展示层用「名字 → canonical」解析输出 canonical 的 id/slug（可点击跳转），draft 行完整保留作溯源。

本模块提供一次性查询辅助，避免 N+1；找不到对应 canonical 的名字不会出现（宁 miss 不错配）。
"""
from django.db.models import Count

from apps.knowledge.models import Method


def canonical_by_name(names):
    """按方法名解析 canonical（已转正、active、无 application 归属）Method 实体。

    返回 {name: {'id', 'name', 'slug'}}。一次 ``name__in`` 查询，避免 N+1。
    ``names`` 为空或 None 时返回空 dict。
    """
    if not names:
        return {}
    rows = Method.objects.filter(
        status='active', application__isnull=True, name__in=names
    ).values('id', 'name', 'slug')
    return {
        row['name']: {'id': row['id'], 'name': row['name'], 'slug': row['slug']}
        for row in rows
    }


def draft_name_counts(min_count=1):
    """统计 draft Method 按名字出现次数（默认全部、>=min_count 过滤）。

    用于 build_canonical_methods 命令：识别高频 draft 方法名。
    返回 list[{'name', 'cnt'}]，按 cnt 降序。
    """
    qs = (
        Method.objects.filter(status='draft')
        .values('name')
        .annotate(cnt=Count('id'))
        .order_by('-cnt')
    )
    if min_count and min_count > 1:
        qs = qs.filter(cnt__gte=min_count)
    return list(qs)
