# -*- coding: utf-8 -*-
"""annotate_protocol_facets 集成测试（route B 加法，范围 A）。

构造自洽合成数据：随机嵌入 + 同一 KMeans(random_state=42,n_init=4) 复现标签，
据此生成 poc_vocab.json / poc_facet_taxonomy.json / poc_topchain_data.json，
使命令重跑 KMeans 时簇大小闸门必 PASS。覆盖：
- 主标签(method/study_type/biological_context) 按簇归并正确
- drop 簇不产生 cluster_main facet
- 交叉检测对含 'mouse' 文本补 'Mus musculus'(cross_detect)
- 幂等：重复运行计数不变
- 闸门：篡改参考 size 即 CommandError
- --dry-run / --limit / --clear 行为正确
"""
import json
import os
import tempfile

import numpy as np
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.knowledge.models import Protocol, FacetValue, ProtocolFacet
from apps.knowledge.services import facet_annotation as fa


def _build_synthetic(data_dir, k=80, n=160, seed=12345):
    """生成自洽合成数据；返回 (labels, protocols_meta)。"""
    rng = np.random.RandomState(seed)
    emb = rng.randn(n, 384).astype('float32')
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    emb = emb / (norms + 1e-9)  # 与真实 L2 归一化一致
    np.save(os.path.join(data_dir, 'poc_protocol_emb.npy'), emb)

    from sklearn.cluster import KMeans
    labels = KMeans(n_clusters=k, random_state=42, n_init=4).fit_predict(emb)

    protocols = []
    for i in range(n):
        cid = int(labels[i])
        obj = f"generic objective for protocol {i}"
        # 让 technique 簇的部分协议文本含 'mouse' -> 触发交叉检测补 'Mus musculus'
        if cid % 4 == 0 and cid != 0:
            obj = f"we used mouse model extensively in protocol {i}"
        protocols.append({"id": i + 1, "name": f"P{i + 1}", "objective": obj})
    with open(os.path.join(data_dir, 'poc_topchain_data.json'), 'w', encoding='utf-8') as f:
        json.dump({"protocols": protocols, "methods": []}, f)

    sizes = {cid: int((labels == cid).sum()) for cid in range(k)}
    clusters = [
        {"cluster_id": cid, "size": sizes[cid], "keywords": [], "top_protocols": []}
        for cid in range(k)
    ]
    vocab = {"generated_at": "test", "n_protocols": n,
             "by_k": {str(k): {"stats": {}, "clusters": clusters}}}
    with open(os.path.join(data_dir, 'poc_vocab.json'), 'w', encoding='utf-8') as f:
        json.dump(vocab, f)

    # taxonomy：覆盖所有分支（含 drop / study_type / 三个 biological_context 子类型）
    tax_clusters = []
    for cid in range(k):
        if cid == 0:
            dim, val, kind = "study_type", f"Study {cid}", ""
        elif cid == 1:
            dim, val, kind = "organism", f"Species {cid}", "species"
        elif cid == 2:
            dim, val, kind = "cell_type", f"Cell {cid}", "cell"
        elif cid == 3:
            dim, val, kind = "disease", f"Disease {cid}", "disease"
        elif cid in (78, 79):
            dim, val, kind = "drop", f"Drop {cid}", None
        else:
            dim, val, kind = "technique", f"Technique {cid}", ""
        tax_clusters.append({"cluster_id": cid, "size": sizes[cid], "keywords": [],
                             "dimension": dim, "value": val, "kind": kind, "note": ""})
    taxonomy = {"k": k, "n_clusters": k, "dimension_counts": {},
                "biological_context_kind_counts": {}, "clusters": tax_clusters}
    with open(os.path.join(data_dir, 'poc_facet_taxonomy.json'), 'w', encoding='utf-8') as f:
        json.dump(taxonomy, f)

    return labels, protocols


