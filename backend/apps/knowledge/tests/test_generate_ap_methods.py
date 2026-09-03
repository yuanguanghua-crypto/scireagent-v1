"""generate_ap_methods 命令 + ApMethodGenerator 服务测试（TDD）。

T2：为无 Method 的 AP 补实验方法（新建 Method，status=draft，FK 挂 AP）。

覆盖：
1. 范围守卫：只处理 ACTIVE + 非 fixture + 无 methods 的 AP
2. 上下文构建：AP 走 research_goal_collections 两级（RG 名 + 协议）
3. dry-run：JSONL 生成，不新建 Method
4. --apply：新建 Method（status=draft、application=AP、origin=ai_extracted）
5. 空输出（LLM 返回 []）：不新建
6. 词表命中标记：in_lexicon 判定
7. checkpoint 续跑：done 集跳过
8. 幂等：apply 后 AP 已有 methods → 不再处理
"""
import io
import json
import os

import pytest
from django.core.management import call_command as cc

from apps.knowledge.models import Application, Method, ResearchGoal
from apps.knowledge.tests.factories import (
    ApplicationFactory, ProtocolFactory, ResearchGoalFactory,
)

pytestmark = pytest.mark.django_db


class FakeExtractor:
    """模拟 LLMExtractor：chat() 返回确定性 JSON 文本（T2 输出为 JSON 数组）。"""
    model = 'fake-model'

    def __init__(self, texts=None, default='{"methods": []}'):
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
        'Beta AP': '{"methods": ["PCR", "qPCR"]}',
    })


@pytest.fixture
def ap():
    return ApplicationFactory(
        name='Beta AP', summary='', status=Application.Status.ACTIVE,
        research_goal=None,
    )


@pytest.fixture
def out_dir(tmp_path):
    return str(tmp_path)


def _run(extractor, out, **kw):
    return cc(
        'generate_ap_methods', extractor=extractor, out=out,
        workers=2, stdout=io.StringIO(), **kw,
    )


def _load_jsonl(path):
    with open(path, encoding='utf-8') as f:
        return [json.loads(l) for l in f]


def _make_generator(extractor):
    from apps.knowledge.services.ap_method_generator import ApMethodGenerator
    return ApMethodGenerator(extractor=extractor)


# --------------------------------------------------------------------------- #
# 服务层
# --------------------------------------------------------------------------- #
def test_scope_guard_active_non_fixture_no_methods(fake_extractor):
    """范围守卫：draft/fixture/已有 methods 的 AP 一律不处理。"""
    ApplicationFactory(name='Draft AP', status=Application.Status.DRAFT)
    ApplicationFactory(
        name='Fixture AP', status=Application.Status.ACTIVE, is_test_fixture=True,
    )
    has_method = ApplicationFactory(name='Has Method AP', status=Application.Status.ACTIVE)
    Method.objects.create(name='PCR', application=has_method)
    gen = _make_generator(fake_extractor)
    names = [e.name for e in gen.fetch_pool()]
    assert 'Draft AP' not in names
    assert 'Fixture AP' not in names
    assert 'Has Method AP' not in names


def test_context_uses_research_goal_collections(fake_extractor):
    """上下文：AP 走 research_goal_collections 两级（RG 名 + RG 协议）。"""
    rg = ResearchGoalFactory(name='Alpha RG', summary='', status=ResearchGoal.Status.ACTIVE)
    proto = ProtocolFactory(name='RG Proto', objective='RG proto objective.')
    rg.protocols.add(proto)
    ap = ApplicationFactory(
        name='Beta AP', status=Application.Status.ACTIVE, research_goal=None,
    )
    rg.application_collection.add(ap)
    gen = _make_generator(fake_extractor)
    item = gen.build_item(ap)
    assert 'Alpha RG' in item['user_prompt']
    assert 'RG Proto' in item['user_prompt']
    assert 'RG proto objective.' in item['user_prompt']
    assert item['context_sources'] == ['research goal', 'protocol']


def test_lexicon_flags(fake_extractor):
    """in_lexicon 判定：词表内 vs 新名。"""
    Method.objects.create(name='PCR')  # 进词表（ACTIVE+DRAFT）
    gen = _make_generator(fake_extractor)
    assert 'PCR' in gen.lexicon()
    assert 'qPCR' not in gen.lexicon()


# --------------------------------------------------------------------------- #
# 命令层：dry-run / apply / checkpoint
# --------------------------------------------------------------------------- #
def test_dry_run_generates_jsonl_no_db_write(fake_extractor, ap, out_dir):
    """dry-run：生成 JSONL，不新建 Method。"""
    out = os.path.join(out_dir, 'ap_methods.jsonl')
    _run(fake_extractor, out)
    assert Method.objects.count() == 0  # 未落库
    rows = _load_jsonl(out)
    assert len(rows) == 1
    assert rows[0]['ap_name'] == 'Beta AP'
    names = [m['name'] for m in rows[0]['methods']]
    assert names == ['PCR', 'qPCR']
    assert rows[0]['error'] is None


