"""generate_protocol_methods 命令 + ProtocolMethodGenerator 服务测试（TDD）。

T3：为无 MethodProtocol 桥的 published 协议补实验方法——在规范方法词表
（排除 ai_extracted + archived 的闭集）上分类，建 MethodProtocol 桥
（evidence_source='llm_reviewed'），**不新建 Method 行**。

覆盖：
1. 范围守卫：只处理 published + 无桥的协议
2. 闭集词表：ai_extracted / archived 不进词表
3. dry-run：JSONL 生成，不建桥
4. --apply：建桥（llm_reviewed、不新建 Method 行）
5. 闭集外名称跳过（宁 miss 不错配）
6. 幂等：重复 apply 不重复建桥
7. checkpoint 续跑：done 集跳过
8. error 行不进 checkpoint done（T2 教训落地）
"""
import io
import json
import os

import pytest
from django.core.management import call_command as cc

from apps.bridges.models import MethodProtocol
from apps.knowledge.models import Method, Protocol
from apps.knowledge.tests.factories import (
    ApplicationFactory, MethodFactory, ProtocolFactory,
)

pytestmark = pytest.mark.django_db


class FakeExtractor:
    """模拟 LLMExtractor：chat() 按协议名返回确定性 JSON。"""
    model = 'fake-model'
    is_available = True

    def __init__(self, texts=None, default='{"methods": []}'):
        self.texts = texts or {}
        self.default = default
        self.calls = []

    def chat(self, system_prompt, user_prompt, temperature=0):
        self.calls.append(user_prompt)
        for name, text in self.texts.items():
            if name in user_prompt:
                return text
        return self.default


class FailingExtractor:
    """恒定抛错（模拟 402/429）。"""
    model = 'fake-model'
    is_available = True

    def chat(self, system_prompt, user_prompt, temperature=0):
        raise RuntimeError('HTTP 402: Payment Required')


@pytest.fixture
def fake_extractor():
    return FakeExtractor(texts={
        'DNA Extraction Proto': '{"methods": ["PCR", "Gel Electrophoresis"]}',
    })


@pytest.fixture
def canonical_method():
    """规范方法（非 ai_extracted → 进闭集词表）。"""
    return MethodFactory(name='PCR', application=ApplicationFactory())


@pytest.fixture
def proto():
    return ProtocolFactory(
        name='DNA Extraction Proto', objective='Extract genomic DNA from cells.',
        status=Protocol.PublicationStatus.PUBLISHED,
    )


@pytest.fixture
def out_dir(tmp_path):
    return str(tmp_path)


def _run(extractor, out, **kw):
    return cc(
        'generate_protocol_methods', extractor=extractor, out=out,
        workers=2, stdout=io.StringIO(), **kw,
    )


def _load_jsonl(path):
    with open(path, encoding='utf-8') as f:
        return [json.loads(l) for l in f]


def _make_generator(extractor):
    from apps.knowledge.services.protocol_method_generator import ProtocolMethodGenerator
    return ProtocolMethodGenerator(extractor=extractor)


# --------------------------------------------------------------------------- #
# 服务层
# --------------------------------------------------------------------------- #
def test_scope_guard_published_no_bridge(fake_extractor, canonical_method, proto):
    """范围守卫：draft / superseded / 已有桥的协议不进池。"""
    ProtocolFactory(name='Draft Proto', status=Protocol.PublicationStatus.DRAFT)
    ProtocolFactory(name='Archived Proto', status=Protocol.PublicationStatus.ARCHIVED)
    with_bridge = ProtocolFactory(
        name='Bridged Proto', status=Protocol.PublicationStatus.PUBLISHED,
    )
    MethodProtocol.objects.create(method=canonical_method, protocol=with_bridge)
    gen = _make_generator(fake_extractor)
    names = [p.name for p in gen.fetch_pool()]
    assert names == ['DNA Extraction Proto']


def test_lexicon_closed_set_excludes_ai_extracted_and_archived(fake_extractor, canonical_method):
    """闭集词表：ai_extracted 与 archived 的 Method 不进词表。"""
    MethodFactory(name='T2 Exploded Method', application=ApplicationFactory(),
                  origin='ai_extracted')
    MethodFactory(name='Old Archived Method', application=ApplicationFactory(),
                  status=Method.Status.ARCHIVED)
    gen = _make_generator(fake_extractor)
    assert gen.lexicon() == {'PCR'}