def _build_synthetic_app(data_dir, k_app=20, n=160, seed=777):
    """生成 application 模式自洽合成数据（k=20 聚类 + application taxonomy + by_k['20'] 闸门）。"""
    rng = np.random.RandomState(seed)
    emb = rng.randn(n, 384).astype('float32')
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    emb = emb / (norms + 1e-9)
    np.save(os.path.join(data_dir, 'poc_protocol_emb.npy'), emb)

    from sklearn.cluster import KMeans
    labels = KMeans(n_clusters=k_app, random_state=42, n_init=4).fit_predict(emb)

    protocols = []
    for i in range(n):
        cid = int(labels[i])
        obj = f"generic objective for protocol {i}"
        if cid % 4 == 0 and cid != 0:
            obj = f"we used mouse model extensively in protocol {i}"
        protocols.append({"id": i + 1, "name": f"P{i + 1}", "objective": obj})
    with open(os.path.join(data_dir, 'poc_topchain_data.json'), 'w', encoding='utf-8') as f:
        json.dump({"protocols": protocols, "methods": []}, f)

    sizes = {cid: int((labels == cid).sum()) for cid in range(k_app)}
    vocab = {"generated_at": "test", "n_protocols": n,
             "by_k": {"20": {"stats": {}, "clusters": [
                 {"cluster_id": cid, "size": sizes[cid]} for cid in range(k_app)]}}}
    with open(os.path.join(data_dir, 'poc_vocab.json'), 'w', encoding='utf-8') as f:
        json.dump(vocab, f)

    tax_clusters = []
    for cid in range(k_app):
        if cid in (8, 13):
            dim, val, kind = "drop", "", None  # 模拟两个 catch-all 噪声簇
        else:
            dim, val, kind = "application", f"AppDomain {cid}", ""
        tax_clusters.append({"cluster_id": cid, "size": sizes[cid], "keywords": [],
                             "dimension": dim, "value": val, "kind": kind, "note": ""})
    taxonomy = {"k": k_app, "n_clusters": k_app, "dimension_counts": {},
                "biological_context_kind_counts": {}, "clusters": tax_clusters}
    with open(os.path.join(data_dir, 'poc_application_taxonomy.json'), 'w', encoding='utf-8') as f:
        json.dump(taxonomy, f)

    return labels, protocols


def _seed_protocols(protocols):
    objs = [
        Protocol(id=p["id"], name=p["name"], slug=f"p-{p['id']}",
                 source=Protocol.Source.CURATED, objective=p["objective"])
        for p in protocols
    ]
    Protocol.objects.bulk_create(objs)


