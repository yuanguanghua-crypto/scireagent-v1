"""generate_knowledge_summaries 命令 + SummaryGenerator 服务测试（TDD）。

覆盖：
1. 范围守卫：只处理 ACTIVE + 非 fixture + summary='' 的 RG/AP
2. 上下文构建：RG 走 protocols M2M / AP 走 research_goal_collections 两级
3. dry-run：只生成 JSONL，不落库
4. --apply：落库（update summary）
5. 空 summary 保留（LLM 返回空 → 不覆盖）
6. checkpoint 续跑：done 集跳过已完成实体，不重复调 LLM；JSONL 追加
"""
import io
import json
import os

import pytest
from django.core.management import call_command

from apps.knowledge.models import Application, ResearchGoal
from apps.knowledge.tests.factories import (
    ApplicationFactory, ProtocolFactory, ResearchGoalFactory,
)

pytestmark = pytest.mark.django_db


# --------------------------------------------------------------------------- #
# 测试桩：mock LLM，返回确定性 summary
# --------------------------------------------------------------------------- #
class FakeExtractor:
    """模拟 LLMExtractor：is_available=True，chat() 返回确定性文本。"""
    model = 'fake-model'

    def __init__(self, texts=None, default='Summary for entity.'):
        self.texts = texts or {}
        self.default = default
        self.calls = []
        self.is_available = True

    def chat(self, system_prompt, user_prompt, temperature=0):
        self.calls.append(user_prompt)
        for name, text in self.texts.items():
            if name in user_prompt:
                return text
        return self.default


@pytest.fixture
def fake_extractor():
    return FakeExtractor(texts={
        'Alpha RG': 'Alpha research goal summary.',
        'Beta AP': 'Beta application summary.',
    })


@pytest.fixture
def entities():
    rg = ResearchGoalFactory(name='Alpha RG', summary='', status=ResearchGoal.Status.ACTIVE)
    ap = ApplicationFactory(
        name='Beta AP', summary='', status=Application.Status.ACTIVE,
        research_goal=None,
    )
    return rg, ap


@pytest.fixture
def out_dir(tmp_path):
    return str(tmp_path)


def _run(extractor, out, **kw):
    from django.core.management import call_command as cc
    return cc(
        'generate_knowledge_summaries', extractor=extractor, out=out,
        workers=2, stdout=io.StringIO(), **kw,
    )


def _load_jsonl(path):
    with open(path, encoding='utf-8') as f:
        return [json.loads(l) for l in f]


# --------------------------------------------------------------------------- #
# 服务层
# --------------------------------------------------------------------------- #
def _make_generator(extractor):
    from apps.knowledge.services.summary_generator import SummaryGenerator
    return SummaryGenerator(extractor=extractor)


def test_scope_guard_only_active_non_fixture_empty_summary(fake_extractor):
    """范围守卫：draft/fixture/已 summary 的一律不处理。"""
    ResearchGoalFactory(name='Draft RG', summary='', status=ResearchGoal.Status.DRAFT)
    ResearchGoalFactory(
        name='Fixture RG', summary='', status=ResearchGoal.Status.ACTIVE,
        is_test_fixture=True,
    )
    ResearchGoalFactory(name='Filled RG', summary='already', status=ResearchGoal.Status.ACTIVE)
    gen = _make_generator(fake_extractor)
    names = [e.name for e in gen.fetch_pool()]
    assert 'Draft RG' not in names
    assert 'Fixture RG' not in names
    assert 'Filled RG' not in names


def test_context_rg_uses_protocols(fake_extractor):
    """RG 上下文：优先 protocols M2M（name+objective）。"""
    rg = ResearchGoalFactory(name='Alpha RG', summary='', status=ResearchGoal.Status.ACTIVE)
    proto = ProtocolFactory(name='Alpha Protocol', objective='Alpha objective text.')
    rg.protocols.add(proto)
    gen = _make_generator(fake_extractor)
    item = gen.build_item('research_goal', rg)
    assert 'Alpha Protocol' in item['user_prompt']
    assert 'Alpha objective text.' in item['user_prompt']
    assert item['context_sources'] == ['protocol']


