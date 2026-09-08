"""P1-1 canonical Method 收敛 —— 修复 P0 方法可见性回归。

回归根因：P0（52868ca, apply_public_visibility）正确地把 draft 挡在展示面外，
但门后没有已转正内容：生产 47,834 行 draft Method 全部 status='draft'，
导致 AP 详情 / 协议详情 / 图谱三处展示层覆盖率骤降。

修复策略（铁律：不删链、不改 47,834 行 draft status）：
- 建 canonical Method 实体（status='active', application=None, 名字=高频 draft 方法名）。
- 展示层统一「名字 → canonical」解析：draft 只提供名字，展示用 canonical 的 id/slug 输出。
- 协议详情 / 图谱侧需保留原 draft method 的 application 上溯（原 method.application）。

本测试覆盖：AP 详情、协议详情、图谱、build_canonical_methods 命令（dry-run/apply/幂等）。
"""
from io import StringIO

from django.test import TestCase
from django.core.management import call_command

from apps.knowledge.models import Method, Application, Protocol, ResearchGoal
from apps.knowledge.tests.factories import (
    ApplicationFactory,
    MethodFactory,
    ProtocolFactory,
    ResearchGoalFactory,
)
from apps.knowledge.api.v1.serializers import (
    ApplicationDetailSerializer,
    ProtocolDetailSerializer,
)
from apps.knowledge.services.graph_service import _protocol_neighbors
from apps.bridges.models import MethodProtocol


class ApplicationDetailCanonicalMethodsTests(TestCase):
    """AP 详情 get_methods：draft method 经 canonical 解析输出。"""

    def test_draft_method_resolves_to_canonical(self):
        ap = ApplicationFactory()
        MethodFactory(application=ap, name='PCR', status='draft')  # T2 补链遗留 draft
        canonical = MethodFactory(name='PCR', status='active', application=None)

        serializer = ApplicationDetailSerializer()
        result = serializer.get_methods(ap)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], canonical.id)
        self.assertEqual(result[0]['name'], 'PCR')
        self.assertEqual(result[0]['slug'], canonical.slug)

    def test_noise_name_without_canonical_is_dropped(self):
        ap = ApplicationFactory()
        MethodFactory(application=ap, name='某个只出现一次的怪名', status='draft')

        serializer = ApplicationDetailSerializer()
        result = serializer.get_methods(ap)

        self.assertEqual(result, [])

    def test_active_method_of_ap_is_output_directly(self):
        ap = ApplicationFactory()
        active = MethodFactory(application=ap, name='qPCR', status='active')

        serializer = ApplicationDetailSerializer()
        result = serializer.get_methods(ap)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], active.id)
        self.assertEqual(result[0]['slug'], active.slug)


class ProtocolDetailCanonicalMethodsTests(TestCase):
    """协议详情 get_methods：draft method 桥 → canonical id/slug，保留 application 上溯。"""

    def test_draft_method_bridge_returns_canonical_preserving_up_trace(self):
        rg = ResearchGoalFactory()
        ap = ApplicationFactory()
        ap.research_goal_collections.add(rg)

        draft_method = MethodFactory(application=ap, name='PCR', status='draft')
        canonical = MethodFactory(name='PCR', status='active', application=None)

        protocol = ProtocolFactory()
        MethodProtocol.objects.create(method=draft_method, protocol=protocol, status='active')

        serializer = ProtocolDetailSerializer()
        result = serializer.get_methods(protocol)

        entry = next(e for e in result if e['name'] == 'PCR')
        # id/slug 来自 canonical
        self.assertEqual(entry['id'], canonical.id)
        self.assertEqual(entry['slug'], canonical.slug)
        # application 上溯仍来自原 draft method 的 application（canonical.application 是 None）
        self.assertEqual(entry['application_id'], ap.id)
        self.assertEqual(entry['application_name'], ap.name)
        self.assertEqual(entry['research_goal_id'], rg.id)
        self.assertEqual(entry['research_goal_name'], rg.name)
        self.assertEqual(
            [r['id'] for r in entry['research_goals']], [rg.id]
        )

    def test_multiple_same_name_draft_methods_dedup_by_canonical(self):
        ap = ApplicationFactory()
        ap.research_goal_collections.add(ResearchGoalFactory())

        canonical = MethodFactory(name='PCR', status='active', application=None)
        protocol = ProtocolFactory()
        # 同名 draft method 出现两次（不同 AP），只应出一个 canonical
        for _ in range(2):
            other_ap = ApplicationFactory()
            draft = MethodFactory(application=other_ap, name='PCR', status='draft')
            MethodProtocol.objects.create(method=draft, protocol=protocol, status='active')

        serializer = ProtocolDetailSerializer()
        result = [e for e in serializer.get_methods(protocol) if e['name'] == 'PCR']

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], canonical.id)

    def test_active_method_bridge_output_directly(self):
        ap = ApplicationFactory()
        active = MethodFactory(application=ap, name='qPCR', status='active')
        protocol = ProtocolFactory()
        MethodProtocol.objects.create(method=active, protocol=protocol, status='active')

        serializer = ProtocolDetailSerializer()
        result = serializer.get_methods(protocol)

        entry = next(e for e in result if e['name'] == 'qPCR')
        self.assertEqual(entry['id'], active.id)

    def test_active_and_draft_same_name_deduped_to_one(self):
        # 缺陷回归：协议同时关联 active 同名 Method（带 application，生产 10 个 active 之一形态）
        # 和 draft 同名 Method（有 canonical）。canonical_by_name 只查 application=None 的
        # active，所以 active 不会被当 canonical 返回 —— 两者并存，必须按输出名去重到一条。
        rg = ResearchGoalFactory()
        ap = ApplicationFactory()
        ap.research_goal_collections.add(rg)

        active = MethodFactory(application=ap, name='PCR', status='active')
        draft = MethodFactory(application=ap, name='PCR', status='draft')
        MethodFactory(name='PCR', status='active', application=None)  # canonical

        protocol = ProtocolFactory()
        MethodProtocol.objects.create(method=active, protocol=protocol, status='active')
        MethodProtocol.objects.create(method=draft, protocol=protocol, status='active')

        serializer = ProtocolDetailSerializer()
        result = serializer.get_methods(protocol)
        pcrs = [e for e in result if e['name'] == 'PCR']

        self.assertEqual(len(pcrs), 1)  # 先到先得：active 先建（id 小）胜出
        self.assertEqual(pcrs[0]['id'], active.id)


