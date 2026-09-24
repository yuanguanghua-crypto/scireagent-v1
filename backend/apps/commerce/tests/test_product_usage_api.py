"""★ P2 第 2 步闸门（2026-09-24）：`usage` 可经 API **读写**，且能**点火轴A 并落 document 行**。

背景：P2 要给研究员一个录入「厂商声称用途（`usage`）」的入口 —— 它是**轴A 的唯一地基**
（`compute_axis_a` 在 usage 为空时返回 `None`）。原先 `usage` 只在模型里，**既不在写序列化器、
也不在读序列化器** ⇒ 前端既不能保存、也不能预填。

本文件锁死三件事：
1. **写路径**：`POST/PUT/PATCH /products/` 能收 `usage`
2. **读路径**：`GET /products/{id}/`（编辑页口径）返回 `usage` ⇒ 前端可预填
3. **★ 收益**：有 `usage` + 方法链 ⇒ `recompute_product` 落 `ProductProtocol` 行
   （原先 usage 空 ⇒ 轴A=None ⇒ 全 weak ⇒ **一行都不落**）
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.bridges.models import MethodProtocol, ProductProtocol
from apps.commerce.models import Product
from apps.knowledge.models import Method, Protocol

User = get_user_model()
USAGE = ('fluorescently labeled nucleotide analog used for direct enzymatic '
         'labeling, imaging and click chemistry conjugation')


class ProductUsageApiTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username='admin_usage', password='pass123', email='u@test.com')
        self.client.force_authenticate(user=self.admin)

    def test_create_accepts_usage_and_detail_returns_it(self):
        """POST 写入 + GET 读回（编辑页预填依赖后者）。"""
        resp = self.client.post('/api/v1/products/', {
            'name': 'E2E usage probe', 'catalog_no': 'E2E-USG-1', 'slug': 'e2e-usg-1',
            'usage': USAGE,
        }, format='json')
        self.assertLess(resp.status_code, 300, 'POST 应成功')
        pid = resp.json()['data']['id']
        self.assertEqual(Product.objects.get(pk=pid).usage, USAGE, 'POST 应写入 usage')

        detail = self.client.get(f'/api/v1/products/{pid}/').json()['data']
        self.assertEqual(detail.get('usage'), USAGE, '详情必须返回 usage（否则编辑页无法预填）')

    def test_update_can_change_usage(self):
        p = Product.objects.create(name='x', catalog_no='E2E-USG-2', slug='e2e-usg-2')
        resp = self.client.patch(f'/api/v1/products/{p.id}/', {'usage': 'changed by api'}, format='json')
        self.assertLess(resp.status_code, 300, 'PATCH 应成功')
        p.refresh_from_db()
        self.assertEqual(p.usage, 'changed by api', 'PATCH 应更新 usage')

    def test_usage_fires_axis_a_and_writes_document_rows(self):
        """★ P2 的收益闸门：有 usage + 方法链 ⇒ 落 `document` 行（原先 0 行）。

        `embedding_available` 被打桩为 False ⇒ 也顺带**模拟生产**（生产容器无 `sentence_transformers`）。
        """
        method = Method.objects.create(name='P2 usage method', slug='p2-usage-method', status='active')
        proto = Protocol.objects.create(
            name='P2 usage protocol', slug='p2-usage-proto', status='published',
            objective='labeling of nucleotide analogs with fluorescent dyes for imaging',
        )
        MethodProtocol.objects.create(method=method, protocol=proto)

        with patch('apps.bridges.services.embedding_backend.embedding_available', return_value=False):
            resp = self.client.post('/api/v1/products/', {
                'name': 'E2E usage axisA', 'catalog_no': 'E2E-USG-3', 'slug': 'e2e-usg-3',
                'usage': USAGE, 'method_ids': [method.id],
            }, format='json')
        self.assertLess(resp.status_code, 300, 'POST 应成功')
        pid = resp.json()['data']['id']

        rows = ProductProtocol.objects.filter(product_id=pid)
        self.assertGreater(rows.count(), 0,
                           '有 usage ⇒ 轴A 有值 ⇒ 应落 ProductProtocol 行（可观测的 P2 收益）')
        self.assertTrue(all(r.tier != 'weak' for r in rows),
                        '落库行不应是 weak（weak 会被 is_evidence_free 过滤）')

    def test_without_usage_no_rows_written(self):
        """对照：同样的产品**不给 usage** ⇒ 不落任何行（证明收益确实来自 usage）。"""
        method = Method.objects.create(name='P2 no-usage method', slug='p2-nousage-method', status='active')
        proto = Protocol.objects.create(
            name='P2 no-usage protocol', slug='p2-nousage-proto', status='published',
            objective='labeling of nucleotide analogs with fluorescent dyes for imaging',
        )
        MethodProtocol.objects.create(method=method, protocol=proto)

        with patch('apps.bridges.services.embedding_backend.embedding_available', return_value=False):
            resp = self.client.post('/api/v1/products/', {
                'name': 'E2E no usage', 'catalog_no': 'E2E-USG-4', 'slug': 'e2e-usg-4',
                'method_ids': [method.id],
            }, format='json')
        self.assertLess(resp.status_code, 300)
        pid = resp.json()['data']['id']
        self.assertEqual(ProductProtocol.objects.filter(product_id=pid).count(), 0,
                         '无 usage ⇒ 轴A=None ⇒ 不应落行（对照基线）')