class AnnotateFacetsCommandTest(TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="poc_annot_")
        self.labels, self.protocols = _build_synthetic(self.tmp, k=80, n=160)
        _seed_protocols(self.protocols)

    # ---------- 正常全量标注 ----------
    def test_full_annotation(self):
        call_command('annotate_protocol_facets', data_dir=self.tmp, k=80)

        # FacetValue：method / study_type / biological_context 均存在
        self.assertTrue(
            FacetValue.objects.filter(facet_type=fa.FACET_TYPE_METHOD).exists(),
            "method facet 缺失",
        )
        self.assertTrue(
            FacetValue.objects.filter(facet_type=fa.FACET_TYPE_STUDY_TYPE).exists(),
            "study_type facet 缺失",
        )
        self.assertTrue(
            FacetValue.objects.filter(facet_type=fa.FACET_TYPE_BIOLOGICAL).exists(),
            "biological_context facet 缺失",
        )

        # 交叉检测：含 'mouse' 文本 -> 'Mus musculus' cross_detect
        mus = FacetValue.objects.filter(
            facet_type=fa.FACET_TYPE_BIOLOGICAL, kind="species", value="Mus musculus"
        ).first()
        self.assertIsNotNone(mus, "交叉检测未产出 Mus musculus")
        pf = ProtocolFacet.objects.filter(facet=mus, source=ProtocolFacet.Source.CROSS_DETECT)
        self.assertTrue(pf.exists(), "Mus musculus 缺少 cross_detect 关联")

        # 来源计数合理
        cm = ProtocolFacet.objects.filter(source=ProtocolFacet.Source.CLUSTER_MAIN).count()
        cd = ProtocolFacet.objects.filter(source=ProtocolFacet.Source.CROSS_DETECT).count()
        self.assertGreater(cm, 0, "cluster_main 关联为空")
        self.assertGreater(cd, 0, "cross_detect 关联为空")

    # ---------- drop 簇不产出 cluster_main ----------
    def test_drop_cluster_has_no_cluster_main(self):
        call_command('annotate_protocol_facets', data_dir=self.tmp, k=80)
        # cluster 78/79 在合成 taxonomy 中为 drop -> 这些协议不应有 cluster_main facet
        drop_pks = [self.protocols[i]["id"] for i, c in enumerate(self.labels) if int(c) in (78, 79)]
        cm_drop = ProtocolFacet.objects.filter(
            protocol_id__in=drop_pks, source=ProtocolFacet.Source.CLUSTER_MAIN
        ).count()
        self.assertEqual(cm_drop, 0, "drop 簇不应有 cluster_main facet")

    # ---------- 交叉检测具体协议双标签 ----------
    def test_cross_detect_adds_species_to_method_protocol(self):
        call_command('annotate_protocol_facets', data_dir=self.tmp, k=80)
        # 找一个 method 簇且文本含 'mouse' 的协议
        target = None
        for i, c in enumerate(self.labels):
            cid = int(c)
            is_method = not (cid in (0, 1, 2, 3, 78, 79))  # 合成里非这些的都 method
            if is_method and "mouse" in self.protocols[i]["objective"]:
                target = self.protocols[i]["id"]
                break
        self.assertIsNotNone(target, "未找到 method+mouse 协议")
        pf_all = ProtocolFacet.objects.filter(protocol_id=target)
        sources = set(pf_all.values_list('source', flat=True))
        # 它应当同时拥有 cluster_main(method) 与 cross_detect(Mus musculus)
        self.assertIn(ProtocolFacet.Source.CLUSTER_MAIN, sources)
        self.assertIn(ProtocolFacet.Source.CROSS_DETECT, sources)
        has_mus = pf_all.filter(
            facet__value="Mus musculus", source=ProtocolFacet.Source.CROSS_DETECT
        ).exists()
        self.assertTrue(has_mus, "method+mouse 协议未补 Mus musculus")

    # ---------- 幂等 ----------
    def test_idempotent_rerun(self):
        call_command('annotate_protocol_facets', data_dir=self.tmp, k=80)
        fv1 = FacetValue.objects.count()
        pf1 = ProtocolFacet.objects.count()
        call_command('annotate_protocol_facets', data_dir=self.tmp, k=80)
        fv2 = FacetValue.objects.count()
        pf2 = ProtocolFacet.objects.count()
        self.assertEqual(fv1, fv2, "重复运行 FacetValue 计数变化（非幂等）")
        self.assertEqual(pf1, pf2, "重复运行 ProtocolFacet 计数变化（非幂等）")

    # ---------- 闸门：篡改参考 size 即失败 ----------
    def test_gate_fails_on_tampered_sizes(self):
        # 把参考 size 改错一个簇
        vp = os.path.join(self.tmp, 'poc_vocab.json')
        with open(vp, encoding='utf-8') as f:
            vocab = json.load(f)
        clusters = vocab['by_k']['80']['clusters']
        clusters[0]['size'] += 1
        with open(vp, 'w', encoding='utf-8') as f:
            json.dump(vocab, f)
        with self.assertRaises(CommandError):
            call_command('annotate_protocol_facets', data_dir=self.tmp, k=80)

    # ---------- dry-run ----------
    def test_dry_run_writes_nothing(self):
        call_command('annotate_protocol_facets', data_dir=self.tmp, k=80, dry_run=True)
        self.assertEqual(FacetValue.objects.count(), 0, "dry-run 不应落库 FacetValue")
        self.assertEqual(ProtocolFacet.objects.count(), 0, "dry-run 不应落库 ProtocolFacet")

    # ---------- limit ----------
    def test_limit_only_processes_prefix(self):
        call_command('annotate_protocol_facets', data_dir=self.tmp, k=80, limit=10)
        # 只有前 10 个协议的关联应存在
        prefix_pks = [self.protocols[i]["id"] for i in range(10)]
        rest_pks = [self.protocols[i]["id"] for i in range(10, len(self.protocols))]
        pf_prefix = ProtocolFacet.objects.filter(protocol_id__in=prefix_pks).count()
        pf_rest = ProtocolFacet.objects.filter(protocol_id__in=rest_pks).count()
        self.assertGreater(pf_prefix, 0, "limit 未标注前缀协议")
        self.assertEqual(pf_rest, 0, "limit 越界标注了后续协议")

    # ---------- clear ----------
    def test_clear_rebuilds(self):
        call_command('annotate_protocol_facets', data_dir=self.tmp, k=80)
        pf_before = ProtocolFacet.objects.count()
        self.assertGreater(pf_before, 0)
        call_command('annotate_protocol_facets', data_dir=self.tmp, k=80, clear=True)
        pf_after = ProtocolFacet.objects.count()
        # clear 后全量重标，数量应与首次一致（自洽数据不变）
        self.assertEqual(pf_after, pf_before, "clear 重标后数量应与首次一致")