def test_context_ap_uses_research_goal_collections(fake_extractor):
    """AP 上下文：research_goal_collections 反向 M2M 两级（RG 名 + RG 协议）。"""
    rg = ResearchGoalFactory(name='Alpha RG', summary='', status=ResearchGoal.Status.ACTIVE)
    proto = ProtocolFactory(name='RG Proto', objective='RG proto objective.')
    rg.protocols.add(proto)
    ap = ApplicationFactory(
        name='Beta AP', summary='', status=Application.Status.ACTIVE,
        research_goal=None,
    )
    rg.application_collection.add(ap)
    gen = _make_generator(fake_extractor)
    item = gen.build_item('application', ap)
    assert 'Alpha RG' in item['user_prompt']
    assert 'RG Proto' in item['user_prompt']
    assert 'RG proto objective.' in item['user_prompt']
    assert item['context_sources'] == ['research goal', 'protocol']


# --------------------------------------------------------------------------- #
# 命令层：dry-run / apply / checkpoint
# --------------------------------------------------------------------------- #
def test_dry_run_generates_jsonl_no_db_write(fake_extractor, entities, out_dir):
    """dry-run：生成 JSONL，DB summary 不变。"""
    rg, ap = entities
    out = os.path.join(out_dir, 'summaries.jsonl')
    _run(fake_extractor, out)
    rg.refresh_from_db()
    ap.refresh_from_db()
    assert rg.summary == '' and ap.summary == ''  # 未落库
    by_name = {r['entity_name']: r for r in _load_jsonl(out)}
    assert by_name['Alpha RG']['summary'] == 'Alpha research goal summary.'
    assert by_name['Beta AP']['summary'] == 'Beta application summary.'
    assert all(r['error'] is None for r in _load_jsonl(out))


def test_apply_writes_summary(fake_extractor, entities, out_dir):
    """--apply：落库 update summary。"""
    rg, ap = entities
    out = os.path.join(out_dir, 'summaries.jsonl')
    _run(fake_extractor, out, apply=True)
    rg.refresh_from_db()
    ap.refresh_from_db()
    assert rg.summary == 'Alpha research goal summary.'
    assert ap.summary == 'Beta application summary.'


def test_apply_keeps_empty_summary(entities, out_dir):
    """LLM 返回空字符串时，apply 不落库（保持空）。"""
    rg, ap = entities
    empty = FakeExtractor(texts={'Beta AP': ''})
    out = os.path.join(out_dir, 'summaries.jsonl')
    _run(empty, out, apply=True)
    rg.refresh_from_db()
    ap.refresh_from_db()
    assert rg.summary == 'Summary for entity.'  # 默认文本落库
    assert ap.summary == ''                      # 空返回 → 不落库


def test_checkpoint_resume_skips_done(fake_extractor, entities, out_dir):
    """checkpoint 续跑：done 集内实体不再调 LLM；JSONL 追加不丢已写行。"""
    rg, ap = entities
    out = os.path.join(out_dir, 'summaries.jsonl')
    ckpt = os.path.join(out_dir, 'ckpt.json')
    # 预置 checkpoint：Alpha RG 已完成
    with open(ckpt, 'w', encoding='utf-8') as f:
        json.dump({'done': [f'research_goal:{rg.id}']}, f)
    _run(fake_extractor, out, checkpoint=ckpt)
    # Alpha RG 不应被调 LLM；Beta AP 应被调
    prompts = fake_extractor.calls
    assert not any('Alpha RG' in p for p in prompts)
    assert any('Beta AP' in p for p in prompts)
    # checkpoint 已更新：两条都 done
    with open(ckpt, encoding='utf-8') as f:
        ckpt_data = json.load(f)
    assert f'research_goal:{rg.id}' in ckpt_data['done']
    assert f'application:{ap.id}' in ckpt_data['done']
    # JSONL 只有 Beta AP 一行（Alpha 未重跑）
    rows = _load_jsonl(out)
    assert [r['entity_name'] for r in rows] == ['Beta AP']


def test_run_twice_is_idempotent(fake_extractor, entities, out_dir):
    """连续跑两次：第二次 checkpoint 全 done → 不调 LLM、JSONL 不重复。"""
    rg, ap = entities
    out = os.path.join(out_dir, 'summaries.jsonl')
    ckpt = os.path.join(out_dir, 'ckpt.json')
    _run(fake_extractor, out, checkpoint=ckpt)
    calls_after_first = len(fake_extractor.calls)
    assert calls_after_first == 2
    _run(fake_extractor, out, checkpoint=ckpt)
    assert len(fake_extractor.calls) == calls_after_first  # 无新增调用
    rows = _load_jsonl(out)
    assert len(rows) == 2  # 不重复
    assert {r['entity_name'] for r in rows} == {'Alpha RG', 'Beta AP'}
