"""A-179 回归测试：RFQ 明细数量必须 ≥ 1，且不得是荒谬值。

### 原文（v4 PDF 明细）
- **A-179**（P1）：数量 0 不拦截，直接提交生成 RFQ #14
- 位置：`/cart → /quote-request`
- 复现：将商品数量改为 0，其余必填项填妥后点击提交
- 预期：数量 0 被拦截并提示
- 实际：未出现任何验证提示，直接提交成功生成 RFQ #14

### 根因（代码实测）
`QuoteRequestItem.quantity = models.IntegerField(default=1)` —— **模型层无任何 validator**；
`QuoteRequestItemSerializer` 是裸 `ModelSerializer`，`quantity` 直接透传 ⇒ 0 与负数都能落库。
（购物车侧 `basket_serializers.py` 三个入口早已有 `min_value=1`，
 唯独 RFQ 这条写入路径没有 ⇒ 是**同一业务量的两套口径**。）

### 现状实测（2026-11-18 生产只读）
`QuoteRequestItem` 共 **14** 条，`quantity` 区间 **1 ~ 2**，`≤0` 为 **0** 条，`>999` 为 **0** 条
⇒ 加下限不会打回任何既有数据。

### ⚠️ 上限为什么不套购物车的 999
购物车是「零售包装自助下单」，999 是包装数量上限；
RFQ 是**批量询价**入口，前端 `QuoteRequestPage.vue:179` 的数量输入只有 `min="1"`、
根本没有 max —— 客户填 5000 支来问价是正常业务。
把 999 硬套到 RFQ 会拒掉真实批量询价，属"修一个 bug 引入另一个 bug"。
⇒ 只设荒谬值护栏（100 万），业务上不构成限制。

### 本测试锁住
1. 0 / 负数 / 荒谬值（1000001）⇒ 400，且**整体不落库**（不留半个询价单）
2. 1 / 999 / 5000（真实批量）/ 1000000（含边界）/ 缺省 ⇒ 通过；缺省落库为模型默认 1
3. 下限与购物车同值（`min_value=1`）；上限**刻意不同**，并有注释说明原因
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.commerce.tests.factories import ProductFactory
from apps.quotes.models import QuoteRequest, QuoteRequestItem

URL = '/api/v1/quote-requests/'


class RfqItemQuantityTest(TestCase):
    """RFQ 明细数量校验"""

    def setUp(self):
        self.client = APIClient()
        self.product = ProductFactory()

    def _payload(self, quantity, with_field=True):
        item = {'product_id': self.product.id}
        if with_field:
            item['quantity'] = quantity
        return {
            'contact_name': 'Dr. Qty',
            'contact_email': 'qty@lab.edu',
            'items': [item],
        }

    def _error_text(self, resp):
        body = resp.json()
        self.assertIn('meta', body, f'响应不是统一信封：{body}')
        err = body['meta'].get('error') or {}
        return f"{err.get('code', '')} | {err.get('message', '')} | {err.get('details', '')}"

    # ---------- 1. 非法数量必须被拒，且不落库 ----------

    def test_zero_quantity_rejected(self):
        """A-179 原值：quantity=0 ⇒ 400，且 QuoteRequest 一条都不建"""
        resp = self.client.post(URL, self._payload(0), format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(QuoteRequest.objects.count(), 0,
                         '数量 0 被接受了 —— A-179 未修好')
        self.assertEqual(QuoteRequestItem.objects.count(), 0)

    def test_negative_quantity_rejected(self):
        resp = self.client.post(URL, self._payload(-3), format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(QuoteRequestItem.objects.count(), 0)

    def test_absurd_quantity_rejected(self):
        """荒谬值（100 万 + 1）⇒ 400。仅挡手滑/脚本灌数，不是业务限制"""
        resp = self.client.post(URL, self._payload(1000001), format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(QuoteRequestItem.objects.count(), 0)

    def test_error_mentions_quantity(self):
        """400 必须指到 quantity，否则前端无法把红字挂到对应行"""
        resp = self.client.post(URL, self._payload(0), format='json')
        self.assertIn('quantity', self._error_text(resp).lower(),
                      self._error_text(resp)[:300])

    # ---------- 2. 合法值必须通过 ----------

    def test_bulk_and_boundary_accepted(self):
        """1 / 999 / 5000（真实批量询价）/ 1000000（含边界）都必须放行"""
        for qty in (1, 999, 5000, 1000000):
            resp = self.client.post(URL, self._payload(qty), format='json')
            self.assertEqual(resp.status_code, 201,
                             f'数量 {qty} 被误拦：{resp.content}')
            item = QuoteRequestItem.objects.latest('id')
            self.assertEqual(item.quantity, qty)

    def test_omitted_quantity_defaults_to_one(self):
        """不传 quantity ⇒ 走模型 default=1，保持原行为"""
        resp = self.client.post(
            URL, self._payload(None, with_field=False), format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(QuoteRequestItem.objects.latest('id').quantity, 1)

    # ---------- 3. 多行时整体原子 ----------

    def test_mixed_items_rejected_entirely(self):
        """一行合法 + 一行数量 0 ⇒ 整体 400，且合法那行也不落库"""
        payload = {
            'contact_name': 'Dr. Mixed',
            'contact_email': 'mixed@lab.edu',
            'items': [
                {'product_id': self.product.id, 'quantity': 2},
                {'product_id': self.product.id, 'quantity': 0},
            ],
        }
        resp = self.client.post(URL, payload, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(QuoteRequest.objects.count(), 0)
        self.assertEqual(QuoteRequestItem.objects.count(), 0)


class RfqQuantityBoundsShapeTest(TestCase):
    """防线：下限与购物车同值；上限刻意放宽，二者都写在同一个常量里。"""

    def test_min_matches_basket(self):
        from apps.quotes.api.v1.serializers import RFQ_ITEM_QTY_MIN
        from apps.transactions.api.v1.basket_serializers import (
            AddToBasketSerializer,
        )
        self.assertEqual(RFQ_ITEM_QTY_MIN, AddToBasketSerializer().fields['quantity'].min_value)

    def test_max_is_deliberately_looser_than_cart(self):
        """RFQ 是批量询价，上限必须明显大于购物车 —— 否则会拒掉真实大单"""
        from apps.quotes.api.v1.serializers import RFQ_ITEM_QTY_MAX
        from apps.transactions.api.v1.basket_serializers import (
            AddToBasketSerializer,
        )
        cart_max = AddToBasketSerializer().fields['quantity'].max_value
        self.assertGreater(
            RFQ_ITEM_QTY_MAX, cart_max,
            'RFQ 上限被设成购物车口径了 —— 会把批量询价客户挡在门外（见本文件头注）',
        )

    def test_serializer_field_uses_the_constants(self):
        from apps.quotes.api.v1.serializers import (
            RFQ_ITEM_QTY_MAX, RFQ_ITEM_QTY_MIN, QuoteRequestItemSerializer,
        )
        f = QuoteRequestItemSerializer().fields['quantity']
        self.assertEqual(f.min_value, RFQ_ITEM_QTY_MIN)
        self.assertEqual(f.max_value, RFQ_ITEM_QTY_MAX)
