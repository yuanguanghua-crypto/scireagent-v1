r"""S3 · AUTO 体系正规化 —— 游离脚本搬为正式 management command 的契约测试。

被测对象：
  - apps/bridges/services/auto_links.py            （核心服务，可注入 model/candidates）
  - management/commands/recompute_auto_links.py    （原 _land_recompute_auto.py）
  - management/commands/build_auto_candidates.py   （原散落在 _measure_*.py 的候选生成块）
  - services/embedding_backend.py                  （emb3_venv 路径改为可配置）

守护的行为契约（与游离脚本严格一致，零行为漂移）：
  1. 每产品 Top-N 落 link_source=AUTO
  2. 幂等：重跑先删本产品旧 AUTO 行再 upsert，不产生重复
  3. 不覆盖 INHERITED/EXPLICIT 链（已在继承链的协议跳过）
  4. --dry-run 零写入
  5. 搬家后**不得**残留硬编码 D:\emb3_venv（服务器必然无此路径）
"""
import hashlib
import json
import os

import numpy as np
import pytest
from django.core.management import call_command

from apps.bridges.models import ProductProtocol
from apps.bridges.tests.factories import ProductProtocolFactory
from apps.commerce.tests.factories import ProductFactory
from apps.knowledge.tests.factories import ProtocolFactory


DIM = 8


class FakeModel:
    """确定性假模型：md5 派生定长单位向量。

    不用内置 hash()（PYTHONHASHSEED 逐进程随机，跨进程不可复现）。
    """

    def encode(self, texts, batch_size=None, normalize_embeddings=True,
               show_progress_bar=False):
        single = isinstance(texts, str)
        items = [texts] if single else list(texts)
        out = []
        for t in items:
            digest = hashlib.md5((t or '').encode('utf-8')).digest()
            vec = np.frombuffer(digest[:DIM], dtype=np.uint8).astype(np.float32)
            vec = vec - vec.mean()
            norm = np.linalg.norm(vec)
            out.append(vec / norm if norm > 0 else np.ones(DIM, dtype=np.float32) / np.sqrt(DIM))
        arr = np.asarray(out, dtype=np.float32)
        return arr[0] if single else arr


def _make_product(catalog_no, usage='PCR amplification of DNA templates'):
    return ProductFactory(catalog_no=catalog_no, usage=usage)


def _make_protocols(names):
    return [ProtocolFactory(name=n, objective=f'Objective for {n}') for n in names]


