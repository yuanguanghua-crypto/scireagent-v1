"""entity_merge 命令测试（TDD：先红后绿）。

覆盖：dry-run 统计不写库 / RG 簇 apply 合并+幂等 / AP 簇 apply /
AP.research_goal FK 迁移保护 / e2e 与测试夹具跳过 / 策展守卫 /
二次 apply 零改动 / chunk 失败回滚继续。
"""
import json

import pytest
from django.core.management import call_command

from apps.knowledge.models import Application, ResearchGoal
from apps.knowledge.tests.factories import (
    ApplicationFactory,
    ProtocolFactory,
    ResearchGoalFactory,
)


def _write_report(path, clusters, summary=None):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'summary': summary or {}, 'clusters': clusters}, f,
                  ensure_ascii=False)


def _rg_cluster(cluster_no, rep_id, member_ids, rep_name='Rep RG',
                has_curated=False):
    return {
        'group': 'rg', 'cluster': cluster_no, 'size': len(member_ids),
        'representative': rep_name, 'representative_id': rep_id,
        'has_curated': has_curated, 'members': [], 'member_ids': member_ids,
        'member_origins': {}, 'max_freq': 1,
    }


class TestDryRun:
    @pytest.mark.django_db
    def test_stats_correct_and_no_writes(self, tmp_path):
        """dry-run：统计正确、不写库（实体与关联都不动）。"""
        rep = ResearchGoalFactory(name='Rep RG', origin='imported')
        m1 = ResearchGoalFactory(name='Member One')
        m2 = ResearchGoalFactory(name='Member Two')
        p1 = ProtocolFactory(name='P1', slug='p1')
        p2 = ProtocolFactory(name='P2', slug='p2')
        a1 = ApplicationFactory(name='App One', slug='app-one', research_goal=None)
        a2 = ApplicationFactory(name='App Two', slug='app-two', research_goal=None)
        m1.protocols.add(p1)
        m2.protocols.add(p2)
        m1.application_collection.add(a1)
        m2.application_collection.add(a2)

        rpt = tmp_path / 'report.json'
        _write_report(rpt, [_rg_cluster(1, rep.id, [rep.id, m1.id, m2.id])])
        out = tmp_path / 'out.json'
        call_command('entity_merge', report=str(rpt), report_out=str(out))

        data = json.loads(out.read_text(encoding='utf-8'))
        s = data['stats']
        assert s['mode'] == 'dry-run'
        assert s['processed_clusters'] == 1
        assert s['merged_entities'] == 2
        assert s['created_entities'] == 0
        assert data['chunk_failures'] == []
        # 不写库：实体都在、代表关联未迁移
        assert ResearchGoal.objects.filter(pk__in=[rep.id, m1.id, m2.id]).count() == 3
        assert list(rep.protocols.all()) == []
        assert list(rep.application_collection.all()) == []


class TestApplyRG:
    @pytest.mark.django_db
    def test_rep_absorbs_relations_members_deleted_second_apply_zero(self, tmp_path):
        """RG 簇 apply：代表收拢 protocols + application_collection、成员被删；
        二次 apply 新建 0 / 删除 0。"""
        rep = ResearchGoalFactory(name='Rep RG', origin='imported')
        m1 = ResearchGoalFactory(name='Member One')
        m2 = ResearchGoalFactory(name='Member Two')
        p1 = ProtocolFactory(name='P1', slug='p1')
        p2 = ProtocolFactory(name='P2', slug='p2')
        a1 = ApplicationFactory(name='App One', slug='app-one', research_goal=None)
        a2 = ApplicationFactory(name='App Two', slug='app-two', research_goal=None)
        m1.protocols.add(p1)
        m2.protocols.add(p2)
        m1.application_collection.add(a1)
        m2.application_collection.add(a2)

        rpt = tmp_path / 'r.json'
        _write_report(rpt, [_rg_cluster(1, rep.id, [rep.id, m1.id, m2.id])])
        out = tmp_path / 'o.json'
        call_command('entity_merge', report=str(rpt), apply=True, report_out=str(out))

        s = json.loads(out.read_text(encoding='utf-8'))['stats']
        assert s['processed_clusters'] == 1
        assert s['merged_entities'] == 2
        assert ResearchGoal.objects.filter(pk=rep.id).exists()
        assert not ResearchGoal.objects.filter(pk__in=[m1.id, m2.id]).exists()
        assert set(rep.protocols.all()) == {p1, p2}
        assert set(rep.application_collection.all()) == {a1, a2}

        # 二次 apply 幂等：新建 0 / 删除 0
        call_command('entity_merge', report=str(rpt), apply=True, report_out=str(out))
        s2 = json.loads(out.read_text(encoding='utf-8'))['stats']
        assert s2['merged_entities'] == 0
        assert s2['created_entities'] == 0
        assert s2['skipped_missing'] >= 2
        assert ResearchGoal.objects.filter(pk__in=[m1.id, m2.id]).count() == 0


