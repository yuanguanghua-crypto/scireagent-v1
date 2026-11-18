"""S3 写路径回归（A-063 / A-076 / A-155 / A-158 的后端部分）。

三个契约各锁一组：

1. **A-063 `application_ids`**：方法新建/更新时能把应用关联真正写进
   `application_method` 桥，且**只增不删**（方法关联可达 1,346 条，替换语义会
   静默删真实数据）。同时锁住旧契约：`application_id`（单数、代表值）仍是只读，
   不允许哪天被误改成半读半写。
2. **A-076 `ProtocolWriteSerializer`**：协议写路径能落 `objective/principle/...`
   等内容字段，同时**不破坏** `methods` 的 `MethodProtocol` 桥写入 ——
   这正是不能直接切 `ProtocolDetailSerializer` 的原因（那里的 `methods` 只读）。
3. **A-155 / A-158 同名口径**：四类实体重名返回 409（而非静默建副本），
   归档行可复用名字，`?allow_duplicate=1` 是显式逃生口。
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.bridges.models import MethodProtocol
from apps.knowledge.models import (
    ApplicationMethod, Application, Method, Protocol, ResearchGoal,
)
from apps.knowledge.tests.factories import (
    ApplicationFactory, MethodFactory, ProtocolFactory, ResearchGoalFactory,
)


class MethodApplicationWriteTest(TestCase):
    """A-063：方法↔应用关联的写路径。"""

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(UserFactory(is_staff=True))
        self.app1 = ApplicationFactory(name='S3 App One')
        self.app2 = ApplicationFactory(name='S3 App Two')

    def test_create_method_links_application(self):
        r = self.client.post('/api/v1/methods/', {
            'name': 'S3 Method With App',
            'application_ids': [self.app1.id],
        }, format='json')
        self.assertIn(r.status_code, (200, 201), r.content[:400])

        m = Method.objects.get(name='S3 Method With App')
        self.assertTrue(
            ApplicationMethod.objects.filter(method=m, application=self.app1).exists(),
            'application_ids 必须真正落进 application_method 桥',
        )

    def test_patch_is_additive_and_never_deletes(self):
        """更新只追加：已有 app1 关联在新增 app2 后必须保留。"""
        m = MethodFactory(name='S3 Additive Method', application=self.app1)
        before = set(
            ApplicationMethod.objects.filter(method=m)
            .values_list('application_id', flat=True)
        )
        self.assertIn(self.app1.id, before, '工厂前置：应已挂 app1')

        r = self.client.patch(f'/api/v1/methods/{m.id}/', {
            'application_ids': [self.app2.id],
        }, format='json')
        self.assertIn(r.status_code, (200, 201), r.content[:400])

        after = set(
            ApplicationMethod.objects.filter(method=m)
            .values_list('application_id', flat=True)
        )
        self.assertIn(self.app2.id, after, '新关联必须写入')
        self.assertTrue(before.issubset(after), f'原有 {before} 不得被删除，实得 {after}')

    def test_repeated_application_ids_is_idempotent(self):
        """重复提交同一应用不产生重复桥行（unique_together + update_or_create）。"""
        m = MethodFactory(name='S3 Idempotent Method', application=self.app1)
        for _ in range(2):
            self.client.patch(f'/api/v1/methods/{m.id}/', {
                'application_ids': [self.app2.id],
            }, format='json')
        self.assertEqual(
            ApplicationMethod.objects.filter(method=m, application=self.app2).count(), 1
        )

    def test_unknown_application_id_is_rejected(self):
        r = self.client.post('/api/v1/methods/', {
            'name': 'S3 Method Bad App',
            'application_ids': [999999],
        }, format='json')
        self.assertEqual(r.status_code, 400, r.content[:400])
        self.assertFalse(Method.objects.filter(name='S3 Method Bad App').exists())

    def test_application_id_singular_stays_readonly(self):
        """锁住旧契约：`application_id` 是代表值只读，写它不落桥、也不报错。"""
        m = MethodFactory(name='S3 Readonly Method', application=self.app1)
        before = ApplicationMethod.objects.filter(method=m).count()

        r = self.client.patch(f'/api/v1/methods/{m.id}/', {
            'application_id': self.app2.id,
        }, format='json')
        self.assertIn(r.status_code, (200, 201), r.content[:400])
        self.assertEqual(
            ApplicationMethod.objects.filter(method=m).count(), before,
            'application_id 是只读代表值；真正写关联必须走 application_ids',
        )


class ProtocolWriteSerializerTest(TestCase):
    """A-076：协议写路径补内容字段，且不丢 methods 桥。"""

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(UserFactory(is_staff=True))

    def test_create_with_content_and_methods_bridge(self):
        m = MethodFactory(name='S3 Proto Method')

        r = self.client.post('/api/v1/protocols/', {
            'name': 'S3 Protocol Full',
            'objective': 'S3 objective text',
            'principle': 'S3 principle text',
            'materials': 'S3 materials',
            'equipment': 'S3 equipment',
            'troubleshooting': 'S3 troubleshooting',
            'expected_results': 'S3 expected',
            'methods': [m.id],
        }, format='json')
        self.assertIn(r.status_code, (200, 201), r.content[:500])

        p = Protocol.objects.get(name='S3 Protocol Full')
        self.assertEqual(p.objective, 'S3 objective text')
        self.assertEqual(p.expected_results, 'S3 expected')
        self.assertTrue(
            MethodProtocol.objects.filter(protocol=p, method=m, explicit=True).exists(),
            'methods 桥必须仍被写入（这是不能切 ProtocolDetailSerializer 的原因）',
        )

    def test_patch_updates_content_fields(self):
        p = ProtocolFactory(name='S3 Protocol Patch')

        r = self.client.patch(f'/api/v1/protocols/{p.id}/', {
            'objective': 'patched objective',
            'reagents': 'patched reagents',
        }, format='json')
        self.assertIn(r.status_code, (200, 201), r.content[:400])

        p.refresh_from_db()
        self.assertEqual(p.objective, 'patched objective')
        self.assertEqual(p.reagents, 'patched reagents')

    def test_list_payload_stays_light(self):
        """列表仍走 ProtocolListSerializer：不吐 objective（避免列表体积翻倍）。"""
        p = ProtocolFactory(name='S3 Published Protocol', status='published')
        r = self.client.get('/api/v1/protocols/?page_size=50')
        self.assertIn(r.status_code, (200, 201), r.content[:300])

        rows = r.json().get('data') or []
        target = next((x for x in rows if x.get('id') == p.id), None)
        self.assertIsNotNone(target, '新建的 published 协议应出现在列表里')
        self.assertNotIn('objective', target, '列表不应带内容字段')


class DuplicateNameGuardTest(TestCase):
    """A-155 / A-158：同名冲突显式 409，归档名可复用，逃生口可用。"""

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(UserFactory(is_staff=True))

    def _assert_conflict(self, resp):
        self.assertEqual(resp.status_code, 409, resp.content[:400])
        body = resp.json()
        self.assertFalse(body.get('success'))
        self.assertEqual(body['meta']['error']['code'], 'conflict')

    def test_goal_duplicate_name_returns_409(self):
        ResearchGoalFactory(name='S3 Dup Goal')
        self._assert_conflict(
            self.client.post('/api/v1/research-goals/', {'name': 'S3 Dup Goal'}, format='json')
        )

    def test_application_duplicate_name_returns_409(self):
        app = ApplicationFactory(name='S3 Dup App')
        self._assert_conflict(
            self.client.post('/api/v1/applications/', {'name': 'S3 Dup App'}, format='json')
        )
        self.assertEqual(Application.objects.filter(name='S3 Dup App').count(), 1)
        self.assertIsNotNone(app.id)

    def test_method_duplicate_name_returns_409(self):
        MethodFactory(name='S3 Dup Method')
        self._assert_conflict(
            self.client.post('/api/v1/methods/', {'name': 'S3 Dup Method'}, format='json')
        )

    def test_protocol_duplicate_name_returns_409(self):
        ProtocolFactory(name='S3 Dup Protocol')
        self._assert_conflict(
            self.client.post('/api/v1/protocols/', {'name': 'S3 Dup Protocol'}, format='json')
        )

    def test_name_match_is_case_and_space_insensitive(self):
        ResearchGoalFactory(name='S3 Case Goal')
        self._assert_conflict(
            self.client.post('/api/v1/research-goals/', {'name': '  s3 case goal  '}, format='json')
        )

    def test_allow_duplicate_escape_hatch(self):
        ResearchGoalFactory(name='S3 Escape Goal')
        r = self.client.post(
            '/api/v1/research-goals/?allow_duplicate=1',
            {'name': 'S3 Escape Goal'}, format='json',
        )
        self.assertIn(r.status_code, (200, 201), r.content[:400])
        self.assertEqual(ResearchGoal.objects.filter(name='S3 Escape Goal').count(), 2)

    def test_archived_name_can_be_reused(self):
        ResearchGoalFactory(name='S3 Recycled Goal', status='archived')
        r = self.client.post(
            '/api/v1/research-goals/', {'name': 'S3 Recycled Goal'}, format='json'
        )
        self.assertIn(r.status_code, (200, 201), r.content[:400])

    def test_update_is_not_blocked_by_own_name(self):
        """改自己（名字不变）不能被自己拦成 409。"""
        g = ResearchGoalFactory(name='S3 Self Goal')
        r = self.client.patch(
            f'/api/v1/research-goals/{g.id}/', {'summary': 'only summary changed'},
            format='json',
        )
        self.assertIn(r.status_code, (200, 201), r.content[:400])
