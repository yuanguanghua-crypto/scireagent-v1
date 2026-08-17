"""S4 数据迁移服务：把历史 `featured`（虚假"编辑精选"徽标）重标为 `weak`。

- 仅作用于 `tier='featured'` 行；`document`/`literature`/`weak` 不动。
- 幂等：重复调用返回 0，且零删除（铁律①）。
- 供迁移 `0004_*` 的 RunPython 与测试复用，逻辑单一来源。
"""
from apps.bridges.models import ProductProtocol


def relabel_featured_to_weak(queryset=None):
    """把 tier='featured' 重标为 'weak'，返回受影响行数。

    不传 queryset 时作用于全表。零删除：仅 UPDATE tier 列。
    """
    qs = queryset if queryset is not None else ProductProtocol.objects.all()
    return qs.filter(tier=ProductProtocol.Tier.FEATURED).update(
        tier=ProductProtocol.Tier.WEAK
    )
