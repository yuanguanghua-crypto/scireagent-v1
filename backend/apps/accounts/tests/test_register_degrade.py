"""注册降级的第二种情况 —— 后端看起来正常但**实际发送失败**。

2026-10-23 真实场景：生产切到 Resend 后，因 DNS 域名未验证，
Resend 返回 403 `domain is not verified`。此时：
- `email_delivery_is_unavailable()` 为 **False**（backend 是 anymail，不在不可达名单）
- 若照常要求邮箱验证 ⇒ 用户注册成功却永远收不到信、永远登不进去

所以注册路径必须有**动态兜底**：发信抛异常时同样降级放行。
"""
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User


class RegisterDegradeOnSendFailureTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = '/api/v1/auth/register'

    def _payload(self, username):
        return {
            'username': username,
            'email': f'{username}@lab.example.org',
            'password': 'TestPass#2026',
            'password_confirm': 'TestPass#2026',
            'role': 'researcher',
            'organization_choice': 'solo',
        }

    @patch('apps.accounts.api.v1.views.send_verification_email',
           side_effect=RuntimeError('Resend 403: domain is not verified'))
    def test_degrades_to_verified_when_send_raises(self, _mock):
        resp = self.client.post(self.url, self._payload('sendfail'), format='json')
        self.assertEqual(resp.status_code, 201, '发信失败不应导致注册失败')
        self.assertTrue(resp.data.get('email_verified'), '应降级为已验证')

        user = User.objects.get(username='sendfail')
        self.assertTrue(user.email_verified, '数据库里也应标记为已验证')

        # 降级后必须能立刻登录 —— 这是降级的唯一意义
        login = self.client.post('/api/v1/auth/login', {
            'username': 'sendfail', 'password': 'TestPass#2026',
        }, format='json')
        self.assertEqual(login.status_code, 200, '降级放行后必须能登录')

    def test_normal_path_still_requires_verification(self):
        """对照组：发信正常时，绝不能把未验证的账号放进来。"""
        resp = self.client.post(self.url, self._payload('normalpath'), format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertFalse(resp.data.get('email_verified'), '正常路径应保持未验证')

        user = User.objects.get(username='normalpath')
        self.assertFalse(user.email_verified)

        login = self.client.post('/api/v1/auth/login', {
            'username': 'normalpath', 'password': 'TestPass#2026',
        }, format='json')
        self.assertEqual(login.status_code, 403, '未验证账号必须被拦住')
