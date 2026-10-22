"""`GET /auth/verify-email` 的 token 容错 —— 畸形 token 必须 400，不能 500。

## 修的是什么
`EmailVerification.token` 是 `UUIDField`。传入非 UUID 字符串（如 `probe-invalid-token`）时，
Django 抛的是 **`django.core.exceptions.ValidationError`**，不是 `ValueError`；
原代码只捕了 `(DoesNotExist, ValueError)` ⇒ 未捕获 → **500 + HTML 错误页**（实测）。

用户手改 URL、邮件客户端截断链接、或历史上发出去的旧格式链接，都会落到这条路径。
正确表现应与"格式对但不存在"**同一句口径**：400 + `Invalid or expired verification token.`
"""
import pytest
from rest_framework.test import APIClient

URL = '/api/v1/auth/verify-email'


@pytest.mark.django_db
class TestVerifyEmailTokenTolerance:
    def test_malformed_token_returns_400_not_500(self):
        """★ 核心回归：非 UUID 字符串曾触发 500。"""
        r = APIClient().get(URL, {'token': 'probe-invalid-token'})
        assert r.status_code == 400, (
            f'畸形 token 得 {r.status_code}（500 说明 ValidationError 又没被捕获）')
        assert 'Invalid or expired' in str(r.json()), r.content[:300]

    def test_malformed_token_with_symbols(self):
        for bad in ('abc', '12345', 'not-a-uuid', '../../etc/passwd', 'x' * 64):
            r = APIClient().get(URL, {'token': bad})
            assert r.status_code == 400, f'{bad!r} 得 {r.status_code}'

    def test_wellformed_but_unknown_token_returns_400(self):
        r = APIClient().get(URL, {'token': '11111111-1111-1111-1111-111111111111'})
        assert r.status_code == 400
        assert 'Invalid or expired' in str(r.json())

    def test_missing_token_returns_400_with_own_message(self):
        r = APIClient().get(URL)
        assert r.status_code == 400
        assert 'Missing verification token' in str(r.json())

    def test_error_body_is_readable_not_html(self):
        """畸形 token 曾返回 HTML 错误页（DEBUG 页），前端无法解析。"""
        r = APIClient().get(URL, {'token': 'probe-invalid-token'})
        assert 'text/html' not in r.get('Content-Type', ''), (
            '仍返回 HTML —— 说明异常没被视图捕获，走的是 Django 默认错误页')
