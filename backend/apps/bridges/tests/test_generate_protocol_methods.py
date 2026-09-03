"""generate_protocol_methods 命令 + ProtocolMethodGenerator 服务测试（TDD，T3）。

T3：为「悬空协议」（无 MethodProtocol 桥的 PUBLISHED 协议）补 Method 关联——
LLM 从词表（Method 表 ACTIVE+DRAFT name，排除 __e2e_ 垃圾）**召回候选**并选名。
铁律：宁 miss 不错配——召回为空不调 LLM 直接空；LLM 输出必须 ∈ 候选，否则拒绝。

与 T2 的关键差异（T2 教训应用）：**error（如 HTTP 429）行不进 checkpoint done**，
重启时自动重跑，杜绝静默数据缺口。

覆盖：
1. 范围守卫：只处理 PUBLISHED + 无桥协议
2. 词表排除 __ 前缀 e2e 垃圾
3. 召回：协议名含方法词 → 候选；不含 → 空候选且不调 LLM
4. dry-run：不建桥
5. --apply：建桥（evidence_source='llm_reviewed'、explicit=False、status='active'）
6. LLM 返回空数组 → 不建桥
7. error 不进 checkpoint done（重启重跑）—— T2 教训
8. checkpoint 续跑：done 集跳过
9. 幂等：已建桥协议不再处理
"""
import json
import os

import pytest
from django.core.management import call_command as cc

from apps.bridges.models import MethodProtocol
from apps.knowledge.models import Method, Protocol
from apps.knowledge.tests.factories import MethodFactory, ProtocolFactory

pytestmark = pytest.mark.django_db


class FakeExtractor:
    """模拟 LLMExtractor：chat() 返回确定性 JSON（T3 输出 {"method_ids": [..]}）。"""
    model = 'fake-model'

    def __init__(self, by_substr=None, default='{"method_ids": []}', fail_on=None):
        self.by_substr = by_substr or {}   # 协议名子串 → 返回文本
        self.default = default
        self.fail_on = fail_on or []       # 协议名子串命中 → 抛错（模拟 429）
        self.calls = []

    def chat(self, system_prompt, user_prompt, temperature=0):
        self.calls.append(user_prompt[:80])
        for key, txt in self.by_substr.items():
            if key in user_prompt:
                if any(f in user_prompt for f in self.fail_on):
                    raise RuntimeError('HTTP 429 Too Many Requests')
                return txt
        if any(f in user_prompt for f in self.fail_on):
            raise RuntimeError('HTTP 429 Too Many Requests')
        return self.default


def _run(out, checkpoint, extractor, apply=False, workers=2, limit=None):
    """执行命令的公共入口（临时文件自动清理）。"""
    kwargs = dict(
        extractor=extractor, out=out, checkpoint=checkpoint,
        workers=workers,
    )
    if apply:
        kwargs['apply'] = True
    if limit is not None:
        kwargs['limit'] = limit
    cc('generate_protocol_methods', **kwargs)


def _load_jsonl(path):
    rows = []
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            rows = [json.loads(l) for l in f if l.strip()]
    return rows


def _load_done(path):
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            return json.load(f).get('done', [])
    return []


class TestScopeGuard:
    def test_only_published_orphan_protocols_in_pool(self):
        """范围守卫：只处理 PUBLISHED 且无桥的协议（draft / 已有桥的不进 pool）。"""
        from apps.bridges.services.protocol_method_generator import ProtocolMethodGenerator
        fake = FakeExtractor()
        gen = ProtocolMethodGenerator(extractor=fake)

        # 已有桥的 published 协议 → 不进 pool
        linked_proto = ProtocolFactory(name='PCR Amplification Protocol', status=Protocol.PublicationStatus.PUBLISHED)
        m = MethodFactory(name='PCR')
        MethodProtocol.objects.create(method=m, protocol=linked_proto)
        # draft 协议 → 不进 pool
        ProtocolFactory(name='ELISA Protocol Draft', status=Protocol.PublicationStatus.DRAFT)
        # 悬空 published → 进 pool
        orphan = ProtocolFactory(name='qPCR Quantification Protocol', status=Protocol.PublicationStatus.PUBLISHED)

        pool = gen.fetch_pool()
        ids = [p.id for p in pool]
        assert orphan.id in ids
        assert linked_proto.id not in ids

    def test_lexicon_excludes_e2e_junk(self):
        """词表排除 __ 前缀（e2e 测试垃圾）与 archived。"""
        from apps.bridges.services.protocol_method_generator import ProtocolMethodGenerator
        MethodFactory(name='PCR')
        MethodFactory(name='__e2e_methods_1783690055811__')
        MethodFactory(name='Gel Purification of DNA')
        gen = ProtocolMethodGenerator(extractor=FakeExtractor())
        lex = gen.lexicon()
        assert 'PCR' in lex
        assert 'Gel Purification of DNA' in lex
        assert not any(n.startswith('__') for n in lex)


