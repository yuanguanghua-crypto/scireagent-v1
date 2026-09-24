"""A / B 修复的回归闸门（2026-09-24）。

**A**：`ProtocolListSerializer.create()/update()` 里用了 `MethodProtocol`（定义在 `apps.bridges`）却
**未导入** ⇒ 只要 `methods` 非空就 `NameError` ⇒ POST/PUT **500** ⇒
「新建协议时选方法 / 编辑保存」**完全不可用**（此前 E2E 只覆盖了 `methods=[]` 的新建，故一直是绿的）。

**B**：`ReferenceSerializer.source_type` 源自模型 choices（出版物类型：journal/book/patent/thesis/web/other），
而库中 **162/208** 条历史值为 `pubmed`（文献库名）⇒ 编辑这类文献保存必 **400**
⇒ 按「**不改模型**」口径在**序列化器层放宽**（模型 choices 与 migration 均不动）。

本文件同时钉住两条**边界契约**，防止"修一处、坏一处"：
  1) 协议写的桥刷新**只动 `explicit=True` 的桥**，不得触碰服务层/AI 派生的非显式桥；
  2) 放宽 `pubmed` **不得收窄**原有枚举，也不得让 `website`（前端曾经的错值）蒙混过关。
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.bridges.models import MethodProtocol
from apps.knowledge.tests.factories import (
    MethodFactory, ProtocolFactory, ReferenceFactory,
)


class ProtocolMethodBridgeWriteTest(TestCase):
    """修 A：带 `methods` 的协议写路径不得 500，且桥刷新契约成立。"""

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=UserFactory(is_staff=True))

    def test_create_with_methods_creates_explicit_bridge(self):
        """POST 带真实 method ⇒ 201，且桥按 explicit=True 建成（原为 500 NameError）。"""
        m = MethodFactory()
        resp = self.client.post(
            '/api/v1/protocols/', {'name': 'P-A', 'methods': [m.id]}, format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.content[:300])
        pid = resp.json()['data']['id']
        rows = list(
            MethodProtocol.objects.filter(protocol_id=pid)
            .values_list('method_id', 'explicit')
        )
        self.assertEqual(rows, [(m.id, True)])

    def test_update_refreshes_only_explicit_bridges(self):
        """PUT 带 1 个 method：`explicit` 桥收敛为所选那一个；**非** explicit 桥原样保留。

        收敛是**已实测的产品行为**（编辑器为单选 UX，页面注释在案）；本用例把两条边界都钉住，
        以免将来把"只动 explicit"改成"全删重建"。
        """
        m1, m2, m3 = MethodFactory(), MethodFactory(), MethodFactory()
        pr = ProtocolFactory()
        MethodProtocol.objects.create(method=m1, protocol=pr, explicit=True, status='active')
        MethodProtocol.objects.create(method=m2, protocol=pr, explicit=True, status='active')
        MethodProtocol.objects.create(method=m3, protocol=pr, explicit=False, status='active')

        resp = self.client.put(
            f'/api/v1/protocols/{pr.id}/', {'name': pr.name, 'methods': [m1.id]}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.content[:300])

        explicit = sorted(
            MethodProtocol.objects.filter(protocol=pr, explicit=True)
            .values_list('method_id', flat=True)
        )
        nonexplicit = sorted(
            MethodProtocol.objects.filter(protocol=pr, explicit=False)
            .values_list('method_id', flat=True)
        )
        self.assertEqual(explicit, [m1.id], 'explicit 桥应收敛为下拉所选的那一个')
        self.assertEqual(nonexplicit, [m3.id], '非 explicit 桥（服务层/AI 派生）不得被触碰')

    def test_update_without_methods_key_leaves_bridges_alone(self):
        """PUT **不带** `methods` 键 ⇒ 完全不刷新桥（`methods is None` 分支）。"""
        m1, m2 = MethodFactory(), MethodFactory()
        pr = ProtocolFactory()
        MethodProtocol.objects.create(method=m1, protocol=pr, explicit=True, status='active')
        MethodProtocol.objects.create(method=m2, protocol=pr, explicit=True, status='active')

        resp = self.client.put(f'/api/v1/protocols/{pr.id}/', {'name': pr.name}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        explicit = sorted(
            MethodProtocol.objects.filter(protocol=pr, explicit=True)
            .values_list('method_id', flat=True)
        )
        self.assertEqual(explicit, sorted([m1.id, m2.id]), '不带 methods 键时不得动桥')


class ReferenceSourceTypeWriteTest(TestCase):
    """修 B：`source_type='pubmed'` 必须可保存；放宽不得收窄原枚举、不得放行错值。"""

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=UserFactory(is_staff=True))

    def _put(self, ref, **extra):
        payload = {'title': ref.title}
        payload.update(extra)
        return self.client.put(f'/api/v1/references/{ref.id}/', payload, format='json')

    def test_put_accepts_pubmed(self):
        """库中 162/208 条为该值 ⇒ 编辑保存必须 2xx 且值保持。"""
        ref = ReferenceFactory(source_type='pubmed')
        resp = self._put(ref, source_type='pubmed')
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        ref.refresh_from_db()
        self.assertEqual(ref.source_type, 'pubmed')

    def test_put_rejects_frontend_legacy_wrong_value(self):
        """前端下拉曾把 `web` 写成 `website` ⇒ 该错值必须**仍被拒**（400），不得因放宽而放行。"""
        ref = ReferenceFactory()
        resp = self._put(ref, source_type='website')
        self.assertEqual(resp.status_code, 400, resp.content[:300])

    def test_all_model_choices_still_accepted(self):
        """放宽不得收窄：模型原有 6 个枚举值全部照常可写。"""
        for value in ('journal', 'book', 'patent', 'thesis', 'web', 'other'):
            with self.subTest(value=value):
                ref = ReferenceFactory()
                resp = self._put(ref, source_type=value)
                self.assertEqual(resp.status_code, 200, f'{value}: {resp.content[:200]}')
