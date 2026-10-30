"""`?ordering=` 的 NULLS LAST 契约（防止 PostgreSQL 的 NULLS FIRST 陷阱复发）。

## 为什么单测必须断言 SQL 而不是结果顺序

本地是 sqlite，**DESC 默认就是 NULLS LAST**；生产是 PostgreSQL，**默认 NULLS FIRST**。
所以「取回来的第一条是不是 NULL」这个问题，在 sqlite 上永远得到"正确"的答案 ——
无论代码有没有修。2026-10-30 的首页 Recent Publications bug 就是这样活了好几个月：
本地一切正常，生产首屏全是空记录。

⇒ 唯一可控的契约是**生成的 SQL 里必须显式带 NULLS LAST**。
这个断言在两种数据库上都成立，且改回裸 `order_by('-x')` 时立刻变红。

## 已发生过的两起真实事故

1. 首页 Recent Publications：`Reference.order_by('-year','-id')` ⇒ 15 条 `year=NULL`
   的记录（doi/url 也全空）占了首屏，5 条标题全都点不了。
2. 产品列表「知识关联最强」：`Product.aggregate_relevance_score` 3/127 为空，
   `?ordering=-aggregate_relevance_score` 把"没有分数"的产品排到最前，语义反了。
"""
from django.conf import settings
from django.test import TestCase
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.knowledge.models import Reference
from core.filters import NullsLastOrderingFilter


class _StubView:
    """最小 view stub：OrderingFilter 只读 ordering / ordering_fields。"""

    ordering_fields = ['year', 'title']


def _filter(query_string):
    request = Request(APIRequestFactory().get(query_string))
    return NullsLastOrderingFilter().filter_queryset(
        request, Reference.objects.all(), _StubView()
    )


class NullsLastOrderingFilterTest(TestCase):
    def test_desc_uses_nulls_last(self):
        sql = str(_filter('/?ordering=-year').query).upper()
        self.assertIn('NULLS LAST', sql)
        self.assertIn('DESC', sql)

    def test_asc_uses_nulls_last(self):
        """升序同样要 NULLS LAST —— 否则空值会顶到最前面。"""
        sql = str(_filter('/?ordering=year').query).upper()
        self.assertIn('NULLS LAST', sql)

    def test_multi_key_all_nulls_last(self):
        sql = str(_filter('/?ordering=-year,-title').query).upper()
        self.assertEqual(sql.count('NULLS LAST'), 2)

    def test_no_ordering_leaves_queryset_untouched(self):
        qs = _filter('/')
        self.assertEqual(str(qs.query), str(Reference.objects.all().query))

    def test_invalid_field_is_dropped_not_crashed(self):
        """不符合 ordering_fields 白名单的字段应被过滤掉，不抛异常。"""
        sql = str(_filter('/?ordering=-not_a_real_field').query)
        self.assertNotIn('not_a_real_field', sql.lower())

    def test_default_ordering_respected(self):
        """view.ordering（默认排序）也要走同一套 NULLS LAST。"""

        class _DefaultOrderingView:
            ordering = ['-year']
            ordering_fields = ['year', 'title']

        request = Request(APIRequestFactory().get('/'))
        qs = NullsLastOrderingFilter().filter_queryset(
            request, Reference.objects.all(), _DefaultOrderingView()
        )
        self.assertIn('NULLS LAST', str(qs.query).upper())


class GlobalBackendWiringTest(TestCase):
    """★ 防止有人把全局配置改回 stock OrderingFilter（那会让所有 API 重新踩坑）。"""

    def test_default_filter_backends_uses_nulls_last_filter(self):
        backends = settings.REST_FRAMEWORK['DEFAULT_FILTER_BACKENDS']
        self.assertIn(
            'core.filters.NullsLastOrderingFilter', backends,
            '全局 OrderingFilter 被换回了 stock 版本 —— Reference.year / '
            'Product.aggregate_relevance_score 的降序排序会在 PostgreSQL 上'
            '把空值行顶到最前',
        )
        self.assertNotIn('rest_framework.filters.OrderingFilter', backends)