class TestApplyAP:
    @pytest.mark.django_db
    def test_collection_moves_to_rep_and_member_deleted(self, tmp_path):
        """AP 簇 apply：application_collection 从成员迁到代表、成员被删。"""
        rep_ap = ApplicationFactory(name='Rep AP', slug='rep-ap', research_goal=None)
        member_ap = ApplicationFactory(name='Member AP', slug='member-ap', research_goal=None)
        rg = ResearchGoalFactory(name='RG')
        rg.application_collection.add(member_ap)

        cluster = {
            'group': 'ap', 'cluster': 1, 'size': 2,
            'representative': rep_ap.name, 'representative_id': rep_ap.id,
            'has_curated': False, 'members': [member_ap.name],
            'member_ids': [rep_ap.id, member_ap.id], 'member_origins': {},
            'max_freq': 1,
        }
        rpt = tmp_path / 'r.json'
        _write_report(rpt, [cluster])
        call_command('entity_merge', report=str(rpt), apply=True)

        assert not Application.objects.filter(pk=member_ap.id).exists()
        assert Application.objects.filter(pk=rep_ap.id).exists()
        assert set(rg.application_collection.all()) == {rep_ap}


class TestFkGuard:
    @pytest.mark.django_db
    def test_fk_relocated_to_rep_not_cascade_deleted(self, tmp_path):
        """AP.research_goal 指向被删 RG → 迁移到代表 RG（不级联删 AP）。"""
        member_rg = ResearchGoalFactory(name='Member RG')
        rep_rg = ResearchGoalFactory(name='Rep RG', origin='imported')
        ap = ApplicationFactory(name='AP under member', slug='ap-under-member',
                                research_goal=member_rg)

        rpt = tmp_path / 'r.json'
        _write_report(rpt, [_rg_cluster(1, rep_rg.id, [rep_rg.id, member_rg.id])])
        out = tmp_path / 'o.json'
        call_command('entity_merge', report=str(rpt), apply=True, report_out=str(out))

        s = json.loads(out.read_text(encoding='utf-8'))['stats']
        assert s['reloc_fk_aps'] == 1
        assert not ResearchGoal.objects.filter(pk=member_rg.id).exists()
        # AP 未被级联删除，FK 已改指向代表
        ap.refresh_from_db()
        assert ap.research_goal_id == rep_rg.id


class TestSkipE2EFixture:
    @pytest.mark.django_db
    def test_e2e_and_fixture_members_skipped(self, tmp_path):
        """e2e（__e2e_ 前缀）与 is_test_fixture 实体跳过不参与合并。"""
        rep = ResearchGoalFactory(name='Rep RG', origin='imported')
        e2e = ResearchGoalFactory(name='__e2e_residue', slug='e2e-residue')
        fx = ResearchGoalFactory(name='Fixture RG', slug='fixture-rg',
                                 is_test_fixture=True)
        normal = ResearchGoalFactory(name='Normal Member', slug='normal-member')
        p1 = ProtocolFactory(name='P1', slug='p1')
        normal.protocols.add(p1)

        rpt = tmp_path / 'r.json'
        _write_report(rpt, [_rg_cluster(1, rep.id, [rep.id, e2e.id, fx.id, normal.id])])
        out = tmp_path / 'o.json'
        call_command('entity_merge', report=str(rpt), apply=True, report_out=str(out))

        assert ResearchGoal.objects.filter(pk__in=[e2e.id, fx.id]).exists()
        assert not ResearchGoal.objects.filter(pk=normal.id).exists()
        s = json.loads(out.read_text(encoding='utf-8'))['stats']
        assert s['skipped_e2e'] == 2
        assert s['merged_entities'] == 1
        assert set(rep.protocols.all()) == {p1}


class TestCurationGuard:
    @pytest.mark.django_db
    def test_has_curated_with_non_curated_rep_skipped(self, tmp_path):
        """代表非策展但含策展成员（has_curated=True）→ 防御跳过整簇。"""
        rep = ResearchGoalFactory(name='AI Rep', origin='ai_extracted')
        curated_member = ResearchGoalFactory(name='Curated Member', slug='curated-member',
                                             origin='human_curated')

        rpt = tmp_path / 'r.json'
        _write_report(rpt, [_rg_cluster(1, rep.id, [rep.id, curated_member.id],
                                        rep_name='AI Rep', has_curated=True)])
        out = tmp_path / 'o.json'
        call_command('entity_merge', report=str(rpt), apply=True, report_out=str(out))

        s = json.loads(out.read_text(encoding='utf-8'))['stats']
        assert s['skipped_guard'] == 1
        assert s['processed_clusters'] == 0
        assert ResearchGoal.objects.filter(pk__in=[rep.id, curated_member.id]).count() == 2

    @pytest.mark.django_db
    def test_has_curated_with_imported_rep_processes(self, tmp_path):
        """正向：has_curated=True 且代表为 imported → 正常合并。"""
        rep = ResearchGoalFactory(name='Imported Rep', origin='imported')
        m = ResearchGoalFactory(name='Member', slug='member')

        rpt = tmp_path / 'r.json'
        _write_report(rpt, [_rg_cluster(1, rep.id, [rep.id, m.id],
                                        rep_name='Imported Rep', has_curated=True)])
        out = tmp_path / 'o.json'
        call_command('entity_merge', report=str(rpt), apply=True, report_out=str(out))

        s = json.loads(out.read_text(encoding='utf-8'))['stats']
        assert s['skipped_guard'] == 0
        assert s['processed_clusters'] == 1
        assert s['merged_entities'] == 1
        assert not ResearchGoal.objects.filter(pk=m.id).exists()


