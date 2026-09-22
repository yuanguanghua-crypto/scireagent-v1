"""S5.3：购物车「悬挂引用」在**读取侧**过滤，不做级联删除。

背景：产品软删（`archived=True`）不级联清理 `basket`（FK 是 CASCADE，但软删不触发），
于是购物车里会残留指向"已进回收站"产品的行（实测生产 5 条，全指向 SC8027）。

处置口径（S5.3）：**读取侧过滤**，行保留在库（不级联删、不改数据），
从而：① 购物车不再渲染已下架商品；② 合计金额不再把失效商品计入。
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.commerce.tests.factories import ProductFactory, SKUFactory
from apps.transactions.models import Basket


class BasketHangingRefTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.live = ProductFactory(name='Live', status='active')
        self.gone = ProductFactory(name='Gone', status='active')
        self.gone.archived = True
        self.gone.save()
        self.sku_live = SKUFactory(product=self.live, sku_code='LIVE-1')
        self.sku_gone = SKUFactory(product=self.gone, sku_code='GONE-1')
        Basket.objects.create(user=self.user, product=self.live, sku=self.sku_live, quantity=1)
        Basket.objects.create(user=self.user, product=self.gone, sku=self.sku_gone, quantity=2)

    def test_archived_product_item_not_rendered(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get('/api/v1/basket')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']          # 信封：{success, data:{items,total,count}}
        self.assertEqual(data['count'], 1, '已归档产品的购物车行不应被渲染')
        codes = [i['sku_code'] for i in data['items']]
        self.assertNotIn('GONE-1', codes)
        self.assertIn('LIVE-1', codes)

    def test_total_excludes_archived_item(self):
        """合计金额不得把已归档商品算进去。"""
        self.client.force_authenticate(user=self.user)
        data = self.client.get('/api/v1/basket').json()['data']
        # 只有 LIVE-1（99.99×1）；GONE-1（99.99×2）被过滤
        self.assertEqual(float(data['total']), 99.99)

    def test_hanging_row_is_kept_in_db(self):
        """读取侧过滤 ≠ 删数据：行必须仍在库里（不做级联删除）。"""
        self.client.force_authenticate(user=self.user)
        self.client.get('/api/v1/basket')
        self.assertEqual(Basket.objects.filter(user=self.user).count(), 2)
