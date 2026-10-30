"""全局 REST framework 过滤器扩展。

## 为什么需要 NullsLastOrderingFilter

DRF 的 `OrderingFilter` 把 `?ordering=-x` 直接交给 `order_by('-x')`，
而 **PostgreSQL 的 DESC 默认是 `NULLS FIRST`**（NULL 当最大值）
⇒ 只要该字段 `null=True`，空值行就会被顶到结果最前面。

本项目已经因此踩过两次：

1. **首页 Recent Publications**（2026-10-30 用户报「标题点不了」）
   `Reference.order_by('-year', '-id')` ⇒ 15 条 `year` 为 NULL 的记录占了首屏，
   而它们恰好 `doi`/`url` 也全空，整条不可点击。
2. **产品列表「知识关联最强」排序**
   `Product.aggregate_relevance_score` 有 3/127 为空（本地实测），
   `?ordering=-aggregate_relevance_score` 会把这 3 个「没有分数」的产品排到最前 ——
   语义上完全反了。

### ★ 为什么单测抓不到

**本地 sqlite 的 DESC 默认是 `NULLS LAST`**（NULL 当最小值），
`order_by('-year')` 在 sqlite 上取到的正好是有值的那几条，看起来完全正常。
只有 PostgreSQL 上才暴露。

⇒ 所以本模块的测试**不能只断言结果顺序**，必须断言生成的 SQL 里带
`NULLS LAST`（见 `tests/test_nulls_last_ordering.py`）—— 那是平台无关的契约。

## 实现要点

只改「NULL 排哪」，不动字段合法性校验：
仍先走 `super().get_ordering()`（它内部已做 `ordering_fields` 白名单校验 +
`remove_invalid_fields` 过滤），再重建表达式。

用 `F(name).desc(nulls_last=True)` 而不是字符串 `'-name'`，
这样 Django 会在 SQL 里显式生成 `NULLS LAST`，两种数据库语义一致。
"""
from django.db.models import F
from rest_framework.filters import OrderingFilter


class NullsLastOrderingFilter(OrderingFilter):
    """把 `?ordering=` 生成的排序统一改为 NULLS LAST。"""

    def filter_queryset(self, request, queryset, view):
        ordering = self.get_ordering(request, queryset, view)
        if not ordering:
            return queryset

        terms = []
        for term in ordering:
            descending = term.startswith('-')
            name = term[1:] if descending else term
            expr = F(name)
            terms.append(
                expr.desc(nulls_last=True) if descending
                else expr.asc(nulls_last=True)
            )
        return queryset.order_by(*terms)
