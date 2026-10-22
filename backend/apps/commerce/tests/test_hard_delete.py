"""F8-1 产品物理删除（hard-delete）—— 超管专属、不可逆，此前没有任何用例。

为什么必须有：
  `POST /products/{id}/hard-delete/` 是 `IsSuperUser`，**前端 0 引用**（真孤儿能力）。
  它不做软删、直接物理删且级联 —— 一旦权限口径被放宽或误操作，数据不可恢复。
  端点无 UI，所以只能在这一层锁住权限边界。
"""
import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.commerce.models import Product
from apps.commerce.tests.factories import ProductFactory


def _url(pid):
    return f'/api/v1/products/{pid}/hard-delete/'


@pytest.mark.django_db
class TestHardDelete:
    def test_superuser_can_hard_delete(self):
        p = ProductFactory(status='draft')
        u = UserFactory(is_staff=True, is_superuser=True, email_verified=True)
        c = APIClient(); c.force_authenticate(user=u)

        r = c.post(_url(p.id))
        assert r.status_code in (200, 204), r.content[:300]
        assert not Product.objects.filter(pk=p.id).exists(), '物理删除后产品仍在'

    def test_staff_cannot_hard_delete(self):
        """★ 核心边界：staff 能软删（DELETE），但**不能**物理删。"""
        p = ProductFactory(status='draft')
        u = UserFactory(is_staff=True, is_superuser=False, email_verified=True)
        c = APIClient(); c.force_authenticate(user=u)

        r = c.post(_url(p.id))
        assert r.status_code == 403, (
            f'staff 竟然能物理删除（得 {r.status_code}）—— 权限被放开了，立刻检查 IsSuperUser')
        assert Product.objects.filter(pk=p.id).exists(), '被拒但仍然删掉了'

    def test_procurement_cannot_hard_delete(self):
        p = ProductFactory(status='draft')
        u = UserFactory(role='procurement', is_staff=False, email_verified=True)
        c = APIClient(); c.force_authenticate(user=u)
        r = c.post(_url(p.id))
        assert r.status_code == 403
        assert Product.objects.filter(pk=p.id).exists()

    def test_anonymous_cannot_hard_delete(self):
        p = ProductFactory(status='draft')
        r = APIClient().post(_url(p.id))
        assert r.status_code in (401, 403)
        assert Product.objects.filter(pk=p.id).exists()

    def test_not_found_returns_404(self):
        u = UserFactory(is_staff=True, is_superuser=True, email_verified=True)
        c = APIClient(); c.force_authenticate(user=u)
        r = c.post(_url(99999999))
        assert r.status_code == 404