class TestRecall:
    def test_recall_hits_method_keyword(self):
        """协议名含方法词 → 候选召回该 Method。"""
        from apps.bridges.services.protocol_method_generator import ProtocolMethodGenerator
        MethodFactory(name='PCR')
        MethodFactory(name='ELISA')
        gen = ProtocolMethodGenerator(extractor=FakeExtractor())
        cands = gen.candidates('PCR Amplification of cDNA Protocol', top_k=10)
        names = [c['name'] for c in cands]
        assert 'PCR' in names

    def test_recall_empty_skips_llm(self):
        """无方法词（如临床随机试验标题）→ 空候选，不调 LLM，记为真空。"""
        from apps.bridges.services.protocol_method_generator import ProtocolMethodGenerator
        MethodFactory(name='PCR')
        fake = FakeExtractor(default='{"method_ids": [0]}')
        gen = ProtocolMethodGenerator(extractor=fake)
        proto = ProtocolFactory(
            name='A Randomized Placebo Controlled Double Blind Clinical Trial of Statins',
            status=Protocol.PublicationStatus.PUBLISHED,
        )
        item = gen.build_item(proto)
        row = gen.probe_one(item)
        assert row['method_names'] == []
        assert row['candidate_names'] == []
        assert fake.calls == []  # 未调 LLM


class TestDryRunAndApply:
    def test_dry_run_no_bridge(self, tmp_path):
        """dry-run：JSONL 生成、不建桥。"""
        ProtocolFactory(name='PCR Amplification Protocol', status=Protocol.PublicationStatus.PUBLISHED)
        MethodFactory(name='PCR')
        fake = FakeExtractor(by_substr={'PCR': '{"method_ids": [0]}'})
        out = str(tmp_path / 't3_dry.jsonl')
        _run(out=out, checkpoint=str(tmp_path / 't3_dry_ckpt.json'), extractor=fake)
        assert MethodProtocol.objects.count() == 0
        rows = _load_jsonl(out)
        assert len(rows) == 1
        assert rows[0]['method_names'] == ['PCR']

    def test_apply_creates_llm_reviewed_bridge(self, tmp_path):
        """--apply：建桥且 evidence_source='llm_reviewed'、explicit=False、status='active'。"""
        proto = ProtocolFactory(name='qPCR Quantification Protocol', status=Protocol.PublicationStatus.PUBLISHED)
        MethodFactory(name='PCR')
        MethodFactory(name='Real-Time Quantitative PCR (qPCR)')
        # 候选按词重合打分：'qPCR Quantification' 的 token 只命中 qPCR 方法（PCR 词不重合）
        fake = FakeExtractor(by_substr={'qPCR Quantification': '{"method_ids": [0]}'})
        out = str(tmp_path / 't3_apply.jsonl')
        _run(out=out, checkpoint=str(tmp_path / 't3_apply_ckpt.json'), extractor=fake, apply=True)

        mp = MethodProtocol.objects.get(protocol=proto)
        assert mp.evidence_source == 'llm_reviewed'
        assert mp.explicit is False
        assert mp.status == 'active'

    def test_empty_llm_response_no_bridge(self, tmp_path):
        """LLM 返回空数组 → 不建桥（宁 miss）。"""
        proto = ProtocolFactory(name='PCR Amplification Protocol', status=Protocol.PublicationStatus.PUBLISHED)
        MethodFactory(name='PCR')
        fake = FakeExtractor(default='{"method_ids": []}')
        out = str(tmp_path / 't3_empty.jsonl')
        _run(out=out, checkpoint=str(tmp_path / 't3_empty_ckpt.json'), extractor=fake, apply=True)
        assert MethodProtocol.objects.count() == 0
        rows = _load_jsonl(out)
        assert rows[0]['method_names'] == []