class TestChunkFailure:
    @pytest.mark.django_db
    def test_failed_chunk_rolls_back_and_continues(self, tmp_path, monkeypatch):
        """chunk 内中途抛异常 → 回滚该 chunk、记录失败、继续后续 chunk。"""
        rep1 = ResearchGoalFactory(name='Rep1', origin='imported')
        m1 = ResearchGoalFactory(name='M1', slug='m1')
        rep2 = ResearchGoalFactory(name='Rep2', origin='imported')
        m2 = ResearchGoalFactory(name='M2', slug='m2')
        p1 = ProtocolFactory(name='P1', slug='p1')
        m1.protocols.add(p1)

        rpt = tmp_path / 'r.json'
        _write_report(rpt, [
            _rg_cluster(1, rep1.id, [rep1.id, m1.id], rep_name='Rep1'),
            _rg_cluster(2, rep2.id, [rep2.id, m2.id], rep_name='Rep2'),
        ])

        from apps.knowledge.management.commands.entity_merge import Command
        orig = Command._process_cluster
        calls = {'n': 0}

        def flaky(self, cluster):
            calls['n'] += 1
            result = orig(self, cluster)  # 先真实写库再抛异常 → 事务回滚
            if calls['n'] == 1:
                raise RuntimeError('boom')
            return result

        monkeypatch.setattr(Command, '_process_cluster', flaky)

        out = tmp_path / 'o.json'
        call_command('entity_merge', report=str(rpt), apply=True, chunk_size=1,
                     report_out=str(out))

        # 簇1 已回滚：成员仍在、关联未迁移
        assert ResearchGoal.objects.filter(pk=m1.id).exists()
        assert set(m1.protocols.all()) == {p1}
        assert set(rep1.protocols.all()) == set()
        # 簇2 正常处理：成员已删
        assert not ResearchGoal.objects.filter(pk=m2.id).exists()

        data = json.loads(out.read_text(encoding='utf-8'))
        s = data['stats']
        assert len(data['chunk_failures']) == 1
        assert 'boom' in data['chunk_failures'][0]['error']
        assert s['merged_entities'] == 1
        assert s['processed_clusters'] == 1


class TestCrossClusterRepSurvival:
    @pytest.mark.django_db
    def test_rep_deleted_by_earlier_cluster_skipped_not_fk_boom(self, tmp_path):
        """跨簇重叠：簇 A 的代表 X 同时是簇 B 的成员，且 B 的代表 Y 同时是
        簇 A 的成员。A 在报告中排前先处理，把 Y 合并删除；随后处理 B 时
        代表 Y 已不存在 → 应幂等跳过（skipped_missing +1），不抛 FK 错误、
        不污染数据。回归：此前预载快照仍认为 Y 存续，rep.protocols.add()
        会命中 FK 约束导致整 chunk 回滚。"""
        x = ResearchGoalFactory(name='Cluster-A Rep X', origin='imported')
        y = ResearchGoalFactory(name='Cluster-B Rep Y')
        p1 = ProtocolFactory(name='P-X', slug='p-x')
        x.protocols.add(p1)  # X 带 protocol：若 B 误用已删代表 Y 收拢，必触发 FK

        # 报告顺序：[A, B]，A 在前
        cluster_a = _rg_cluster('A', x.id, [x.id, y.id], rep_name='Cluster-A Rep X')
        cluster_b = _rg_cluster('B', y.id, [x.id, y.id], rep_name='Cluster-B Rep Y')
        rpt = tmp_path / 'r.json'
        _write_report(rpt, [cluster_a, cluster_b])
        out = tmp_path / 'o.json'
        call_command('entity_merge', report=str(rpt), apply=True,
                     report_out=str(out))

        data = json.loads(out.read_text(encoding='utf-8'))
        s = data['stats']
        # B 的代表 Y 已被 A 合并删除 → B 安全跳过，不抛 FK 错误、无 chunk 回滚
        assert data['chunk_failures'] == []
        assert s['skipped_missing'] == 1
        assert s['processed_clusters'] == 1
        assert s['merged_entities'] == 1
        # 数据不被污染：X 存续且收拢了自己的 protocol，Y 已被删
        assert ResearchGoal.objects.filter(pk=x.id).exists()
        assert not ResearchGoal.objects.filter(pk=y.id).exists()
        assert set(x.protocols.all()) == {p1}
