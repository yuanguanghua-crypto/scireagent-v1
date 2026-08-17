# -*- coding: utf-8 -*-
"""route B 加法部分测试：facet 归并 + 交叉检测 + 模型/关联（TDD）。

纯逻辑（resolve_facet_spec / detect_biological_context）可独立运行；
模型相关测试在 FacetValue/ProtocolFacet 实现前为红（导入失败）。
"""
from django.test import TestCase

from apps.knowledge.services import facet_annotation as fa


# ----------------------------------------------------------------------------
# 纯逻辑：聚类 → facet 归并
# ----------------------------------------------------------------------------
class TestFacetMapping(TestCase):
    def _map(self, dimension, value, kind=""):
        return fa.resolve_facet_spec(
            0, {0: {"dimension": dimension, "value": value, "kind": kind}}
        )

    def test_method_maps_directly(self):
        spec = self._map("technique", "PCR / qPCR")
        self.assertEqual(spec, (fa.FACET_TYPE_METHOD, "", "PCR / qPCR"))

    def test_application_maps_directly(self):
        spec = self._map("application", "Neuroscience")
        self.assertEqual(spec, (fa.FACET_TYPE_APPLICATION, "", "Neuroscience"))

    def test_study_type_maps_directly(self):
        spec = self._map("study_type", "Systematic Review / Clinical Study")
        self.assertEqual(spec, (fa.FACET_TYPE_STUDY_TYPE, "", "Systematic Review / Clinical Study"))

    def test_organism_collapses_to_biological_context_species(self):
        spec = self._map("organism", "C. elegans", "species")
        self.assertEqual(spec, (fa.FACET_TYPE_BIOLOGICAL, "species", "C. elegans"))

    def test_cell_type_collapses_to_biological_context_cell(self):
        spec = self._map("cell_type", "Macrophage", "cell")
        self.assertEqual(spec, (fa.FACET_TYPE_BIOLOGICAL, "cell", "Macrophage"))

    def test_disease_collapses_to_biological_context_disease(self):
        spec = self._map("disease", "Cancer / Tumor Model", "disease")
        self.assertEqual(spec, (fa.FACET_TYPE_BIOLOGICAL, "disease", "Cancer / Tumor Model"))

    def test_drop_cluster_skipped(self):
        self.assertIsNone(self._map("drop", "Protocol boilerplate (units/volumes)"))

    def test_unknown_cluster_skipped(self):
        self.assertIsNone(fa.resolve_facet_spec(999, {}))

    def test_empty_value_skipped(self):
        self.assertIsNone(self._map("method", ""))


# ----------------------------------------------------------------------------
# 纯逻辑：交叉检测（保守，宁漏不错）
# ----------------------------------------------------------------------------
class TestCrossDetection(TestCase):
    def test_species_mouse(self):
        hits = fa.detect_biological_context("We used mouse embryonic fibroblasts from Mus musculus.")
        self.assertIn(("species", "Mus musculus"), hits)

    def test_cell_hek293(self):
        hits = fa.detect_biological_context("Transfect HEK293 cells with the plasmid.")
        self.assertIn(("cell", "HEK293"), hits)

    def test_disease_cancer(self):
        hits = fa.detect_biological_context("A xenograft tumor model for cancer research.")
        self.assertIn(("disease", "Cancer"), hits)

    def test_no_false_positive_substring(self):
        # "cellulose" / "intercellular" / 裸 "cell" 不应命中
        hits = fa.detect_biological_context("The cellulose intercellular matrix of the cell wall.")
        self.assertEqual(hits, [])

    def test_no_false_positive_patient(self):
        # "patient" 不在物种词表（保守），不应命中
        hits = fa.detect_biological_context("The patient received the treatment in clinic.")
        self.assertEqual(hits, [])

    def test_empty_text(self):
        self.assertEqual(fa.detect_biological_context(""), [])


# ----------------------------------------------------------------------------
# 模型 / 关联（实现前为红）
# ----------------------------------------------------------------------------
class TestFacetModels(TestCase):
    def test_facet_value_unique_constraint(self):
        from apps.knowledge.models import FacetValue
        from django.db import IntegrityError, transaction

        FacetValue.objects.create(
            facet_type=fa.FACET_TYPE_METHOD, kind="", value="PCR / qPCR", slug="pcr-qpcr"
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                FacetValue.objects.create(
                    facet_type=fa.FACET_TYPE_METHOD, kind="", value="PCR / qPCR", slug="pcr-qpcr-dup"
                )

    def test_protocol_facets_m2m_through(self):
        from apps.knowledge.models import FacetValue, Protocol, ProtocolFacet

        proto = Protocol.objects.create(name="Dummy Protocol", slug="dummy-protocol", version="1.0")
        fv = FacetValue.objects.create(
            facet_type=fa.FACET_TYPE_METHOD, kind="", value="PCR / qPCR", slug="pcr-qpcr-2"
        )
        pf = ProtocolFacet.objects.create(protocol=proto, facet=fv, source=ProtocolFacet.Source.CLUSTER_MAIN)
        self.assertIn(fv, list(proto.facets.all()))
        self.assertEqual(pf.source, ProtocolFacet.Source.CLUSTER_MAIN)

    def test_research_goal_protocols_currated_m2m(self):
        from apps.knowledge.models import Protocol, ResearchGoal

        rg = ResearchGoal.objects.create(name="RNA Analysis", slug="rna-analysis")
        proto = Protocol.objects.create(name="Dummy Protocol 2", slug="dummy-protocol-2", version="1.0")
        rg.protocols.add(proto)
        self.assertIn(proto, list(rg.protocols.all()))
