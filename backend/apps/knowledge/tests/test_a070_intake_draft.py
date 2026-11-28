"""A-070 方案 A：Intake 表单草稿（存草稿 / 回读 / 不污染业务写入）。

## 背景
A-070 的另一半是"保存后重载，表单全空"。原实现只写协议/方法，**不保存表单本身**。
方案 A（用户 2026-11-28 定）：单独存一份草稿，打开页面按产品回读。

## 三条边界
① 提交成功后草稿落库，`GET ?product_id=` 能原样取回；
② 同一产品再存 → **覆盖**，不产生第二条（OneToOne + update_or_create）；
③ 没有草稿的产品 → `draft: null`（前端据此渲染空表，不报错）。

## 为什么不从已落库内容反推
表单里的 `protocol_time` / `protocol_difficulty` / `reference_pmid` 等本来就不落库
（`unmapped_fields` 已如实回报），反推回来是有损的，字段对不上会误导。
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.commerce.models import Product
from apps.knowledge.models import KnowledgeIntakeDraft


class IntakeDraftTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='a070_admin', password='x', email='a070@lab.edu',
            role='admin', is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.product = Product.objects.create(
            name='A070 Probe', slug='a070-probe', catalog_no='A070-1',
            status='draft', research_use_only=True)

    def _submit(self, **over):
        payload = {
            'product_id': self.product.id,
            'research_goals': [],
            'applications': [],
            'methods': [],
            'protocols': ['ZZ-TEST-PROTOCOL-A070'],
            'protocol_objective': 'objective text',
            'protocol_steps': '1. step one\n2. step two',
            'protocol_time': '2h',
            'protocol_difficulty': 'advanced',
            'reference_pmid': '12345678',
            'key_advantages': 'fast',
            'key_limitations': 'pricey',
            'confidence': 'medium',
        }
        payload.update(over)
        return self.client.post('/api/v1/knowledge-intake/', payload, format='json')

    def test_draft_created_and_readable(self):
        r = self._submit()
        self.assertEqual(r.status_code, 200, r.content[:400])
        d = KnowledgeIntakeDraft.objects.get(product=self.product)
        self.assertEqual(d.form_json.get('protocol_time'), '2h')

        g = self.client.get('/api/v1/knowledge-intake/',
                            {'product_id': self.product.id})
        self.assertEqual(g.status_code, 200, g.content[:300])
        body = g.json()['data']
        self.assertIsNotNone(body['draft'])
        self.assertEqual(body['draft']['protocol_difficulty'], 'advanced')
        self.assertIn('saved_at', body)

    def test_second_save_overwrites_not_duplicates(self):
        self._submit()
        self._submit(protocol_time='4h')
        self.assertEqual(
            KnowledgeIntakeDraft.objects.filter(product=self.product).count(), 1)
        d = KnowledgeIntakeDraft.objects.get(product=self.product)
        self.assertEqual(d.form_json.get('protocol_time'), '4h')

    def test_missing_draft_returns_null(self):
        g = self.client.get('/api/v1/knowledge-intake/',
                            {'product_id': self.product.id})
        self.assertEqual(g.status_code, 200)
        self.assertIsNone(g.json()['data']['draft'])

    def test_bad_product_id_returns_400(self):
        g = self.client.get('/api/v1/knowledge-intake/', {'product_id': 'abc'})
        self.assertEqual(g.status_code, 400)

    def test_product_id_not_stored_inside_draft(self):
        """草稿里不该带 product_id（它是外键，重复存一份会在回填时造成歧义）。"""
        self._submit()
        d = KnowledgeIntakeDraft.objects.get(product=self.product)
        self.assertNotIn('product_id', d.form_json)