def test_probe_one_marks_lexicon(fake_extractor, canonical_method, proto):
    """probe_one：词表内标记 in_lexicon=True，闭集外 False。"""
    gen = _make_generator(fake_extractor)
    item = gen.build_item(proto)
    row = gen.probe_one(item)
    assert row['error'] is None
    assert row['protocol_id'] == proto.id
    assert row['methods'] == [
        {'name': 'PCR', 'in_lexicon': True},
        {'name': 'Gel Electrophoresis', 'in_lexicon': False},
    ]


def test_probe_one_error_row(fake_extractor, proto):
    """probe_one：LLM 异常 → error 行（methods 空、不崩溃）。"""
    gen = _make_generator(FailingExtractor())
    row = gen.probe_one(gen.build_item(proto))
    assert row['error'] and row['methods'] == []


def test_apply_row_creates_bridge_no_new_method(fake_extractor, canonical_method, proto):
    """apply_row：建桥（llm_reviewed）且不新建 Method 行；闭集外跳过。"""
    n_methods_before = Method.objects.count()
    gen = _make_generator(fake_extractor)
    row = {'protocol_id': proto.id,
           'methods': [{'name': 'PCR'}, {'name': 'Not In Lexicon'}]}
    created, skipped = gen.apply_row(row)
    assert (created, skipped) == (1, 1)
    assert Method.objects.count() == n_methods_before  # 不新建 Method
    bridge = MethodProtocol.objects.get(method=canonical_method, protocol=proto)
    assert bridge.evidence_source == 'llm_reviewed'


def test_apply_row_idempotent(fake_extractor, canonical_method, proto):
    """apply_row 幂等：重复执行不重复建桥。"""
    gen = _make_generator(fake_extractor)
    row = {'protocol_id': proto.id, 'methods': [{'name': 'PCR'}]}
    assert gen.apply_row(row) == (1, 0)
    assert gen.apply_row(row) == (0, 0)
    assert MethodProtocol.objects.count() == 1


# --------------------------------------------------------------------------- #
# 命令层：dry-run / apply / checkpoint
# --------------------------------------------------------------------------- #
def test_dry_run_no_bridge(fake_extractor, canonical_method, proto, out_dir):
    """dry-run：JSONL 生成，不建桥。"""
    out = os.path.join(out_dir, 'proto_methods.jsonl')
    _run(fake_extractor, out)
    assert MethodProtocol.objects.count() == 0
    rows = _load_jsonl(out)
    assert len(rows) == 1 and rows[0]['protocol_name'] == 'DNA Extraction Proto'
    assert rows[0]['error'] is None


def test_apply_creates_bridge(fake_extractor, canonical_method, proto, out_dir):
    """--apply：建桥落库。"""
    out = os.path.join(out_dir, 'proto_methods.jsonl')
    _run(fake_extractor, out, apply=True)
    assert MethodProtocol.objects.filter(
        method=canonical_method, protocol=proto,
        evidence_source='llm_reviewed',
    ).exists()


def test_checkpoint_resume_skips_done(fake_extractor, proto, out_dir):
    """checkpoint 续跑：done 集内协议不再调 LLM。"""
    out = os.path.join(out_dir, 'proto_methods.jsonl')
    ckpt = os.path.join(out_dir, 'ckpt.json')
    with open(ckpt, 'w', encoding='utf-8') as f:
        json.dump({'done': [f'protocol:{proto.id}']}, f)
    _run(fake_extractor, out, checkpoint=ckpt)
    assert fake_extractor.calls == []


def test_error_row_not_in_checkpoint_done(proto, out_dir):
    """T2 教训落地：error 行写 JSONL 但不进 done → 重启自动重跑。"""
    out = os.path.join(out_dir, 'proto_err.jsonl')
    ckpt = os.path.join(out_dir, 'ckpt_err.json')
    _run(FailingExtractor(), out, checkpoint=ckpt)
    rows = _load_jsonl(out)
    assert len(rows) == 1 and rows[0]['error']
    done = json.load(open(ckpt, encoding='utf-8'))['done']
    assert done == []