class GraphProtocolNeighborsCanonicalTests(TestCase):
    """图谱 _protocol_neighbors：draft method 桥 → canonical id/name/slug。"""

    def test_draft_method_bridge_returns_canonical(self):
        ap = ApplicationFactory()
        draft_method = MethodFactory(application=ap, name='PCR', status='draft')
        canonical = MethodFactory(name='PCR', status='active', application=None)

        protocol = ProtocolFactory()
        MethodProtocol.objects.create(method=draft_method, protocol=protocol, status='active')

        neighbors = _protocol_neighbors(protocol.id)
        method_neighbors = [n for n in neighbors if n['target_type'] == 'method']
        entry = next(e for e in method_neighbors if e['target_label'] == 'PCR')

        self.assertEqual(entry['target_id'], canonical.id)
        self.assertEqual(entry['target_slug'], canonical.slug)
        self.assertEqual(entry['target_type'], 'method')


class BuildCanonicalMethodsCommandTests(TestCase):
    """build_canonical_methods 命令：dry-run 不落库 / apply 落库 / 幂等。"""

    def _seed_drafts(self, name, count):
        ap = ApplicationFactory()
        for _ in range(count):
            MethodFactory(application=ap, name=name, status='draft')

    def test_dry_run_does_not_write(self):
        self._seed_drafts('PCR', 15)
        self._seed_drafts('NoiseOnlyOnce', 1)  # 噪音名，低于 min-count

        before = Method.objects.count()
        out = StringIO()
        call_command('build_canonical_methods', min_count=10, stdout=out)
        after = Method.objects.count()

        self.assertEqual(before, after)  # dry-run 不落库
        self.assertIn('DRY-RUN', out.getvalue())

    def test_apply_creates_canonical_with_application_none(self):
        self._seed_drafts('PCR', 15)
        self._seed_drafts('Immunofluorescence Staining', 12)

        call_command('build_canonical_methods', min_count=10, apply=True)

        canonical = Method.objects.filter(
            status='active', application__isnull=True, name='PCR'
        )
        self.assertEqual(canonical.count(), 1)
        self.assertEqual(
            Method.objects.filter(
                status='active', application__isnull=True,
                name='Immunofluorescence Staining'
            ).count(), 1
        )

    def test_apply_is_idempotent(self):
        self._seed_drafts('PCR', 15)
        call_command('build_canonical_methods', min_count=10, apply=True)
        first = Method.objects.filter(status='active', application__isnull=True).count()

        call_command('build_canonical_methods', min_count=10, apply=True)
        second = Method.objects.filter(status='active', application__isnull=True).count()

        self.assertEqual(first, second)  # 第二次 apply 0 新增
        self.assertEqual(
            Method.objects.filter(name='PCR', status='active', application__isnull=True).count(), 1
        )

    def test_apply_skips_existing_active_same_name(self):
        # 已存在同名 active canonical（application=None），命令应复用不新建
        existing = MethodFactory(name='qPCR', status='active', application=None)
        self._seed_drafts('qPCR', 20)

        call_command('build_canonical_methods', min_count=10, apply=True)

        canonicals = Method.objects.filter(name='qPCR', status='active')
        self.assertEqual(canonicals.count(), 1)
        self.assertEqual(canonicals.first().id, existing.id)

    def test_apply_does_not_modify_draft_rows(self):
        self._seed_drafts('PCR', 15)
        draft_ids = set(Method.objects.filter(status='draft').values_list('id', flat=True))

        call_command('build_canonical_methods', min_count=10, apply=True)

        remaining = set(Method.objects.filter(status='draft').values_list('id', flat=True))
        self.assertEqual(draft_ids, remaining)  # draft 行完整保留

    def test_verify_reports_canonical_count(self):
        self._seed_drafts('PCR', 15)
        call_command('build_canonical_methods', min_count=10, apply=True)

        out = StringIO()
        call_command('build_canonical_methods', min_count=10, verify=True, stdout=out)
        self.assertIn('canonical', out.getvalue().lower())
