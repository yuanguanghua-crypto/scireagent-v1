"""A-101 回归测试：归档（回收站）产品不得出现在前台读路径。

为什么单独立一条：`archived` 不是「status 的一个取值」，而是**回收站**语义。
生产实测 141 条产品里 **114 条是「archived=True 且 status='active'」**
（归档只把行移进回收站，不改 status）。因此任何只按 `status='active'` 过滤、
不显式排除 `archived` 的读路径，都会把回收站产品端出去；
而公开详情端点对 archived 返回 404 ⇒ 用户看到的是「列表里有、点进去没有」。

本文件锁住三条真实读路径（2026-11-18 修复前均会漏）：
  1. 产品详情页「相关产品」（`services/related_products.py`）
  2. 产品详情聚合的 related（`services/product_relationship_service.py`）
  3. 应用/协议/方法详情里的 `products` 列表（`knowledge/api/v1/serializers.py`）

每条都配一个**对照组**：非归档产品必须仍在结果里 —— 否则「过滤过头」也能让测试变绿。
"""
from django.test import TestCase

from apps.bridges.models import MethodProtocol, ProductMethod
from apps.commerce.services.product_relationship_service import (
    get_related_products as get_related_via_relationship,
)
from apps.commerce.services.related_products import get_related_products
from apps.commerce.tests.factories import ProductClassFactory, ProductFactory
from apps.knowledge.api.v1.serializers import (
    ApplicationDetailSerializer,
    MethodDetailSerializer,
    ProtocolDetailSerializer,
)
from apps.knowledge.models import Protocol
from apps.knowledge.tests.factories import (
    ApplicationFactory,
    MethodFactory,
    ProtocolFactory,
    ResearchGoalFactory,
)


class ArchivedProductExcludedFromReadPathsTest(TestCase):
    def setUp(self):
        self.pc = ProductClassFactory(name='Read Path Class')

        # 主角：前台可见的在售产品
        self.live = ProductFactory(
            name='Live Product', slug='live-product', catalog_no='SC-A101-LIVE',
            status='active', archived=False, product_class=self.pc,
        )
        # 对照：回收站产品，**status 仍是 active**（这正是生产 114 条的形态）
        self.gone = ProductFactory(
            name='Archived Product', slug='archived-product', catalog_no='SC-A101-GONE',
            status='active', archived=True, product_class=self.pc,
        )
        self.assertFalse(self.gone.archived is False, '前置：gone 必须是 archived=True')
        self.assertEqual(self.gone.status, 'active', '前置：gone 的 status 必须仍是 active')

        # 两条产品共享同一个方法 ⇒ 三个读路径都会命中它们
        self.goal = ResearchGoalFactory(name='Read Path Goal')
        self.app = ApplicationFactory(name='Read Path App', research_goal=self.goal)
        self.method = MethodFactory(name='Read Path Method', application=self.app)
        self.protocol = ProtocolFactory(name='Read Path Protocol')

        ProductMethod.objects.create(product=self.live, method=self.method)
        ProductMethod.objects.create(product=self.gone, method=self.method)
        MethodProtocol.objects.create(method=self.method, protocol=self.protocol)

    # ---------- 1. 产品详情「相关产品」 ----------

    def test_related_products_excludes_archived(self):
        rows = get_related_products(self.live, limit=10)
        ids = {p.id for p in rows}
        self.assertNotIn(self.gone.id, ids, '回收站产品出现在前台「相关产品」里')
        self.assertIn(self.live.id, ids | {self.live.id}, '前置自检')

    def test_related_products_still_returns_live_siblings(self):
        """对照组：同分类的在售产品必须仍在（防过滤过头把功能滤没了）"""
        sibling = ProductFactory(
            name='Live Sibling', slug='live-sibling', catalog_no='SC-A101-SIB',
            status='active', archived=False, product_class=self.pc,
        )
        ids = {p.id for p in get_related_products(self.live, limit=10)}
        self.assertIn(sibling.id, ids, '在售同分类产品被误滤掉了')

    # ---------- 2. 聚合详情的 related ----------

    def test_relationship_service_excludes_archived(self):
        rows = get_related_via_relationship(self.live, limit=10)
        ids = {r['id'] for r in rows}
        self.assertNotIn(self.gone.id, ids, '回收站产品出现在聚合详情的 related 里')

    def test_relationship_service_still_returns_live_siblings(self):
        sibling = ProductFactory(
            name='Live Sibling 2', slug='live-sibling-2', catalog_no='SC-A101-SIB2',
            status='active', archived=False, product_class=self.pc,
        )
        ids = {r['id'] for r in get_related_via_relationship(self.live, limit=10)}
        self.assertIn(sibling.id, ids, '在售同分类产品被误滤掉了')

    # ---------- 3. 应用 / 协议 / 方法详情里的 products ----------

    def _product_ids(self, serializer_cls, obj):
        data = serializer_cls(obj).data
        return {p['id'] for p in data.get('products', [])}

    def test_application_products_excludes_archived(self):
        ids = self._product_ids(ApplicationDetailSerializer, self.app)
        self.assertIn(self.live.id, ids, '在售产品从应用详情里消失了')
        self.assertNotIn(self.gone.id, ids, '回收站产品出现在应用详情的产品列表里')

    def test_protocol_products_excludes_archived(self):
        ids = self._product_ids(ProtocolDetailSerializer, self.protocol)
        self.assertIn(self.live.id, ids, '在售产品从协议详情里消失了')
        self.assertNotIn(self.gone.id, ids, '回收站产品出现在协议详情的产品列表里')

    def test_method_products_excludes_archived(self):
        ids = self._product_ids(MethodDetailSerializer, self.method)
        self.assertIn(self.live.id, ids, '在售产品从方法详情里消失了')
        self.assertNotIn(self.gone.id, ids, '回收站产品出现在方法详情的产品列表里')
