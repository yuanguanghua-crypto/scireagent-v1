# -*- coding: utf-8 -*-
"""外部数据源失效时的**降级行为**（对应 FAILURE_MODES 7.1，此前是 B 类）

## 为什么这个测试是"补修复"而不是"补断言"
先实测了当前行为（patch `resolve_to_properties` 抛 `requests.ConnectionError`）：
**视图里没有任何 try/except ⇒ 未捕获异常 ⇒ 生产直接 500。**
产品编辑页的"自动补全"会整个失败，用户也不知道可以手动填。

所以先修（外层兜 503 + 批量模式单条降级），再用测试钉住。

## 为什么不用 cassette
PubChem 主路径走的是 `pubchempy`（内部用 urllib），**绕过了统一 HTTP 客户端**，
cassette 覆盖不到（和之前发现的 3 处 urllib 直连是同一个问题）。
ChEMBL fallback 走 `request_with_resilience` 且自身已有 try/except。
⇒ 这里直接 patch 业务层方法，比绕到 HTTP 层更贴近"数据源不可用"这个事实。

## 三层降级语义
| 场景 | 期望 |
|---|---|
| 单产品模式，数据源挂 | **503** + `DATASOURCE_UNAVAILABLE`（不是 500） |
| 批量模式，部分产品失败 | **200**，失败项 `found=False, error=source_unavailable`，其余正常返回 |
| 正常 | 200 + 正常数据 |
"""
from unittest import mock

import requests
from rest_framework.test import APITestCase

from apps.accounts.tests.factories import UserFactory
from apps.commerce.tests.factories import ProductFactory

URL = '/api/v1/products/enrich-from-pubchem/'
PATCH_TARGET = ('apps.commerce.services.validators.pubchem_enhancer'
                '.PubChemEnhancer.resolve_to_properties')

OK_RESULT = {
    'found': True, 'cid': 2244, 'namespace': 'name',
    'properties': {'molecular_formula': 'C9H8O4', 'molecular_weight': 180.16},
}


class EnrichDegradationTests(APITestCase):
    def setUp(self):
        self.staff = UserFactory(is_staff=True, role='admin')
        self.client.force_authenticate(user=self.staff)

    # ── ① 单产品：数据源挂 ⇒ 503，不是 500 ──
    def test_single_mode_returns_503_when_source_down(self):
        with mock.patch(PATCH_TARGET, side_effect=requests.ConnectionError('pubchem down')):
            resp = self.client.post(URL, {'product_name': 'Aspirin', 'cas': '50-78-2'}, format='json')

        self.assertEqual(resp.status_code, 503,
                         f'数据源挂掉必须是 503 而非 {resp.status_code}（500 会被误读成代码 bug）')
        err = resp.json()['meta']['error']
        self.assertEqual(err['code'], 'DATASOURCE_UNAVAILABLE')
        # 消息要能指导用户下一步，不能只说 "error"
        self.assertIn('manually', err['message'].lower())

    def test_single_mode_timeout_also_503(self):
        """超时和连接错误一样要降级（这是最常见的失效形态）。"""
        with mock.patch(PATCH_TARGET, side_effect=requests.Timeout('read timeout')):
            resp = self.client.post(URL, {'product_name': 'X'}, format='json')
        self.assertEqual(resp.status_code, 503)

    # ── ② 批量：一个失败不拖垮整批 ──
    def test_batch_mode_degrades_per_item(self):
        p1 = ProductFactory(name='Aspirin', cas='50-78-2')
        p2 = ProductFactory(name='Ibuprofen', cas='15687-27-1')

        def fake_resolve(self_, identifier, **kwargs):
            if identifier == 'Aspirin':
                raise requests.ConnectionError('boom')
            return OK_RESULT

        with mock.patch(PATCH_TARGET, new=fake_resolve):
            resp = self.client.post(URL, {'product_ids': [p1.id, p2.id]}, format='json')

        self.assertEqual(resp.status_code, 200,
                         '批量模式单条失败不该让整批 503')
        rows = resp.json()['data']
        by_id = {r['product_id']: r for r in rows}
        self.assertEqual(len(by_id), 2, '两个产品都应出现在结果里')
        self.assertFalse(by_id[p1.id]['enriched']['found'])
        self.assertEqual(by_id[p1.id]['enriched'].get('error'), 'source_unavailable')
        self.assertTrue(by_id[p2.id]['enriched']['found'],
                        '失败的那条不能影响成功的那条')

    # ── ③ 正常路径不受影响 ──
    def test_happy_path_still_works(self):
        with mock.patch(PATCH_TARGET, return_value=OK_RESULT):
            resp = self.client.post(URL, {'product_name': 'Aspirin'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.json()['data']['found'])

    # ── ④ 缺标识符仍走原来的 400，不被 503 兜底吞掉 ──
    def test_missing_identifier_still_400(self):
        resp = self.client.post(URL, {}, format='json')
        self.assertEqual(resp.status_code, 400,
                         '参数错误是 400，不能被外层 503 兜底误判成"数据源不可用"')

    # ── ⑤ 权限不变：非 staff 不可用 ──
    def test_non_staff_forbidden(self):
        researcher = UserFactory(role='researcher')
        self.client.force_authenticate(user=researcher)
        resp = self.client.post(URL, {'product_name': 'Aspirin'}, format='json')
        self.assertIn(resp.status_code, (401, 403))