class TestCheckpointAndErrors:
    def test_error_not_in_checkpoint_done(self, tmp_path):
        """T2 教训：429 error 行写 JSONL 但不进 checkpoint done → 重启重跑。"""
        ok_proto = ProtocolFactory(name='PCR Clean Protocol', status=Protocol.PublicationStatus.PUBLISHED)
        err_proto = ProtocolFactory(name='ELISA Trouble Protocol', status=Protocol.PublicationStatus.PUBLISHED)
        MethodFactory(name='PCR')
        MethodFactory(name='ELISA')
        fake = FakeExtractor(
            by_substr={'PCR Clean': '{"method_ids": [0]}', 'ELISA Trouble': '{"method_ids": [0]}'},
            fail_on=['ELISA Trouble'],
        )
        out = str(tmp_path / 't3_err.jsonl')
        ckpt = str(tmp_path / 't3_err_ckpt.json')
        _run(out=out, checkpoint=ckpt, extractor=fake, apply=True)

        # error 协议：无桥 + JSONL error 行 + 不在 done
        assert not MethodProtocol.objects.filter(protocol=err_proto).exists()
        rows = _load_jsonl(out)
        err_rows = [r for r in rows if r.get('error')]
        assert len(err_rows) == 1 and err_rows[0]['protocol_id'] == err_proto.id
        done = _load_done(ckpt)
        assert f'protocol:{err_proto.id}' not in done
        # 正常协议：有桥 + 在 done
        assert MethodProtocol.objects.filter(protocol=ok_proto).exists()
        assert f'protocol:{ok_proto.id}' in done

    def test_checkpoint_resume_skips_done(self, tmp_path):
        """checkpoint 续跑：done 集内的协议跳过。"""
        done_proto = ProtocolFactory(name='Done Protocol PCR', status=Protocol.PublicationStatus.PUBLISHED)
        todo_proto = ProtocolFactory(name='Todo Protocol qPCR', status=Protocol.PublicationStatus.PUBLISHED)
        MethodFactory(name='PCR')
        ckpt = str(tmp_path / 't3_resume_ckpt.json')
        with open(ckpt, 'w', encoding='utf-8') as f:
            json.dump({'done': [f'protocol:{done_proto.id}']}, f)

        fake = FakeExtractor(by_substr={'Todo Protocol': '{"method_ids": [0]}'})
        out = str(tmp_path / 't3_resume.jsonl')
        _run(out=out, checkpoint=ckpt, extractor=fake, apply=True)

        rows = _load_jsonl(out)
        assert [r['protocol_id'] for r in rows] == [todo_proto.id]  # 只处理未 done 的
        assert not MethodProtocol.objects.filter(protocol=done_proto).exists()

    def test_idempotent_no_duplicate_bridge(self, tmp_path):
        """幂等：已有桥协议不再处理；bulk_create(ignore_conflicts) 不重复建桥。"""
        proto = ProtocolFactory(name='PCR Protocol', status=Protocol.PublicationStatus.PUBLISHED)
        m = MethodFactory(name='PCR')
        MethodProtocol.objects.create(method=m, protocol=proto)  # 已有桥
        fake = FakeExtractor(by_substr={'PCR': '{"method_ids": [0]}'})
        out = str(tmp_path / 't3_idem.jsonl')
        _run(out=out, checkpoint=str(tmp_path / 't3_idem_ckpt.json'), extractor=fake, apply=True)
        assert MethodProtocol.objects.filter(protocol=proto).count() == 1

    def test_duplicate_method_names_do_not_crash(self, tmp_path):
        """同名 Method 多条 → apply_row 不崩（取其一建桥）。

        实证背景：Method 表 21,302 行 / 仅 1,742 个唯一名（T2 为每个 AP 各建一条，
        平均每个方法名 12 条记录）。原 apply_row 用 Method.objects.get(name=...)
        → MultipleObjectsReturned（非 DoesNotExist，except 捕获不到）→ 批跑直接崩。
        """
        from apps.bridges.services.protocol_method_generator import ProtocolMethodGenerator
        proto = ProtocolFactory(
            name='qPCR Quantification Protocol',
            status=Protocol.PublicationStatus.PUBLISHED,
        )
        MethodFactory(name='Real-Time Quantitative PCR (qPCR)')
        MethodFactory(name='Real-Time Quantitative PCR (qPCR)')  # 同名第二条
        assert Method.objects.filter(name='Real-Time Quantitative PCR (qPCR)').count() == 2
        gen = ProtocolMethodGenerator(extractor=FakeExtractor())
        row = {
            'protocol_id': proto.id,
            'method_names': ['Real-Time Quantitative PCR (qPCR)'],
        }
        assert gen.apply_row(row) == 1
        assert MethodProtocol.objects.filter(protocol=proto).count() == 1