# ----------------------------------------------------------------------------
# application 模式（k=20 研究域 facet）
# ----------------------------------------------------------------------------
class AnnotateApplicationCommandTest(TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="poc_app_")
        self.labels, self.protocols = _build_synthetic_app(self.tmp, k_app=20, n=160)
        _seed_protocols(self.protocols)

    def test_application_annotation_creates_application_facets(self):
        call_command('annotate_protocol_facets', data_dir=self.tmp, application=True)
        self.assertTrue(
            FacetValue.objects.filter(facet_type=fa.FACET_TYPE_APPLICATION).exists(),
            "application facet 缺失",
        )
        # application 模式仅标研究域：不应产生 method / biological_context
        self.assertFalse(
            FacetValue.objects.filter(facet_type=fa.FACET_TYPE_METHOD).exists(),
            "application 模式不应产生 method facet",
        )
        self.assertFalse(
            FacetValue.objects.filter(facet_type=fa.FACET_TYPE_BIOLOGICAL).exists(),
            "application 模式不应产生 biological_context facet",
        )

    def test_application_forces_k20_regardless_of_k_flag(self):
        # 即便传 --k 80，application 模式仍用 k=20（内部强制），闸门按 by_k['20'] 校验
        call_command('annotate_protocol_facets', data_dir=self.tmp, application=True, k=80)
        self.assertTrue(
            FacetValue.objects.filter(facet_type=fa.FACET_TYPE_APPLICATION).exists()
        )

    def test_application_drop_clusters_skipped(self):
        call_command('annotate_protocol_facets', data_dir=self.tmp, application=True)
        drop_pks = [self.protocols[i]["id"] for i, c in enumerate(self.labels)
                    if int(c) in (8, 13)]
        pf = ProtocolFacet.objects.filter(
            protocol_id__in=drop_pks, facet__facet_type=fa.FACET_TYPE_APPLICATION
        ).count()
        self.assertEqual(pf, 0, "application drop 簇不应有 application facet")

    def test_application_no_cross_detect(self):
        call_command('annotate_protocol_facets', data_dir=self.tmp, application=True)
        # 含 'mouse' 文本也不应触发 Mus musculus（app 模式跳过交叉检测）
        self.assertFalse(
            FacetValue.objects.filter(
                facet_type=fa.FACET_TYPE_BIOLOGICAL, kind="species", value="Mus musculus"
            ).exists(),
            "application 模式不应做生物交叉检测",
        )

    def test_application_idempotent(self):
        call_command('annotate_protocol_facets', data_dir=self.tmp, application=True)
        pf1 = ProtocolFacet.objects.filter(
            facet__facet_type=fa.FACET_TYPE_APPLICATION).count()
        call_command('annotate_protocol_facets', data_dir=self.tmp, application=True)
        pf2 = ProtocolFacet.objects.filter(
            facet__facet_type=fa.FACET_TYPE_APPLICATION).count()
        self.assertEqual(pf1, pf2, "application 重复运行非幂等")

    def test_application_clear_forbidden(self):
        with self.assertRaises(CommandError):
            call_command('annotate_protocol_facets', data_dir=self.tmp,
                        application=True, clear=True)
