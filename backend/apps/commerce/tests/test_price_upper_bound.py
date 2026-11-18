"""A-048 / A-208 回归测试：目录价必须有**合理上限**。

### 两条是同一现象（S1 入口核对时发现，建议合并）

| 条目 | 级别 | 原文位置 | 复现 |
|---|---|---|---|
| A-048 | P2 | PRODUCTS > Edit Product（5454，SKU 价格） | 改成 99999999 保存重载 ⇒ 成功显示 99999999.00 |
| A-208 | P1 | PRODUCTS > Edit Product（5454）> SKU | 5454 SKU `TEST-20261110-03-A` 原 -5.00 改 99999999 ⇒ 成功持久化 |

**同产品、同 SKU、同数值 99999999**，A-048 是 Batch 5、A-208 是 Batch 16 复测同一件事。
⇒ 并入一条，按 P1（A-208 级别更高）计。

### 上限取值依据（改前查现状，铁律）

2026-11-18 生产只读实测：
- SKU 共 **50** 条，`price` 区间 **0.00 ~ 989.00**；`>100000` 为 **0** 条，`>1000000` 为 **0** 条
- `SkuPriceTier` 共 **69** 条，`unit_price` 最高 **899.00**

⇒ 取 **1,000,000**（`MONEY_MAX`）作为上限：比现有最高值大 **1000 倍**，
既能挡住 99999999 这类明显误输，又不会把任何既有数据打回。

### 本测试锁住
1. 99999999 / 1000000.01 ⇒ 400，消息是人话（含"上限"），且**不留半写**
2. 边界内（0 / 989 / 999999.99 / 1000000）⇒ 通过
3. 阶梯价 `unit_price` 同口径（共用 `MONEY_MAX`，不许各写各的）
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.commerce.tests.factories import ProductFactory, SKUFactory


class PriceUpperBoundTest(TestCase):
    """目录价上限校验（接口层）"""

    def setUp(self):
        self.client = APIClient()
        self.staff = UserFactory(is_staff=True)
        self.client.force_authenticate(user=self.staff)

    # ---------- helpers（与 test_price_non_negative.py 同口径）----------

    def _error_text(self, resp):
        body = resp.json()
        self.assertIn('meta', body, f'响应不是统一信封：{body}')
        err = body['meta'].get('error') or {}
        return f"{err.get('code', '')} | {err.get('message', '')} | {err.get('details', '')}"

    def _create_payload(self, price, catalog_no='SC-CAP-001'):
        return {
            'name': 'Price Cap Product',
            # slug 必须随 catalog_no 变，否则同用例内第二次创建会撞 slug 唯一约束
            'slug': f'price-cap-{catalog_no.lower()}',
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

    # ---------- 1. 超上限必须被拒（A-048 / A-208 的原值）----------

    def test_create_with_99999999_rejected(self):
        """A-048/A-208 的原始复现值 99999999 ⇒ 400"""
        resp = self.client.post(
            '/api/v1/products/', self._create_payload('99999999'), format='json',
        )
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_update_existing_sku_beyond_cap_rejected_and_no_partial_write(self):
        """把已有 SKU 改成 99999999 ⇒ 400，库里仍是原价（不留半写）"""
        product = ProductFactory(
            name='Price Cap Existing', catalog_no='SC-CAP-002', status='draft',
        )
        sku = SKUFactory(product=product, sku_code='SC-CAP-002-1',
                         price=Decimal('12.34'), is_default=True)

        resp = self.client.put(
            f'/api/v1/products/{product.pk}/',
            self._put_payload(product, '99999999'),
            format='json',
        )
        self.assertEqual(resp.status_code, 400, resp.content)

        sku.refresh_from_db()
        self.assertEqual(sku.price, Decimal('12.34'),
                         '校验失败后原价被改动 —— 出现了半写')

    def test_over_cap_message_is_readable(self):
        """400 的消息必须说清是"超上限"，不能只给 invalid"""
        resp = self.client.post(
            '/api/v1/products/', self._create_payload('1000000.01', 'SC-CAP-003'),
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('上限', self._error_text(resp),
                      f'消息没说明上限，实际：{self._error_text(resp)[:300]}')

    # ---------- 2. 边界内必须通过（防过滤过头）----------

    def test_boundary_values_accepted(self):
        """0 / 989（生产最高）/ 999999.99 / 1000000（含边界）都合法"""
        for i, price in enumerate(('0.00', '989.00', '999999.99', '1000000')):
            resp = self.client.post(
                '/api/v1/products/',
                self._create_payload(price, f'SC-CAP-1{i:02d}'),
                format='json',
            )
            self.assertIn(resp.status_code, (200, 201),
                          f'价格 {price} 被误拦：{resp.content}')

    # ---------- 3. 阶梯价同口径 ----------

    def test_tier_unit_price_over_cap_rejected(self):
        """阶梯价 unit_price=99999999 ⇒ 400（与目录价共用 MONEY_MAX）"""
        product = ProductFactory(
            name='Tier Cap', catalog_no='SC-CAP-020', status='draft',
        )
        sku = SKUFactory(product=product, sku_code='SC-CAP-020-1',
                         price=Decimal('10.00'), is_default=True)

        resp = self.client.put(
            f'/api/v1/skus/{sku.pk}/price-tiers/',
            {'tiers': [{'min_qty': 10, 'unit_price': '99999999'}]},
            format='json',
        )
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('上限', self._error_text(resp))


class MoneyMaxConstantSingleSourceTest(TestCase):
    """防线：上限只能有一个来源，两处金额字段必须引用它。"""

    def test_shared_max_constant(self):
        from apps.commerce.api.v1.serializers import (
            MONEY_MAX, SKUCreateSerializer, SkuTierItemSerializer,
        )
        self.assertEqual(MONEY_MAX, Decimal('1000000'))
        self.assertEqual(SKUCreateSerializer().fields['price'].max_value, MONEY_MAX)
        self.assertEqual(
            SkuTierItemSerializer().fields['unit_price'].max_value, MONEY_MAX)
