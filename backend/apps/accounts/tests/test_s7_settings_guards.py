"""设置页的三道闸门（A-183 / A-187，2026-11-27）。

## 改前
- **A-183**：界面把 Nickname 标成必填，但前后端**都没拦** —— 清空保存照样
  "Profile updated successfully"，旧值被写空。
- **A-187**：地址模型字段全 `blank=True`、序列化器零校验 ⇒ `POST /addresses/ {}`
  直接 201，落一条 `line1=''、city=''、country='US'` 的空白地址（表单全空点 Save 就多一行）。

本文件钉住：空提交必须被拒，合法提交必须通过（避免"收紧了但正常也用不了"）。
"""
import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory


@pytest.mark.django_db
class TestNicknameRequired:
    def _patch(self, payload):
        u = UserFactory(nickname='TEST-Nick')
        c = APIClient()
        c.force_authenticate(u)
        return c.put('/api/v1/auth/profile', payload, format='json'), u

    def test_empty_nickname_is_rejected(self):
        r, u = self._patch({'nickname': ''})
        assert r.status_code == 400, r.content[:300]
        u.refresh_from_db()
        assert u.nickname == 'TEST-Nick', '被拒时旧值必须保留'

    def test_blank_nickname_is_rejected(self):
        r, _ = self._patch({'nickname': '   '})
        assert r.status_code == 400

    def test_valid_nickname_passes(self):
        r, u = self._patch({'nickname': 'NEW-Nick'})
        assert r.status_code == 200, r.content[:300]
        u.refresh_from_db()
        assert u.nickname == 'NEW-Nick'

    def test_other_fields_without_nickname_still_pass(self):
        """不传 nickname 的更新（如只改电话）不能被误拦。"""
        r, _ = self._patch({'phone': '123'})
        assert r.status_code == 200, r.content[:300]


@pytest.mark.django_db
class TestAddressRequired:
    def setup_method(self):   # pytest 的钩子名；写成 setUp 不会被调（纯类不是 TestCase）
        self.user = UserFactory()
        from apps.accounts.models import Organization
        if not self.user.organization:
            self.user.organization = Organization.objects.create(name='Addr Org', org_type='academic')
            self.user.save(update_fields=['organization'])
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_empty_payload_rejected(self):
        r = self.client.post('/api/v1/addresses/', {}, format='json')
        assert r.status_code == 400, '★ 空地址不能落库（改前直接 201）'

    def test_missing_city_rejected(self):
        r = self.client.post('/api/v1/addresses/', {'line1': '1 Main St'}, format='json')
        assert r.status_code == 400

    def test_complete_address_accepted(self):
        r = self.client.post('/api/v1/addresses/',
                             {'line1': '1 Main St', 'city': 'Boston', 'country': 'US'},
                             format='json')
        assert r.status_code == 201, r.content[:300]
