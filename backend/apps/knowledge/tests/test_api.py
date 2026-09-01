from django.test import TestCase
from rest_framework.test import APIClient
from apps.knowledge.tests.factories import (
    ResearchGoalFactory, ApplicationFactory, MethodFactory,
    ProtocolFactory, ProtocolStepFactory, ReferenceFactory, CompatibilityFactory
)
from apps.knowledge.models import ResearchGoal, Application, Method
from apps.bridges.tests.factories import ProductMethodFactory, MethodProtocolFactory
from apps.bridges.models import MethodProtocol
from apps.accounts.tests.factories import UserFactory


class ResearchGoalAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        # BUG-2a 修复后，公开端点对匿名/普通用户仅返回 ACTIVE 记录。
        # 这些通用 API 测试以 staff 身份验证"能看到创建的全量数据"
        # （含草稿/归档）这一原有假设，恢复修复前的行为预期。
        self.client.force_authenticate(user=UserFactory(is_staff=True))

    def test_list_empty(self):
        resp = self.client.get('/api/v1/research-goals/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data'], [])

    def test_list_with_data(self):
        ResearchGoalFactory.create_batch(3)
        resp = self.client.get('/api/v1/research-goals/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['data']), 3)

    def test_list_envelope_format(self):
        ResearchGoalFactory()
        resp = self.client.get('/api/v1/research-goals/')
        data = resp.json()
        self.assertIn('success', data)
        self.assertIn('data', data)
        self.assertIn('meta', data)

    def test_detail(self):
        goal = ResearchGoalFactory(name='Test Goal')
        resp = self.client.get(f'/api/v1/research-goals/{goal.id}/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['data']['name'], 'Test Goal')

    def test_detail_fields(self):
        goal = ResearchGoalFactory()
        resp = self.client.get(f'/api/v1/research-goals/{goal.id}/')
        data = resp.json()['data']
        self.assertIn('id', data)
        self.assertIn('name', data)
        self.assertIn('slug', data)
        self.assertIn('summary', data)
        self.assertIn('priority', data)
        self.assertIn('status', data)
        self.assertIn('created_at', data)

    def test_create(self):
        # Create admin user for write operations
        admin = UserFactory(is_staff=True)
        self.client.force_authenticate(user=admin)

        resp = self.client.post('/api/v1/research-goals/', {
            'name': 'New Goal', 'slug': 'new-goal', 'summary': 'Test'
        }, format='json')
        self.assertEqual(resp.status_code, 201)

    def test_detail_not_found(self):
        resp = self.client.get('/api/v1/research-goals/99999/')
        self.assertEqual(resp.status_code, 404)

    def test_detail_includes_protocols(self):
        goal = ResearchGoalFactory()
        p = ProtocolFactory()
        goal.protocols.add(p)
        resp = self.client.get(f'/api/v1/research-goals/{goal.id}/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertIn('protocols', data)
        ids = {x['id'] for x in data['protocols']}
        self.assertIn(p.id, ids)

    def test_anonymous_detail_includes_protocols(self):
        # 公开端点对匿名可读；策展协议集是只读展示，不应因匿名而消失。
        self.client.force_authenticate(user=None)
        goal = ResearchGoalFactory(status=ResearchGoal.Status.ACTIVE)
        p = ProtocolFactory()
        goal.protocols.add(p)
        resp = self.client.get(f'/api/v1/research-goals/{goal.id}/')
        self.assertEqual(resp.status_code, 200)
        ids = {x['id'] for x in resp.json()['data']['protocols']}
        self.assertIn(p.id, ids)

    def test_staff_can_update_protocols(self):
        admin = UserFactory(is_staff=True)
        self.client.force_authenticate(user=admin)
        goal = ResearchGoalFactory()
        p = ProtocolFactory()
        resp = self.client.put(
            f'/api/v1/research-goals/{goal.id}/',
            {
                'name': goal.name, 'slug': goal.slug, 'summary': goal.summary,
                'priority': goal.priority, 'status': goal.status,
                'protocols': [p.id],
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.json())
        goal.refresh_from_db()
        self.assertEqual(list(goal.protocols.values_list('id', flat=True)), [p.id])

    def test_staff_can_clear_protocols(self):
        admin = UserFactory(is_staff=True)
        self.client.force_authenticate(user=admin)
        goal = ResearchGoalFactory()
        p = ProtocolFactory()
        goal.protocols.add(p)
        resp = self.client.put(
            f'/api/v1/research-goals/{goal.id}/',
            {
                'name': goal.name, 'slug': goal.slug, 'summary': goal.summary,
                'priority': goal.priority, 'status': goal.status,
                'protocols': [],
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.json())
        goal.refresh_from_db()
        self.assertEqual(list(goal.protocols.values_list('id', flat=True)), [])

    def test_non_staff_cannot_update_protocols(self):
        user = UserFactory(is_staff=False)
        self.client.force_authenticate(user=user)
        goal = ResearchGoalFactory()
        p = ProtocolFactory()
        resp = self.client.put(
            f'/api/v1/research-goals/{goal.id}/',
            {
                'name': goal.name, 'slug': goal.slug, 'summary': goal.summary,
                'priority': goal.priority, 'status': goal.status,
                'protocols': [p.id],
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 403)


class ApplicationAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        # 同 ResearchGoalAPITest：以 staff 身份查看全量数据。
        self.client.force_authenticate(user=UserFactory(is_staff=True))

    def test_list(self):
        ApplicationFactory.create_batch(2)
        resp = self.client.get('/api/v1/applications/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['data']), 2)

    def test_list_fields(self):
        ApplicationFactory()
        resp = self.client.get('/api/v1/applications/')
        data = resp.json()['data'][0]
        self.assertIn('id', data)
        self.assertIn('name', data)
        self.assertIn('slug', data)
        self.assertIn('research_goal_id', data)
        self.assertIn('research_goal_name', data)
        self.assertIn('research_goals', data)

    def test_detail_includes_methods(self):
        app = ApplicationFactory()
        resp = self.client.get(f'/api/v1/applications/{app.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('methods', resp.json()['data'])

    def test_detail_includes_protocols(self):
        app = ApplicationFactory()
        resp = self.client.get(f'/api/v1/applications/{app.id}/')
        self.assertIn('protocols', resp.json()['data'])

    def test_detail_includes_products(self):
        app = ApplicationFactory()
        resp = self.client.get(f'/api/v1/applications/{app.id}/')
        self.assertIn('products', resp.json()['data'])

    def test_detail_methods_populated(self):
        app = ApplicationFactory()
        method = MethodFactory(application=app)
        resp = self.client.get(f'/api/v1/applications/{app.id}/')
        data = resp.json()['data']
        method_ids = [m['id'] for m in data['methods']]
        self.assertIn(method.id, method_ids)

    def test_filter_by_research_goal_id(self):
        goal = ResearchGoalFactory()
        app = ApplicationFactory()
        app.research_goal_collections.add(goal)  # #P0-1：过滤改走 M2M
        ApplicationFactory()  # different goal
        resp = self.client.get(f'/api/v1/applications/?research_goal_id={goal.id}')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_filter_by_status(self):
        ApplicationFactory(status='active')
        ApplicationFactory(status='draft')
        resp = self.client.get('/api/v1/applications/?status=active')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_search(self):
        ApplicationFactory(name='RNA Labeling')
        ApplicationFactory(name='DNA Sequencing')
        resp = self.client.get('/api/v1/applications/?search=RNA')
        self.assertEqual(len(resp.json()['data']), 1)


class ApplicationM2MAPITest(TestCase):
    """#P0-1：RG↔AP 关联 API 读 M2M（application_collection）路径验证。

    T4 顶部链真实关联存于 M2M（84,555 条）；FK research_goal 仅 8 条策展。
    API 读取（research_goal_id/name/research_goals/计数/上溯）必须走 M2M，
    写路径（决策 B1）写 FK 并同步 M2M、仅显式变更才动 M2M。
    """

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=UserFactory(is_staff=True))

    # ---- 读路径：M2M 首个 + 多值数组 ----

    def test_list_research_goal_reads_m2m_first(self):
        rg1 = ResearchGoalFactory(name='RG First')
        rg2 = ResearchGoalFactory(name='RG Second')
        app = ApplicationFactory()  # FK 为空
        # 仅建 M2M，不建 FK：T4 导入的真实形态
        app.research_goal_collections.add(rg1)
        app.research_goal_collections.add(rg2)
        resp = self.client.get('/api/v1/applications/')
        data = resp.json()['data'][0]
        self.assertEqual(data['research_goal_id'], rg1.id)  # id 升序首个
        self.assertEqual(data['research_goal_name'], 'RG First')
        self.assertEqual(data['research_goals'], [
            {'id': rg1.id, 'name': 'RG First'},
            {'id': rg2.id, 'name': 'RG Second'},
        ])

    def test_list_research_goal_empty_m2m(self):
        ApplicationFactory()
        resp = self.client.get('/api/v1/applications/')
        data = resp.json()['data'][0]
        self.assertIsNone(data['research_goal_id'])
        self.assertIsNone(data['research_goal_name'])
        self.assertEqual(data['research_goals'], [])

    def test_detail_research_goal_reads_m2m(self):
        rg1 = ResearchGoalFactory(name='Detail RG')
        rg2 = ResearchGoalFactory(name='Detail RG 2')
        app = ApplicationFactory()
        app.research_goal_collections.add(rg1)
        app.research_goal_collections.add(rg2)
        resp = self.client.get(f'/api/v1/applications/{app.id}/')
        data = resp.json()['data']
        self.assertEqual(data['research_goal_id'], rg1.id)
        self.assertEqual(data['research_goal_name'], 'Detail RG')
        self.assertEqual(len(data['research_goals']), 2)

    def test_research_goal_application_count_counts_m2m(self):
        rg = ResearchGoalFactory()
        app1 = ApplicationFactory()
        app2 = ApplicationFactory()
        rg.application_collection.add(app1)
        rg.application_collection.add(app2)
        resp = self.client.get('/api/v1/research-goals/')
        for row in resp.json()['data']:
            if row['id'] == rg.id:
                self.assertEqual(row['application_count'], 2)
                break
        else:  # pragma: no cover
            self.fail('RG 不在列表响应中')

    def test_research_goal_detail_includes_application_collection(self):
        rg = ResearchGoalFactory(name='Goal X')
        app = ApplicationFactory(name='App Y')
        rg.application_collection.add(app)
        resp = self.client.get(f'/api/v1/research-goals/{rg.id}/')
        data = resp.json()['data']
        ids = [x['id'] for x in data['application_collection']]
        self.assertIn(app.id, ids)

    # ---- 写路径：决策 B1 ----

    def test_create_syncs_fk_and_m2m(self):
        rg = ResearchGoalFactory()
        resp = self.client.post('/api/v1/applications/', {
            'name': 'New App', 'slug': 'new-app', 'summary': '',
            'research_goal_id': rg.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        app = Application.objects.get(pk=resp.json()['data']['id'])
        self.assertEqual(app.research_goal_id, rg.id)  # FK 已写
        self.assertEqual(set(app.research_goal_collections.all()), {rg})  # M2M 已同步

    def test_update_change_goal_sets_m2m(self):
        rg_old = ResearchGoalFactory(name='Old Goal')
        rg_new = ResearchGoalFactory(name='New Goal')
        app = ApplicationFactory(research_goal=rg_old)
        app.research_goal_collections.add(rg_old)
        resp = self.client.patch(f'/api/v1/applications/{app.id}/', {
            'research_goal_id': rg_new.id,
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.research_goal_id, rg_new.id)  # FK 更新
        self.assertEqual(set(app.research_goal_collections.all()), {rg_new})  # M2M set 为新值

    def test_update_other_fields_does_not_touch_m2m(self):
        """编辑其它字段（不提交 research_goal_id）绝不动 M2M——T4 多值关联受保护。"""
        rg1 = ResearchGoalFactory(name='RG A')
        rg2 = ResearchGoalFactory(name='RG B')
        app = ApplicationFactory()
        app.research_goal_collections.add(rg1)
        app.research_goal_collections.add(rg2)
        resp = self.client.patch(f'/api/v1/applications/{app.id}/', {
            'summary': 'updated summary only',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(set(app.research_goal_collections.all()), {rg1, rg2})  # 原样保留

    def test_update_clear_goal_removes_from_m2m_keeps_others(self):
        """显式清空（research_goal_id=null）：FK 置空 + 该 RG 从 M2M 移除，其它 RG 保留。"""
        rg_owned = ResearchGoalFactory(name='Owned')
        rg_other = ResearchGoalFactory(name='Other')
        app = ApplicationFactory(research_goal=rg_owned)
        app.research_goal_collections.add(rg_owned)
        app.research_goal_collections.add(rg_other)
        resp = self.client.patch(f'/api/v1/applications/{app.id}/', {
            'research_goal_id': None,
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        app.refresh_from_db()
        self.assertIsNone(app.research_goal_id)  # FK 置空
        self.assertEqual(set(app.research_goal_collections.all()), {rg_other})  # 保留其它 M2M

    def test_update_invalid_goal_id_400(self):
        app = ApplicationFactory()
        resp = self.client.patch(f'/api/v1/applications/{app.id}/', {
            'research_goal_id': 999999,
        }, format='json')
        self.assertEqual(resp.status_code, 400)


class ApplicationM2MProtocolUpstreamTest(TestCase):
    """#P0-1：Protocol 详情 get_methods 的 RG 上溯走 M2M（research_goal_collections）。"""

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=UserFactory(is_staff=True))

    def test_protocol_methods_research_goal_upstreams_m2m(self):
        rg = ResearchGoalFactory(name='Upstream RG')
        app = ApplicationFactory()
        app.research_goal_collections.add(rg)  # M2M 关联（T4 形态）
        method = MethodFactory(application=app)
        proto = ProtocolFactory()
        MethodProtocolFactory(method=method, protocol=proto, status='active')
        resp = self.client.get(f'/api/v1/protocols/{proto.id}/')
        self.assertEqual(resp.status_code, 200)
        methods = resp.json()['data']['methods']
        self.assertEqual(len(methods), 1)
        row = methods[0]
        self.assertEqual(row['application_id'], app.id)
        self.assertEqual(row['research_goal_id'], rg.id)
        self.assertEqual(row['research_goal_name'], 'Upstream RG')
        self.assertEqual(row['research_goals'], [{'id': rg.id, 'name': 'Upstream RG'}])

    def test_protocol_methods_no_application_returns_null_rg(self):
        method = MethodFactory(application=None)  # 显式无 application（Factory 默认会建一个）
        proto = ProtocolFactory()
        MethodProtocolFactory(method=method, protocol=proto, status='active')
        resp = self.client.get(f'/api/v1/protocols/{proto.id}/')
        row = resp.json()['data']['methods'][0]
        self.assertIsNone(row['application_id'])
        self.assertIsNone(row['research_goal_id'])
        self.assertEqual(row['research_goals'], [])


class MethodAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        # 同 ResearchGoalAPITest：以 staff 身份查看全量数据。
        self.client.force_authenticate(user=UserFactory(is_staff=True))

    def test_list(self):
        MethodFactory.create_batch(2)
        resp = self.client.get('/api/v1/methods/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['data']), 2)

    def test_list_fields(self):
        MethodFactory()
        resp = self.client.get('/api/v1/methods/')
        data = resp.json()['data'][0]
        self.assertIn('id', data)
        self.assertIn('name', data)
        self.assertIn('application_id', data)

    def test_detail_includes_protocols(self):
        method = MethodFactory()
        resp = self.client.get(f'/api/v1/methods/{method.id}/')
        self.assertIn('protocols', resp.json()['data'])

    def test_detail_includes_products(self):
        method = MethodFactory()
        resp = self.client.get(f'/api/v1/methods/{method.id}/')
        self.assertIn('products', resp.json()['data'])

    def test_detail_protocols_populated(self):
        method = MethodFactory()
        protocol = ProtocolFactory()
        MethodProtocol.objects.create(method=method, protocol=protocol)
        resp = self.client.get(f'/api/v1/methods/{method.id}/')
        data = resp.json()['data']
        protocol_ids = [p['id'] for p in data['protocols']]
        self.assertIn(protocol.id, protocol_ids)

    def test_detail_products_populated(self):
        method = MethodFactory()
        pm = ProductMethodFactory(method=method)
        resp = self.client.get(f'/api/v1/methods/{method.id}/')
        data = resp.json()['data']
        product_ids = [p['id'] for p in data['products']]
        self.assertIn(pm.product_id, product_ids)

    def test_filter_by_application_id(self):
        app = ApplicationFactory()
        MethodFactory(application=app)
        MethodFactory()  # different app
        resp = self.client.get(f'/api/v1/methods/?application_id={app.id}')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_filter_by_status(self):
        MethodFactory(status='active')
        MethodFactory(status='draft')
        resp = self.client.get('/api/v1/methods/?status=active')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_search(self):
        MethodFactory(name='Sanger Sequencing')
        MethodFactory(name='PCR')
        resp = self.client.get('/api/v1/methods/?search=Sanger')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_json_ld_endpoint(self):
        method = MethodFactory(name='Sanger Sequencing')
        resp = self.client.get(f'/api/v1/methods/{method.id}/json-ld/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # EnvelopeRenderer wraps: {success: True, data: {<jsonld>}, meta: {}}
        jsonld = data.get('data', data)
        self.assertIn('@context', jsonld)
        self.assertIn('@type', jsonld)


class KnowledgePublicVisibilityTest(TestCase):
    """BUG-2a 回归测试：公开端点（匿名）仅返回已发布(ACTIVE)记录，草稿对匿名不可见。

    对应源码修复：ResearchGoal/Application/Method 三个 ViewSet 的 get_queryset
    对匿名及普通用户过滤 status=ACTIVE，仅 staff 可访问全量（含草稿/归档）。
    这些用例刻意以匿名客户端发起，锁定该安全行为不被回退。
    """

    def setUp(self):
        self.client = APIClient()

    def test_research_goal_anonymous_sees_only_active(self):
        ResearchGoalFactory(status=ResearchGoal.Status.DRAFT)
        ResearchGoalFactory(status=ResearchGoal.Status.ACTIVE)
        resp = self.client.get('/api/v1/research-goals/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['data']), 1)

    def test_research_goal_draft_invisible_to_anonymous(self):
        goal = ResearchGoalFactory(status=ResearchGoal.Status.DRAFT)
        resp = self.client.get(f'/api/v1/research-goals/{goal.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_application_anonymous_sees_only_active(self):
        ApplicationFactory(status=Application.Status.DRAFT)
        ApplicationFactory(status=Application.Status.ACTIVE)
        resp = self.client.get('/api/v1/applications/')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_method_anonymous_sees_only_active(self):
        MethodFactory(status=Method.Status.DRAFT)
        MethodFactory(status=Method.Status.ACTIVE)
        resp = self.client.get('/api/v1/methods/')
        self.assertEqual(len(resp.json()['data']), 1)


class ProtocolAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_list(self):
        ProtocolFactory.create_batch(2)
        resp = self.client.get('/api/v1/protocols/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['data']), 2)

    def test_list_fields(self):
        ProtocolFactory()
        resp = self.client.get('/api/v1/protocols/')
        data = resp.json()['data'][0]
        self.assertIn('id', data)
        self.assertIn('name', data)
        self.assertIn('version', data)
        self.assertNotIn('method_id', data)

    def test_detail_includes_steps(self):
        protocol = ProtocolFactory()
        ProtocolStepFactory(protocol=protocol, step_no=1)
        ProtocolStepFactory(protocol=protocol, step_no=2)
        resp = self.client.get(f'/api/v1/protocols/{protocol.id}/')
        data = resp.json()['data']
        self.assertEqual(len(data['steps']), 2)
        self.assertEqual(data['steps'][0]['step_no'], 1)

    def test_detail_step_fields(self):
        protocol = ProtocolFactory()
        step = ProtocolStepFactory(protocol=protocol, step_no=1, title='Prepare')
        resp = self.client.get(f'/api/v1/protocols/{protocol.id}/')
        step_data = resp.json()['data']['steps'][0]
        self.assertIn('id', step_data)
        self.assertIn('step_no', step_data)
        self.assertIn('title', step_data)
        self.assertIn('body', step_data)

    def test_detail_includes_references(self):
        protocol = ProtocolFactory()
        resp = self.client.get(f'/api/v1/protocols/{protocol.id}/')
        self.assertIn('references', resp.json()['data'])

    def test_detail_includes_products(self):
        protocol = ProtocolFactory()
        resp = self.client.get(f'/api/v1/protocols/{protocol.id}/')
        self.assertIn('products', resp.json()['data'])

    def test_protocol_linked_to_method_appears_in_list(self):
        method = MethodFactory()
        protocol = ProtocolFactory()
        MethodProtocol.objects.create(method=method, protocol=protocol)
        ProtocolFactory()  # unrelated protocol
        resp = self.client.get('/api/v1/protocols/')
        data = resp.json()['data']
        self.assertEqual(len(data), 2)
        protocol_ids = [p['id'] for p in data]
        self.assertIn(protocol.id, protocol_ids)
        # 桥接关系成立（替代已删除的 ?method_id= 过滤）
        self.assertTrue(
            MethodProtocol.objects.filter(method=method, protocol=protocol).exists()
        )

    def test_filter_by_status(self):
        ProtocolFactory(status='published')
        ProtocolFactory(status='draft')
        resp = self.client.get('/api/v1/protocols/?status=published')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_search(self):
        ProtocolFactory(name='RNA Labeling Protocol')
        ProtocolFactory(name='DNA Extraction')
        resp = self.client.get('/api/v1/protocols/?search=RNA')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_json_ld_endpoint(self):
        protocol = ProtocolFactory(name='RNA Protocol')
        resp = self.client.get(f'/api/v1/protocols/{protocol.id}/json-ld/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # EnvelopeRenderer wraps: {success: True, data: {<jsonld>}, meta: {}}
        jsonld = data.get('data', data)
        self.assertIn('@context', jsonld)
        self.assertIn('@type', jsonld)
        self.assertIn('step', jsonld)


class ReferenceAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_list(self):
        ReferenceFactory.create_batch(2)
        resp = self.client.get('/api/v1/references/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['data']), 2)

    def test_list_fields(self):
        ReferenceFactory()
        resp = self.client.get('/api/v1/references/')
        data = resp.json()['data'][0]
        self.assertIn('id', data)
        self.assertIn('title', data)
        self.assertIn('authors', data)
        self.assertIn('doi', data)
        self.assertIn('pmid', data)

    def test_detail(self):
        ref = ReferenceFactory(title='Nature 2024', doi='10.1038/test')
        resp = self.client.get(f'/api/v1/references/{ref.id}/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(data['title'], 'Nature 2024')
        self.assertEqual(data['doi'], '10.1038/test')

    def test_search_by_title(self):
        ReferenceFactory(title='Nature Paper')
        ReferenceFactory(title='Science Paper')
        resp = self.client.get('/api/v1/references/?search=Nature')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_search_by_doi(self):
        ReferenceFactory(doi='10.1038/unique')
        ReferenceFactory(doi='10.1126/other')
        resp = self.client.get('/api/v1/references/?search=10.1038')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_filter_by_source_type(self):
        ReferenceFactory(source_type='journal')
        ReferenceFactory(source_type='book')
        resp = self.client.get('/api/v1/references/?source_type=journal')
        self.assertEqual(len(resp.json()['data']), 1)


class CompatibilityAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_list(self):
        CompatibilityFactory.create_batch(2)
        resp = self.client.get('/api/v1/compatibility/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['data']), 2)

    def test_list_fields(self):
        CompatibilityFactory()
        resp = self.client.get('/api/v1/compatibility/')
        data = resp.json()['data'][0]
        self.assertIn('id', data)
        self.assertIn('code', data)
        self.assertIn('scope', data)
        self.assertIn('rule_type', data)
        self.assertIn('severity', data)

    def test_detail(self):
        comp = CompatibilityFactory(code='COMP-001', rule_type='compatible')
        resp = self.client.get(f'/api/v1/compatibility/{comp.id}/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(data['code'], 'COMP-001')

    def test_filter_by_scope(self):
        CompatibilityFactory(scope='product-product')
        CompatibilityFactory(scope='product-method')
        resp = self.client.get('/api/v1/compatibility/?scope=product-product')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_filter_by_rule_type(self):
        CompatibilityFactory(rule_type='compatible')
        CompatibilityFactory(rule_type='incompatible')
        resp = self.client.get('/api/v1/compatibility/?rule_type=compatible')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_filter_by_severity(self):
        CompatibilityFactory(severity='info')
        CompatibilityFactory(severity='blocking')
        resp = self.client.get('/api/v1/compatibility/?severity=blocking')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_search_by_code(self):
        CompatibilityFactory(code='COMP-Alpha')
        CompatibilityFactory(code='COMP-Beta')
        resp = self.client.get('/api/v1/compatibility/?search=Alpha')
        self.assertEqual(len(resp.json()['data']), 1)