def test_apply_creates_methods(fake_extractor, ap, out_dir):
    """--apply：新建 Method（draft、挂 AP、origin=ai_extracted）。"""
    out = os.path.join(out_dir, 'ap_methods.jsonl')
    _run(fake_extractor, out, apply=True)
    methods = list(Method.objects.filter(application=ap))
    assert len(methods) == 2
    assert {m.name for m in methods} == {'PCR', 'qPCR'}
    assert all(m.status == Method.Status.DRAFT for m in methods)
    assert all(m.origin == 'ai_extracted' for m in methods)
    assert all(m.slug for m in methods)  # slug 自动生成


def test_apply_empty_output_creates_nothing(ap, out_dir):
    """LLM 返回空数组：不新建任何 Method。"""
    empty = FakeExtractor(default='{"methods": []}')
    out = os.path.join(out_dir, 'ap_methods.jsonl')
    _run(empty, out, apply=True)
    assert Method.objects.count() == 0


def test_checkpoint_resume_skips_done(fake_extractor, ap, out_dir):
    """checkpoint 续跑：done 集内 AP 不再调 LLM。"""
    out = os.path.join(out_dir, 'ap_methods.jsonl')
    ckpt = os.path.join(out_dir, 'ckpt.json')
    with open(ckpt, 'w', encoding='utf-8') as f:
        json.dump({'done': [f'application:{ap.id}']}, f)
    _run(fake_extractor, out, checkpoint=ckpt)
    assert fake_extractor.calls == []  # 已 done，不调 LLM
    # 全 done 时无新结果，JSONL 不被创建/追加（已有内容也不丢）
    if os.path.exists(out):
        assert _load_jsonl(out) == []


def test_run_twice_is_idempotent(fake_extractor, ap, out_dir):
    """apply 后再跑：AP 已有 methods → 不在池 → 不重复创建。"""
    out = os.path.join(out_dir, 'ap_methods.jsonl')
    ckpt = os.path.join(out_dir, 'ckpt.json')
    _run(fake_extractor, out, apply=True, checkpoint=ckpt)
    assert Method.objects.count() == 2
    calls_after_first = len(fake_extractor.calls)
    _run(fake_extractor, out, apply=True, checkpoint=ckpt)
    assert len(fake_extractor.calls) == calls_after_first  # 无新增 LLM 调用
    assert Method.objects.count() == 2  # 无重复创建
    assert len(_load_jsonl(out)) == 1   # JSONL 不重复


# --------------------------------------------------------------------------- #
# 方案 B：词表召回（prompt 瘦身）+ error 不进 checkpoint（T2 缺陷修复）
# --------------------------------------------------------------------------- #
class FailingExtractor:
    """恒定抛错的 extractor（模拟 402/429 批量失败）。"""
    model = 'fake-model'
    is_available = True

    def chat(self, system_prompt, user_prompt, temperature=0):
        raise RuntimeError('HTTP 402: Payment Required')


def test_recall_limits_prompt_to_candidates(fake_extractor):
    """方案 B 核心：prompt 只带召回候选（≤TOP_K），不再塞全量词表。

    背景：词表已 21,302 条，全量塞入 = 单次 ~16.9 万 tokens，是成本失控根因。
    """
    Method.objects.create(name='PCR')          # 与 AP 名相关 → 应被召回
    for i in range(80):                        # 撑大词表（无关方法）
        Method.objects.create(name=f'Unrelated Method {i}')
    ap = ApplicationFactory(
        name='PCR Amplification Application', summary='',
        status=Application.Status.ACTIVE, research_goal=None,
    )
    gen = _make_generator(fake_extractor)
    item = gen.build_item(ap)
    cands = item['candidates']
    assert len(Method.objects.all()) > 50          # 词表确实很大
    assert len(cands) <= 50                        # 候选被截断到 TOP_K
    assert 'PCR' in cands                          # 相关方法被召回
    # prompt 只列候选，不列全量词表
    sp = gen.system_prompt(cands)
    listed = [ln for ln in sp.splitlines() if ln.startswith('- ')]
    assert len(listed) <= 50
    assert '- Unrelated Method 79' not in sp       # 无关词表项不再进 prompt


def test_error_row_not_in_checkpoint_done(ap, out_dir):
    """T2 缺陷修复：error 行不进 checkpoint done → 重启自动重跑。

    原缺陷：generate_ap_methods 无条件 done.add() → 19,720 条 402 失败
    被永久跳过，形成 69% 静默数据缺口（T3 创建时已修正，T2 补修）。
    """
    out = os.path.join(out_dir, 'ap_err.jsonl')
    ckpt = os.path.join(out_dir, 'ckpt_err.json')
    _run(FailingExtractor(), out, checkpoint=ckpt)
    rows = _load_jsonl(out)
    assert len(rows) == 1 and rows[0]['error']      # 失败行照常写 JSONL
    done = json.load(open(ckpt, encoding='utf-8'))['done']
    assert done == []                               # 但不进 done → 重启重跑
