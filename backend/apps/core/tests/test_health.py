# -*- coding: utf-8 -*-
"""健康检查端点的契约测试

## 这组用例要钉住什么
1. **正常 ⇒ 200 + status=ok**
2. **DB 挂 ⇒ 503**（不是 500 —— 503 才能让 LB 正确摘流量）
3. **磁盘不足 ⇒ 503**
4. **自身绝不 500**：任何一项检查炸了，只把该项标 error（健康检查自己崩掉就没意义了）
5. **匿名只拿状态，不拿运维细节**：`details` 只回给 `is_staff`

## 怎么模拟故障
直接 monkeypatch 三项检查函数（`_check_db` / `_check_disk` / `_check_cache`）——
这比真的去停 DB 更可靠（后者在 CI 里做不到，且会污染其他测试）。
"""
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from core import health

URL = '/api/v1/health/'


class HealthCheckTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_healthy_returns_200(self):
        resp = self.client.get(URL)
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertEqual(body['status'], 'ok')
        self.assertEqual(body['checks'], {'db': 'ok', 'cache': 'ok', 'disk': 'ok'})

    def test_db_down_returns_503(self):
        """★ 核心用例：DB 不可用必须 503，不能 500，也不能假装 200。"""
        with mock.patch.object(health, '_check_db', return_value=(False, 'OperationalError')):
            resp = self.client.get(URL)
        self.assertEqual(resp.status_code, 503, resp.content)
        body = resp.json()
        self.assertEqual(body['status'], 'degraded')
        self.assertEqual(body['checks']['db'], 'error')
        # 其他项仍应为 ok（不能因为 DB 挂就把一切标红）
        self.assertEqual(body['checks']['cache'], 'ok')
        self.assertEqual(body['checks']['disk'], 'ok')

    def test_low_disk_returns_503(self):
        with mock.patch.object(health, '_check_disk', return_value=(False, 'low_disk')):
            resp = self.client.get(URL)
        self.assertEqual(resp.status_code, 503, resp.content)
        self.assertEqual(resp.json()['checks']['disk'], 'error')

    def test_cache_down_returns_503(self):
        with mock.patch.object(health, '_check_cache', return_value=(False, 'ConnectionError')):
            resp = self.client.get(URL)
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.json()['checks']['cache'], 'error')

    def test_check_raising_does_not_500(self):
        """检查函数自己抛异常时，端点也不能 500 —— 否则健康检查形同虚设。"""
        with mock.patch.object(health, '_check_db', side_effect=RuntimeError('boom')):
            resp = self.client.get(URL)
        self.assertEqual(resp.status_code, 503, resp.content)

    def test_anonymous_gets_no_details(self):
        """匿名者只能拿到 ok/error，不暴露异常类型/磁盘数值等运维信息。"""
        with mock.patch.object(health, '_check_db', return_value=(False, 'OperationalError')):
            resp = self.client.get(URL)
        body = resp.json()
        self.assertNotIn('details', body)
        # 原始异常类型名不应出现在响应里
        self.assertNotIn('OperationalError', str(body))

    def test_staff_gets_details(self):
        from apps.accounts.tests.factories import UserFactory
        staff = UserFactory(is_staff=True, role='admin')
        self.client.force_authenticate(user=staff)
        with mock.patch.object(health, '_check_db', return_value=(False, 'OperationalError')):
            resp = self.client.get(URL)
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.json()['details'].get('db'), 'OperationalError')

    def test_anonymous_can_access(self):
        """监控系统没有业务 token ⇒ 必须匿名可访问。"""
        self.client.force_authenticate(None)
        resp = self.client.get(URL)
        self.assertEqual(resp.status_code, 200)