# --------------------------------------------------------------------------
# 服务层契约
# --------------------------------------------------------------------------
@pytest.mark.django_db
class TestRecomputeAutoLinksService:

    def test_writes_auto_rows(self):
        from apps.bridges.services.auto_links import recompute_auto_links

        prod = _make_product('SCT001')
        names = ['Alpha PCR protocol', 'Beta cloning protocol']
        _make_protocols(names)

        stats = recompute_auto_links(
            {'SCT001': names}, topn=20, model=FakeModel(),
        )

        rows = ProductProtocol.objects.filter(
            product=prod, link_source=ProductProtocol.LinkSource.AUTO)
        assert rows.count() == 2
        assert stats['written'] == 2
        assert stats['products'] == 1

    def test_topn_limits_rows_per_product(self):
        from apps.bridges.services.auto_links import recompute_auto_links

        prod = _make_product('SCT002')
        names = [f'Protocol candidate {i}' for i in range(5)]
        _make_protocols(names)

        recompute_auto_links({'SCT002': names}, topn=2, model=FakeModel())

        assert ProductProtocol.objects.filter(
            product=prod, link_source=ProductProtocol.LinkSource.AUTO).count() == 2

    def test_idempotent_rerun_no_duplicates(self):
        from apps.bridges.services.auto_links import recompute_auto_links

        prod = _make_product('SCT003')
        names = ['Gamma ligation protocol', 'Delta transfection protocol']
        _make_protocols(names)

        recompute_auto_links({'SCT003': names}, topn=20, model=FakeModel())
        first = list(ProductProtocol.objects.filter(product=prod)
                     .values_list('protocol_id', 'relevance_score').order_by('protocol_id'))

        recompute_auto_links({'SCT003': names}, topn=20, model=FakeModel())
        second = list(ProductProtocol.objects.filter(product=prod)
                      .values_list('protocol_id', 'relevance_score').order_by('protocol_id'))

        assert len(second) == 2
        assert first == second

    def test_skips_protocols_already_inherited(self):
        """铁律①：继承链是真实数据，AUTO 不得覆盖或重复。"""
        from apps.bridges.services.auto_links import recompute_auto_links

        prod = _make_product('SCT004')
        protos = _make_protocols(['Kept inherited protocol', 'Fresh auto protocol'])
        ProductProtocolFactory(
            product=prod, protocol=protos[0],
            link_source=ProductProtocol.LinkSource.INHERITED,
            relevance_score=0.99,
        )

        stats = recompute_auto_links(
            {'SCT004': [p.name for p in protos]}, topn=20, model=FakeModel())

        inherited = ProductProtocol.objects.get(product=prod, protocol=protos[0])
        assert inherited.link_source == ProductProtocol.LinkSource.INHERITED
        assert float(inherited.relevance_score) == pytest.approx(0.99)

        auto_rows = ProductProtocol.objects.filter(
            product=prod, link_source=ProductProtocol.LinkSource.AUTO)
        assert auto_rows.count() == 1
        assert auto_rows.first().protocol_id == protos[1].id
        assert stats['skipped_linked'] == 1

    def test_dry_run_writes_nothing(self):
        from apps.bridges.services.auto_links import recompute_auto_links

        prod = _make_product('SCT005')
        names = ['Epsilon assay protocol']
        _make_protocols(names)

        stats = recompute_auto_links(
            {'SCT005': names}, topn=20, model=FakeModel(), dry_run=True)

        assert ProductProtocol.objects.filter(product=prod).count() == 0
        assert stats['written'] == 1  # 报告"将写入"，但不落库

    def test_verify_matches_production_scalar_functions(self):
        """向量化批算 == relevance 生产逐对函数（等价性自检，容差同脚本）。"""
        from apps.bridges.services.auto_links import recompute_auto_links

        _make_product('SCT006')
        names = ['Zeta sequencing protocol', 'Eta blotting protocol']
        _make_protocols(names)

        stats = recompute_auto_links(
            {'SCT006': names}, topn=20, model=FakeModel(),
            verify=True, verify_sample_rate=1.0,
        )

        assert stats['verified'] >= 1
        assert stats['mismatches'] == 0

    def test_selection_is_reported_in_score_order(self):
        """dry-run 平价核对依赖 selection：须按融合分降序给出被选协议 id。"""
        from apps.bridges.services.auto_links import recompute_auto_links

        prod = _make_product('SCT008')
        names = [f'Ordered protocol {i}' for i in range(4)]
        _make_protocols(names)

        stats = recompute_auto_links(
            {'SCT008': names}, topn=3, model=FakeModel(), dry_run=True)

        picked = stats['selection']['SCT008']
        assert len(picked) == 3
        # 落库版本（非 dry-run）的排序须与 selection 一致
        recompute_auto_links({'SCT008': names}, topn=3, model=FakeModel())
        rows = ProductProtocol.objects.filter(
            product=prod, link_source=ProductProtocol.LinkSource.AUTO
        ).order_by('-relevance_score').values_list('protocol_id', flat=True)
        assert list(rows) == picked

    def test_unknown_catalog_and_unknown_title_are_ignored(self):
        from apps.bridges.services.auto_links import recompute_auto_links

        _make_product('SCT007')
        _make_protocols(['Theta real protocol'])

        stats = recompute_auto_links(
            {
                'SCT007': ['Theta real protocol', 'Title with no Protocol row'],
                'SC-NOT-IN-DB': ['Theta real protocol'],
            },
            topn=20, model=FakeModel(),
        )

        assert stats['products'] == 1
        assert stats['written'] == 1


