"""T2: extract_topchain_drafts 命令（dry-run + 无 key 降级 + 取样逻辑）。"""
import json

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.knowledge.tests.factories import ProtocolFactory


class TestNoKey:
    def test_command_errors_without_key(self, monkeypatch):
        monkeypatch.delenv('SCIREAGENT_LLM_API_KEY', raising=False)
        with pytest.raises(CommandError) as ei:
            call_command('extract_topchain_drafts', count=3)
        assert 'SCIREAGENT_LLM_API_KEY' in str(ei.value)


class TestSampling:
    @pytest.mark.django_db
    def test_picks_rich_protocols_by_objective(self, monkeypatch):
        """取样：objective/principle 非空的协议（正文丰富优先）。"""
        monkeypatch.setenv('SCIREAGENT_LLM_API_KEY', 'sk-test')
        # 构造 2 个富正文 + 1 个空正文
        ProtocolFactory(name='Rich P1', slug='rich-p1',
                        objective='A' * 50, principle='B' * 30)
        ProtocolFactory(name='Rich P2', slug='rich-p2',
                        objective='C' * 50, principle='D' * 30)
        ProtocolFactory(name='Empty P3', slug='empty-p3', objective='', principle='')
        # 阻止真实 LLM 调用：用 monkeypatch 替换 extract 方法
        import apps.knowledge.management.commands.extract_topchain_drafts as mod

        picked = []
        orig = mod.Command._pick_protocols

        def fake_pick(self, options):
            qs = orig(self, options)
            picked.append(list(qs.values_list('name', flat=True)))
            return qs[:0]  # 返回空 queryset 避免真实 LLM 调用

        monkeypatch.setattr(mod.Command, '_pick_protocols', fake_pick)
        call_command('extract_topchain_drafts', count=2)
        names = picked[0]
        assert 'Empty P3' not in names
        assert len(names) == 2


class TestReport:
    @pytest.mark.django_db
    def test_report_written_dry_run(self, monkeypatch, tmp_path):
        """--report 写 JSON（dry-run 模式），内容含 stats。"""
        monkeypatch.setenv('SCIREAGENT_LLM_API_KEY', 'sk-test')
        from apps.knowledge.services import llm_extractor as le

        def fake_extract(self, protocol_text, temperature=0):
            return {'research_goals': [{'name': 'RNA Analysis', 'confidence': 0.9}],
                    'applications': []}

        monkeypatch.setattr(le.LLMExtractor, 'extract_topchain', fake_extract)
        ProtocolFactory(name='T2 Proto', slug='t2-proto',
                        objective='RNA labeling', principle='chem',
                        reagents='dye')
        out = tmp_path / 't2_report.json'
        call_command('extract_topchain_drafts', count=10, report=str(out))
        data = json.loads(out.read_text(encoding='utf-8'))
        assert data['mode'] == 'dry-run'
        assert data['stats']['protocols'] >= 1
        assert data['rows'][0]['research_goals'][0]['name'] == 'RNA Analysis'
        # 黄金集 md 同目录生成
        assert (tmp_path / 't2_report_review.md').exists()


class TestConcurrency:
    @pytest.mark.django_db
    def test_workers_extract_all_rows(self, monkeypatch, tmp_path):
        """--workers 并发：所有协议都被提取且保序输出。"""
        monkeypatch.setenv('SCIREAGENT_LLM_API_KEY', 'sk-test')
        from apps.knowledge.services import llm_extractor as le
        from apps.knowledge.models import Protocol
        seen = {'n': 0}

        def fake_extract(self, protocol_text, temperature=0):
            seen['n'] += 1
            return {'research_goals': [{'name': f'RG-{seen["n"]}', 'confidence': 0.5}],
                    'applications': []}

        monkeypatch.setattr(le.LLMExtractor, 'extract_topchain', fake_extract)
        # 建 5 个协议
        for i in range(5):
            ProtocolFactory(name=f'Conc P{i}', slug=f'conc-p{i}',
                            objective='X' * 30, principle='Y')
        out = tmp_path / 'conc_report.json'
        call_command('extract_topchain_drafts', count=5, workers=4, report=str(out))
        data = json.loads(out.read_text(encoding='utf-8'))
        assert data['stats']['protocols'] == 5
        assert data['stats']['errors'] == 0
        # 保序：rows 索引与输入顺序一致（p.id 递增）
        ids = [r['protocol_id'] for r in data['rows']]
        assert ids == sorted(ids)
        # 每行都有提取结果
        for r in data['rows']:
            assert r['research_goals'], f'p={r["protocol_id"]} 缺 RG'
            assert r['error'] is None
