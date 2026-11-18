"""A-017 回归测试：目录价不得为负（与阶梯价同口径）。

复现路径（修复前实测成立）：
  产品编辑页保存 SKU，`price` 交给 `SKUCreateSerializer`。
  该序列化器此前**没有任何 min_value / validator**，模型 `SKU.price` 也没有，
  所以 `-100.00` 能一路落库。生产实测 SKU 963 = `-5.00`（已按 A-017 修正为 0.00）。

修复：抽出 `MONEY_MIN / MONEY_MAX_DIGITS / MONEY_DECIMAL_PLACES` 三个常量，
`SKUCreateSerializer.price` 与 `SkuTierItemSerializer.unit_price` 共用同一套口径。

本测试锁住四条不变式：
  1. 负数 ⇒ 400，且消息是人话（不能只给 "invalid"）
  2. 0 ⇒ 合法（生产有 3 条 0 价 SKU，代表"待定价"，不得误伤）
  3. 省略 price ⇒ 合法（模型 default=0 生效，保持原行为）
  4. 校验失败时**不得留下半写数据**（产品与 SKU 要么都不建，要么都不改）
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.commerce.tests.factories import ProductFactory, SKUFactory


class SkuPriceNonNegativeTest(TestCase):
    """目录价下限校验（接口层）"""

    def setUp(self):
        self.client = APIClient()
        self.staff = UserFactory(is_staff=True)
        self.client.force_authenticate(user=self.staff)

    # ---------- helpers ----------

    def _error_envelope(self, resp):
        """取统一信封里的错误体。

        ★ 本项目所有接口走统一信封 `{success, data, meta:{error:{code,
          message, details}}}`，**不是** DRF 默认的顶层 `errors` 键。
          早期这里按 `resp.json()['errors']` 断言 ⇒ 读到的是整个 body、
          断言必然失败，会让人误判成"校验没生效"。
        """
        body = resp.json()
        self.assertIn('meta', body, f'响应不是统一信封：{body}')
        meta = body['meta']
        self.assertIsInstance(meta, dict, f'meta 不是对象：{meta}')
        self.assertIn('error', meta, f'meta 里没有 error：{meta}')
        return meta['error']

    def _error_text(self, resp):
        """把信封错误压成一段可搜索的文本（message + details）。"""
        err = self._error_envelope(resp)
        return f"{err.get('code', '')} | {err.get('message', '')} | {err.get('details', '')}"

    def _create_payload(self, price, catalog_no='SC-PRICE-001'):
        return {
            'name': 'Price Guard Product',
            'slug': 'price-guard-product',
            'catalog_no': catalog_no,
            'cas': '1927-31-7',
            'smiles': 'CCO',
            'status': 'draft',
            'skus': [
                {'sku_code': f'{catalog_no}-1', 'pack_size': '100mg',
                 'price': price, 'is_default': True},
            ],
        }

    def _put_payload(self, product, price):
        return {
            'name': product.name,
            'slug': product.slug,
            'catalog_no': product.catalog_no,
            'cas': '1927-31-7',
            'smiles': 'CCO',
            'status': product.status,
            'skus': [
                {'sku_code': product.skus.first().sku_code,
                 'pack_size': '100mg', 'price': price, 'is_default': True},
            ],
        }

    # ---------- 1. 负数必须被拒 ----------

    def test_create_with_negative_price_rejected(self):
        """新建产品带 -5.00 ⇒ 400，且错误指向 price 字段"""
        resp = self.client.post(
            '/api/v1/products/', self._create_payload('-5.00'), format='json',
        )
        self.assertEqual(resp.status_code, 400, resp.content)

        err = self._error_envelope(resp)
        self.assertEqual(err.get('code'), 'validation_error', err)
        # 必须指到 price 上，否则前端无法把红字挂到对应输入框
        self.assertIn('price', err.get('message', ''), err)
        self.assertIn('skus', err.get('message', ''), err)

    def test_update_existing_sku_to_negative_rejected(self):
        """把已有 SKU 的价改成 -100.00 ⇒ 400，且库里仍是原价（不留半写）"""
        product = ProductFactory(
            name='Price Guard Existing', catalog_no='SC-PRICE-002', status='draft',
        )
        sku = SKUFactory(product=product, sku_code='SC-PRICE-002-1',
                         price=Decimal('12.34'), is_default=True)

        resp = self.client.put(
            f'/api/v1/products/{product.pk}/',
            self._put_payload(product, '-100.00'),
            format='json',
        )
        self.assertEqual(resp.status_code, 400, resp.content)

        sku.refresh_from_db()
        self.assertEqual(sku.price, Decimal('12.34'),
                         '校验失败后原价被改动 —— 出现了半写')

    # ---------- 2. 错误消息必须是人话 ----------

    def test_negative_price_message_is_readable(self):
        """400 的消息必须能让人看懂，不能只给 "invalid" """
        resp = self.client.post(
            '/api/v1/products/', self._create_payload('-1.00', 'SC-PRICE-003'),
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        body = self._error_text(resp)
        self.assertIn('价格不能为负', body,
                      f'错误消息不明确，实际返回：{body[:300]}')

    # ---------- 3. 0 与省略都合法 ----------

    def test_zero_price_allowed(self):
        """0 是合法的"待定价"占位，不得被拦"""
        resp = self.client.post(
            '/api/v1/products/', self._create_payload('0.00', 'SC-PRICE-004'),
            format='json',
        )
        self.assertIn(resp.status_code, (200, 201), resp.content)

    def test_omitted_price_allowed(self):
        """不传 price ⇒ 走模型 default=0，保持原行为"""
        payload = self._create_payload('0.00', 'SC-PRICE-005')
        del payload['skus'][0]['price']
        resp = self.client.post('/api/v1/products/', payload, format='json')
        self.assertIn(resp.status_code, (200, 201), resp.content)

    # ---------- 4. 阶梯价同口径（锁住既有行为，防回退）----------

    def test_tier_negative_unit_price_rejected(self):
        """阶梯价 unit_price=-1 ⇒ 400（与目录价共用 MONEY_MIN）"""
        product = ProductFactory(
            name='Tier Guard', catalog_no='SC-PRICE-006', status='draft',
        )
        sku = SKUFactory(product=product, sku_code='SC-PRICE-006-1',
                         price=Decimal('10.00'), is_default=True)

        resp = self.client.put(
            f'/api/v1/skus/{sku.pk}/price-tiers/',
            {'tiers': [{'min_qty': 10, 'unit_price': '-1.00'}]},
            format='json',
        )
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('价格不能为负', self._error_text(resp))


class MoneyConstantSingleSourceTest(TestCase):
    """防线：两处金额口径必须引用同一常量，不许再各写各的。"""

    def test_both_serializers_use_shared_min(self):
        from apps.commerce.api.v1.serializers import (
            MONEY_MIN, SKUCreateSerializer, SkuTierItemSerializer,
        )
        self.assertEqual(SKUCreateSerializer().fields['price'].min_value, MONEY_MIN)
        self.assertEqual(
            SkuTierItemSerializer().fields['unit_price'].min_value, MONEY_MIN)