# --------------------------------------------------------------------------
# 命令层契约
# --------------------------------------------------------------------------
@pytest.mark.django_db
class TestRecomputeAutoLinksCommand:

    def test_command_runs_with_injected_candidates_and_model(self):
        prod = _make_product('SCT010')
        names = ['Iota purification protocol']
        _make_protocols(names)

        call_command(
            'recompute_auto_links',
            candidates={'SCT010': names},
            model=FakeModel(),
            topn=5,
        )

        assert ProductProtocol.objects.filter(
            product=prod, link_source=ProductProtocol.LinkSource.AUTO).count() == 1

    def test_command_reads_candidates_file(self, tmp_path):
        prod = _make_product('SCT011')
        names = ['Kappa extraction protocol']
        _make_protocols(names)

        path = tmp_path / 'cands.json'
        path.write_text(json.dumps({'SCT011': names}), encoding='utf-8')

        call_command(
            'recompute_auto_links',
            '--candidates', str(path),
            model=FakeModel(),
        )

        assert ProductProtocol.objects.filter(
            product=prod, link_source=ProductProtocol.LinkSource.AUTO).count() == 1


@pytest.mark.django_db
class TestBuildAutoCandidatesCommand:

    def test_writes_candidates_json_from_recommender(self, tmp_path):
        _make_product('SCT020', usage='Reverse transcription of RNA')

        class FakeRecommender:
            def recommend_expanded(self, product_name, category_path=None,
                                   synonyms=None, top_k=None):
                return [{'title': 'Lambda RT protocol'}, {'title': 'Mu RT protocol'}]

        out = tmp_path / 'cands.json'
        docx = tmp_path / 'docx.json'
        docx.write_text(json.dumps(
            [{'catalog': 'SCT020', 'name': 'RT Enzyme', 'usage': 'Reverse transcription'}]
        ), encoding='utf-8')

        call_command(
            'build_auto_candidates',
            '--out', str(out),
            '--docx', str(docx),
            recommender=FakeRecommender(),
        )

        data = json.loads(out.read_text(encoding='utf-8'))
        assert data == {'SCT020': ['Lambda RT protocol', 'Mu RT protocol']}

    def test_refuses_to_overwrite_without_force(self, tmp_path):
        out = tmp_path / 'cands.json'
        out.write_text('{"EXISTING": []}', encoding='utf-8')
        docx = tmp_path / 'docx.json'
        docx.write_text('[]', encoding='utf-8')

        class FakeRecommender:
            def recommend_expanded(self, *a, **kw):
                return []

        call_command(
            'build_auto_candidates',
            '--out', str(out), '--docx', str(docx),
            recommender=FakeRecommender(),
        )
        # 未加 --force：既有 129MB 产物不得被静默覆盖
        assert json.loads(out.read_text(encoding='utf-8')) == {'EXISTING': []}


# --------------------------------------------------------------------------
# 可移植性：emb3_venv 硬编码清除
# --------------------------------------------------------------------------
class TestEmb3VenvPortability:

    def test_path_is_configurable_via_env(self, monkeypatch, tmp_path):
        from apps.bridges.services import embedding_backend as EB

        monkeypatch.setenv('EMB3_VENV', str(tmp_path))
        assert EB.emb3_venv_path() == str(tmp_path)

    def test_falls_back_to_default_when_unset(self, monkeypatch):
        from apps.bridges.services import embedding_backend as EB

        monkeypatch.delenv('EMB3_VENV', raising=False)
        assert EB.emb3_venv_path() == EB.DEFAULT_EMB3_VENV

    @pytest.mark.parametrize('module_path', [
        'apps/bridges/services/auto_links.py',
        'apps/bridges/management/commands/recompute_auto_links.py',
        'apps/bridges/management/commands/build_auto_candidates.py',
    ])
    def test_no_hardcoded_emb3_path_in_moved_modules(self, module_path):
        """搬家目标里不得出现盘符路径字面量或 sys.path 注入。

        （只禁"硬编码路径"这一真实风险；文档里提及 EMB3_VENV 变量名是允许的）
        """
        base = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))))
        full = os.path.join(base, module_path.replace('/', os.sep))
        assert os.path.exists(full), f'搬家目标不存在: {module_path}'
        src = open(full, encoding='utf-8').read().lower()

        for literal in ('d:\\emb3_venv', 'd:/emb3_venv', 'site-packages'):
            assert literal not in src, (
                f'{module_path} 残留硬编码路径 {literal!r} —— 服务器必然失败')
        assert 'sys.path.insert' not in src, (
            f'{module_path} 仍自行操纵 sys.path —— 应交由 embedding_backend 统一处理')
