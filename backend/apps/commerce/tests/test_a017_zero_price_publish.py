"""A-017 方案 A：0 价可存草稿，但**不得发布上架**（用户 2026-11-28 定）。

## 为什么是方案 A 而不是"下限改 0.01"
原预期是「价格须大于 0，填 0 应报错」。开发在 S1 按"只挡负价"处理
（`MONEY_MIN = 0`），理由是「0 是合法的待定价占位，生产有 3 条 0 价 SKU」。
用户 2026-11-28 拍板取方案 A：**下限不动（不误伤存量 3 条 0 价 SKU），
但 status=active 时若所有 SKU 都 0 价则拦**。

## 三条边界
① `draft` + 0 价 → 允许（待定价占位）
② `active` + 全部 0 价 → 拦（400）
③ 已经是 `active` 的 0 价产品，**再保存别的字段不重复拦**
   （否则运营改个描述就被顶回来，生产那 3 条首当其冲）
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.commerce.models import Product, SKU


class ZeroPricePublishTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='a017_admin', password='x', email='a017@lab.edu',
            role='admin', is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def _create(self, status, price='0', name='A017 Probe'):
        return self.client.post('/api/v1/products/', {
            'name': name, 'slug': name.lower().replace(' ', '-'),
            'catalog_no': name.replace(' ', '-') + '-1',
            'status': status, 'research_use_only': True,
            'skus': [{'sku_code': name.replace(' ', '-') + '-1',
                      'pack_size': '1 mg', 'price': price, 'is_default': True}],
        }, format='json')

    def test_zero_price_draft_allowed(self):
        r = self._create('draft')
        self.assertEqual(r.status_code, 201, r.content[:300])

    def test_zero_price_active_rejected(self):
        r = self._create('active')
        self.assertEqual(r.status_code, 400, r.content[:300])
        body = r.json()
        self.assertIn('skus', str(body))

    def test_zero_price_with_one_priced_sku_active_allowed(self):
        """只要有一个 SKU 定了价，就不算"全部 0 价"，放行。"""
        r = self.client.post('/api/v1/products/', {
            'name': 'A017 Mixed', 'slug': 'a017-mixed', 'catalog_no': 'A017-MIXED-1',
            'status': 'active', 'research_use_only': True,
            'skus': [
                {'sku_code': 'A017-MIXED-1', 'pack_size': '1 mg', 'price': '0'},
                {'sku_code': 'A017-MIXED-2', 'pack_size': '5 mg', 'price': '99.00',
                 'is_default': True},
            ],
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content[:300])

    def test_existing_active_zero_price_can_update_other_fields(self):
        """已 active 的 0 价产品（生产有 3 条）改描述不应被拦。"""
        p = Product.objects.create(
            name='Legacy Zero', slug='legacy-zero', catalog_no='LEGACY-ZERO',
            status='active', research_use_only=True)
        SKU.objects.create(product=p, sku_code='LEGACY-ZERO-1',
                           pack_size='1 mg', price=Decimal('0'), is_default=True)
        r = self.client.patch(f'/api/v1/products/{p.id}/',
                              {'summary': '改个描述'}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
