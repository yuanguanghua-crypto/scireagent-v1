"""
TDD: fetch_external_objectives 命令（A 类补全 — 外部抓取补齐 objective）。

纯函数（extract_objective / title_similarity / choose_best_match）直接单测；
命令集成测试 mock core.datasource_client 链路（与 test_pubmed_integration 一致，
实际 patch apps.knowledge.services.pubmed_client.request_with_resilience）。

铁律校验：宁 miss 不错配（相似度 < 门槛 → objective 保持空）。
"""
import json
import os
import tempfile
from unittest.mock import patch, MagicMock

from django.core.management import call_command
from django.test import TestCase

from apps.knowledge.models import Protocol
from apps.knowledge.services import external_objective as eo
from apps.knowledge.services.pubmed_client import PubMedClient, _parse_pubmed_xml_abstract
from apps.knowledge.services.europepmc_client import (
    EuropePMCClient,
    build_queries,
    clean_abstract,
)


def _make_response(json_payload=None, text=None):
    m = MagicMock()
    m.status_code = 200
    m.raise_for_status = lambda: None
    if json_payload is not None:
        m.json = lambda: json_payload
    if text is not None:
        m.text = text
    return m


def _epmc_response(results):
    """构造 Europe PMC search 响应（resultType=core：摘要内嵌在 abstractText）。"""
    return _make_response(json_payload={
        "hitCount": len(results),
        "resultList": {"result": results},
    })


def _epmc_article(title, abstract, pmid="", doi="", source="MED", pmcid=""):
    return {
        "id": pmid or doi or title, "source": source,
        "pmid": pmid, "pmcid": pmcid, "doi": doi,
        "title": title, "abstractText": abstract,
        "authorString": "A B.", "pubYear": "2024",
    }


def _pubmed_fake(esummary_title, abstract_text):
    """构造 request_with_resilience 的 side_effect：按 URL 分支返回 esearch/esummary/efetch。"""
    def fake(method, url, source="pubmed", timeout=15, **kwargs):
        if "esearch.fcgi" in url:
            return _make_response(json_payload={"esearchresult": {"idlist": ["123"], "count": "1"}})
        if "esummary.fcgi" in url:
            return _make_response(json_payload={"result": {
                "123": {"uid": "123", "title": esummary_title, "source": "J",
                        "pubdate": "2020", "authors": [{"name": "A B"}]}}})
        if "efetch.fcgi" in url:
            return _make_response(text=abstract_text)
        return _make_response(json_payload={})
    return fake


class ExtractObjectiveTest(TestCase):
    def test_empty(self):
        self.assertEqual(eo.extract_objective(""), "")
        self.assertEqual(eo.extract_objective(None), "")

    def test_prefers_objective_section(self):
        ab = ("BACKGROUND: We studied X. OBJECTIVE: To ligate linkers to RNA ends. "
              "METHODS: click chemistry. RESULTS: success.")
        self.assertEqual(eo.extract_objective(ab), "To ligate linkers to RNA ends.")

    def test_aim_keyword_sentence(self):
        ab = "We developed a new assay. AIM: To quantify RNA modification levels accurately. It works."
        self.assertEqual(eo.extract_objective(ab), "To quantify RNA modification levels accurately.")

    def test_fallback_first_sentences(self):
        ab = "This protocol describes fluorescent labeling of nucleotides. It is robust and simple."
        out = eo.extract_objective(ab)
        self.assertIn("fluorescent labeling", out)

    def test_caps_length(self):
        ab = "OBJECTIVE: " + ("word " * 200)
        out = eo.extract_objective(ab, max_chars=60)
        self.assertLessEqual(len(out), 61)
        self.assertTrue(out.endswith("…") or len(out) <= 60)

    def test_rejects_junk_short_citation(self):
        """无摘要旧文献只返回期刊行（如 '1. Biotechniques.'）→ 视为 junk 跳过。"""
        self.assertEqual(eo.extract_objective("1. Biotechniques."), "")
        self.assertEqual(eo.extract_objective("NATURE."), "")
        self.assertEqual(eo.extract_objective("short"), "")

    def test_strips_leading_citation_fragment(self):
        ab = "Nat Methods 10:1096-1098, 2013), we developed FLASH-seq for full-length scRNA-seq."
        out = eo.extract_objective(ab)
        self.assertFalse(out.startswith("Nat Methods"))
        self.assertTrue(out.startswith("we developed FLASH-seq"))

    def test_extract_flash_seq_strips_dangling_citation(self):
        """回归：书籍章节体摘要，抽取句以悬挂引用 '...Nat Methods 10:1096-1098, 2013), we developed' 开头，须洗掉。"""
        ab = ("Building upon the existing Smart-seq2/3 workflows "
              "(Picelli et al Smart-seq2 for sensitive full-length transcriptome profiling "
              "in single cells. Nat Methods 10:1096-1098, 2013), we developed FLASH-seq (FS), "
              "a new full-length scRNA-seq method capable of detecting a significantly higher "
              "number of genes than previous versions.")
        out = eo.extract_objective(ab)
        self.assertFalse(out.startswith("Nat Methods"), f"悬挂引用未洗掉: {out[:60]}")
        self.assertTrue(out.startswith("we developed FLASH-seq"))

    def test_no_false_match_generic_capitalized_word(self):
        """回归（id=199）：'Adult human small intestine cell dissociation' 对任意含 'adult' 的论文，
        采纳相似度（token_similarity）须 <0.5，绝不因 method_match 误判为 1.0 而错配。"""
        sim = eo.token_similarity(
            "Adult human small intestine cell dissociation (on ice)",
            "The prevalence of adult attention-deficit hyperactivity disorder: "
            "A global systematic review and meta-analysis.",
        )
        self.assertLess(sim, 0.5)

    def test_method_match_acronym(self):
        # method token 'barseq' 命中标题 → ≥0.5（足以采纳）；另一方法 token high-throughput 不在标题 → 比例 0.5
        self.assertGreaterEqual(eo.method_match("BARseq - high-throughput cell typing", "BARseq: ..."), 0.5)
        # Micro-C XL：method_match 因 'xl' 过短无法整词命中，但 token 覆盖率=1.0 仍采纳
        self.assertGreaterEqual(
            max(eo.token_similarity("Micro-C XL", "Mammalian Micro-C-XL."),
                eo.method_match("Micro-C XL", "Mammalian Micro-C-XL.")), 0.5)
        # "Hybridization..." 与泛标题共享方法 token 'hybridization' → 0.333（<0.5，非强匹配，低于采纳门槛）
        self.assertLess(eo.method_match("Hybridization of Random-Primed DNA Probes",
                                        "A rapid non-radioactive procedure for plaque hybridization"), 0.5)

    def test_method_tokens_extraction(self):
        self.assertIn("barseq", eo._method_tokens("BARseq - high-throughput cell typing"))
        self.assertIn("high-throughput", eo._method_tokens("BARseq - high-throughput cell typing"))
        self.assertIn("micro-c", eo._method_tokens("Micro-C XL"))
        self.assertIn("hcr", eo._method_tokens("HCR - Embryo/Larvae fixation"))


class PubMedClientMethodTokenTest(TestCase):
    @patch("apps.knowledge.services.pubmed_client.request_with_resilience")
    def test_search_includes_method_token_query(self, mock_req):
        """search_by_protocol_name 应把方法缩写 token 作为检索词之一。

        "BARseq - high-throughput cell typing" 的方法 token 为 barseq / high-throughput，
        排序后首选 high-throughput，故方法缩写短语查询为 '"high-throughput"[Title/Abstract]'。
        仅该查询命中 id 9，其余返回空 → 验证方法 token 检索路径确实被纳入。
        """
        _METHOD_PHRASE = '"high-throughput"[Title/Abstract]'

        def fake(method, url, source="pubmed", timeout=15, **kwargs):
            if "esearch.fcgi" in url:
                term = (kwargs.get("params") or {}).get("term", "")
                if term == _METHOD_PHRASE:
                    return _make_response(
                        json_payload={"esearchresult": {"idlist": ["9"], "count": "1"}})
                return _make_response(
                    json_payload={"esearchresult": {"idlist": [], "count": "0"}})
            if "esummary.fcgi" in url:
                return _make_response(json_payload={"result": {
                    "9": {"uid": "9", "title": "BARseq: high-throughput cell typing",
                          "source": "J", "pubdate": "2021", "authors": [{"name": "A B"}]}}})
            if "efetch.fcgi" in url:
                return _make_response(text="OBJECTIVE: To type cells by sequencing.")
            return _make_response(json_payload={})

        mock_req.side_effect = fake
        client = PubMedClient()
        results = client.search_by_protocol_name("BARseq - high-throughput cell typing", max_results=5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["pmid"], "9")
        # 验证方法缩写短语查询确实出现在 esearch 调用序列中
        esearch_terms = [
            (c.kwargs.get("params") or {}).get("term", "")
            for c in mock_req.call_args_list
            if "esearch.fcgi" in c.args[1]
        ]
        self.assertIn(_METHOD_PHRASE, esearch_terms)


class RadioactiveGuardTest(TestCase):
    @patch("apps.knowledge.services.pubmed_client.request_with_resilience")
    def test_rejects_radioactive_contradiction(self, mock_req):
        """协议名说放射性，但命中的是非放射性文章 → 拒（宁 miss）。"""
        Protocol.objects.create(
            name="Radioactive in vitro transcription", slug="rivt",
            source=Protocol.Source.CURATED, objective="",
        )
        mock_req.side_effect = _pubmed_fake(
            esummary_title="A novel, non-radioactive eukaryotic in vitro transcription assay",
            abstract_text="OBJECTIVE: We developed a non-radioactive in vitro transcription assay.",
        )
        call_command("fetch_external_objectives", "--apply", "--only=curated")
        p = Protocol.objects.get(slug="rivt")
        self.assertEqual(p.objective, "", "放射性/非放射性矛盾不得误写")


class XmlAbstractParseTest(TestCase):
    def test_parse_pubmed_xml_abstract(self):
        xml = (
            '<PubmedArticleSet><PubmedArticle><MedlineCitation><Article>'
            '<Abstract>'
            '<AbstractText Label="BACKGROUND" NlmCategory="BACKGROUND">We studied X.</AbstractText>'
            '<AbstractText Label="OBJECTIVE" NlmCategory="OBJECTIVE">To ligate linkers to RNA ends.</AbstractText>'
            '</Abstract>'
            '</Article></MedlineCitation></PubmedArticle></PubmedArticleSet>'
        )
        out = _parse_pubmed_xml_abstract(xml)
        self.assertIn("BACKGROUND:", out)
        self.assertIn("OBJECTIVE:", out)
        self.assertIn("ligate linkers", out)

    def test_parse_pubmed_xml_abstract_no_label(self):
        xml = '<Abstract><AbstractText>Plain abstract body without label.</AbstractText></Abstract>'
        out = _parse_pubmed_xml_abstract(xml)
        self.assertIn("Plain abstract body", out)
        self.assertNotIn(":", out.split()[0])  # 无 Label 则不加冒号前缀

    def test_parse_pubmed_xml_abstract_none(self):
        self.assertEqual(_parse_pubmed_xml_abstract("<x></x>"), "")
        self.assertEqual(_parse_pubmed_xml_abstract(""), "")

    def test_parse_strips_inner_tags(self):
        xml = '<Abstract><AbstractText Label="OBJECTIVE">To <b>label</b> RNA.</AbstractText></Abstract>'
        out = _parse_pubmed_xml_abstract(xml)
        self.assertIn("OBJECTIVE:", out)
        self.assertIn("label RNA", out)
        self.assertNotIn("<b>", out)

    def test_parse_unescapes_html_entities(self):
        """NCBI 用数值实体表示希腊字母/符号（&#x3b2; = β），必须还原为字符，
        否则 objective 正文会出现 'pancreatic &#x3b2; cell' 这类脏文本。"""
        xml = (
            '<Abstract><AbstractText Label="OBJECTIVE">'
            'Pancreatic &#x3b2; cell and &#x3b1;-amylase assay in &lt;1 copy/mL &amp; urine.'
            '</AbstractText></Abstract>'
        )
        out = _parse_pubmed_xml_abstract(xml)
        self.assertIn("Pancreatic \u03b2 cell", out)
        self.assertIn("\u03b1-amylase", out)
        self.assertIn("<1 copy/mL & urine", out)
        self.assertNotIn("&#x", out)
        self.assertNotIn("&amp;", out)

    def test_parse_unescape_does_not_resurrect_tags(self):
        """先去标签再反转义：转义后的 &lt;b&gt; 只应变成字面文本，不得被当成标签再剥掉。"""
        xml = '<Abstract><AbstractText>Use &lt;b&gt;bold&lt;/b&gt; marker.</AbstractText></Abstract>'
        out = _parse_pubmed_xml_abstract(xml)
        self.assertIn("<b>bold</b> marker", out)


class FetchAbstractXmlTest(TestCase):
    @patch("apps.knowledge.services.pubmed_client.request_with_resilience")
    def test_fetch_abstract_xml_mode(self, mock_req):
        """efetch retmode=xml 返回 <AbstractText> → 干净解析，无引文头噪声。"""
        xml = ('<Abstract><AbstractText Label="OBJECTIVE" NlmCategory="OBJECTIVE">'
               'To label RNA.</AbstractText></Abstract>')
        mock_req.side_effect = lambda method, url, source="pubmed", timeout=15, **kw: (
            _make_response(text=xml) if "efetch.fcgi" in url else _make_response(json_payload={})
        )
        client = PubMedClient()
        out = client.fetch_abstract("123")
        self.assertIn("OBJECTIVE:", out)
        self.assertIn("label RNA", out)

    @patch("apps.knowledge.services.pubmed_client.request_with_resilience")
    def test_fetch_abstract_xml_fallback_to_text(self, mock_req):
        """XML 无 AbstractText → 回退 retmode=text（去 'PMID:' 前缀）。"""
        state = {"n": 0}
        def fake(method, url, source="pubmed", timeout=15, **kw):
            state["n"] += 1
            if "efetch.fcgi" in url:
                if state["n"] == 1:
                    return _make_response(text="<Error>no abstract text</Error>")
                return _make_response(text="PMID: 123\nThis is plain abstract text.")
            return _make_response(json_payload={})
        mock_req.side_effect = fake
        client = PubMedClient()
        out = client.fetch_abstract("123")
        self.assertIn("plain abstract text", out)
        self.assertNotIn("PMID:", out)


class SemanticGateTest(TestCase):
    @patch("apps.knowledge.services.pubmed_client.request_with_resilience")
    def test_semantic_gate_accepts_borderline(self, mock_req):
        """token<门槛 但语义>=SEMANTIC_THRESHOLD → 采纳（capture 同名方法措辞不同）。"""
        mock_req.side_effect = _pubmed_fake(
            esummary_title="A rapid non-radioactive procedure for plaque hybridization using biotinylated probes",
            abstract_text="OBJECTIVE: To detect DNA by hybridization.",
        )
        sem = eo.SEMANTIC_THRESHOLD  # 绑定常量，阈值调整不应让本例失效
        cand = eo.pubmed_candidate(
            PubMedClient(), "Hybridization of Random-Primed DNA Probes",
            eo.PUBMED_THRESHOLD, semantic_sim=sem,
        )
        self.assertIsNotNone(cand)
        self.assertTrue(cand["accepted"])
        self.assertEqual(cand["accept_reason"], "semantic")
        self.assertEqual(cand["semantic_similarity"], sem)

    @patch("apps.knowledge.services.pubmed_client.request_with_resilience")
    def test_semantic_gate_rejects_below(self, mock_req):
        """token<门槛 且 语义<SEMANTIC_THRESHOLD → 不采纳（accept_reason=below）。"""
        mock_req.side_effect = _pubmed_fake(
            esummary_title="Completely unrelated yeast study",
            abstract_text="OBJECTIVE: yeast growth.",
        )
        cand = eo.pubmed_candidate(
            PubMedClient(), "Linker Ligation Protocol",
            eo.PUBMED_THRESHOLD, semantic_sim=eo.SEMANTIC_THRESHOLD - 0.30,
        )
        self.assertIsNotNone(cand)  # 有 objective 文本，只是不采纳
        self.assertFalse(cand["accepted"])
        self.assertEqual(cand["accept_reason"], "below")

    @patch("apps.knowledge.services.pubmed_client.request_with_resilience")
    def test_semantic_none_keeps_token_only(self, mock_req):
        """未提供语义分 → 仅 token 门生效（低 token 不采纳）。"""
        mock_req.side_effect = _pubmed_fake(
            esummary_title="Completely unrelated yeast study",
            abstract_text="OBJECTIVE: yeast growth.",
        )
        cand = eo.pubmed_candidate(
            PubMedClient(), "Linker Ligation Protocol", eo.PUBMED_THRESHOLD,
        )
        self.assertFalse(cand["accepted"])
        self.assertEqual(cand["accept_reason"], "below")
        self.assertIsNone(cand["semantic_similarity"])


class SimilarityAndChooseTest(TestCase):
    def test_title_similarity(self):
        self.assertAlmostEqual(eo.title_similarity("RNA Labeling", "RNA Labeling"), 1.0)
        self.assertLess(eo.title_similarity("RNA Labeling", "Yeast Fermentation"), 0.5)
        self.assertEqual(eo.title_similarity("", "x"), 0.0)

    def test_choose_best_prefers_higher_similarity(self):
        pm = {"objective": "from pubmed", "pmid": "1", "article_title": "A", "similarity": 0.7}
        bio = {"objective": "from bio", "url": "u", "source_title": "B", "similarity": 0.9}
        chosen = eo.choose_best_match("x", pm, bio)
        self.assertEqual(chosen[0], "from bio")
        self.assertEqual(chosen[1], "bioprotocol")

    def test_choose_best_pubmed_tie_priority(self):
        pm = {"objective": "p", "pmid": "1", "article_title": "A", "similarity": 0.8}
        bio = {"objective": "b", "url": "u", "source_title": "B", "similarity": 0.8}
        chosen = eo.choose_best_match("x", pm, bio)
        self.assertEqual(chosen[1], "pubmed")

    def test_choose_best_none_when_both_empty(self):
        self.assertIsNone(eo.choose_best_match("x", None, None))


class CommandTest(TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="extobj_")

    def _write_bio(self, data):
        p = os.path.join(self.tmp, "bio.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        return p

    def test_command_importable(self):
        from apps.knowledge.management.commands import (  # noqa: F401
            fetch_external_objectives,
        )

    @patch("apps.knowledge.services.pubmed_client.request_with_resilience")
    def test_fills_from_pubmed_good_match(self, mock_req):
        proto = Protocol.objects.create(
            name="Linker Ligation at both Ends of RNAs on Beads",
            slug="llr", source=Protocol.Source.CURATED, objective="",
        )
        mock_req.side_effect = _pubmed_fake(
            esummary_title="Linker Ligation at both Ends of RNAs on Beads",
            abstract_text="BACKGROUND: x. OBJECTIVE: To ligate linkers to RNA ends on beads. METHODS: y.",
        )
        call_command("fetch_external_objectives", "--apply", "--only=curated")
        proto.refresh_from_db()
        self.assertIn("ligate linkers", proto.objective)

    @patch("apps.knowledge.services.pubmed_client.request_with_resilience")
    def test_miss_when_low_similarity(self, mock_req):
        """宁 miss 不错配：PubMed 返回无关标题 → 不写 objective。"""
        proto = Protocol.objects.create(
            name="Linker Ligation at both Ends of RNAs on Beads",
            slug="llr2", source=Protocol.Source.CURATED, objective="",
        )
        mock_req.side_effect = _pubmed_fake(
            esummary_title="Completely unrelated study of yeast fermentation dynamics",
            abstract_text="OBJECTIVE: To measure yeast growth.",
        )
        call_command("fetch_external_objectives", "--apply", "--only=curated")
        proto.refresh_from_db()
        self.assertEqual(proto.objective, "", "低相似度不得误写")

    @patch("apps.knowledge.services.pubmed_client.request_with_resilience")
    def test_dry_run_no_persist(self, mock_req):
        Protocol.objects.create(
            name="RNA Labeling Protocol", slug="rl", source=Protocol.Source.CURATED, objective="",
        )
        mock_req.side_effect = _pubmed_fake(
            esummary_title="RNA Labeling Protocol",
            abstract_text="OBJECTIVE: To label RNA.",
        )
        call_command("fetch_external_objectives", "--only=curated")
        p = Protocol.objects.get(slug="rl")
        self.assertEqual(p.objective, "")

    @patch("apps.knowledge.services.pubmed_client.request_with_resilience")
    def test_idempotent(self, mock_req):
        proto = Protocol.objects.create(
            name="RNA Labeling Protocol", slug="rlid", source=Protocol.Source.CURATED, objective="",
        )
        fake = _pubmed_fake("RNA Labeling Protocol", "OBJECTIVE: To label RNA.")
        mock_req.side_effect = fake
        call_command("fetch_external_objectives", "--apply", "--only=curated")
        mock_req.side_effect = fake
        call_command("fetch_external_objectives", "--apply", "--only=curated")
        proto.refresh_from_db()
        self.assertEqual(proto.objective, "To label RNA.")

    @patch("apps.knowledge.services.pubmed_client.request_with_resilience")
    def test_bioprotocol_override_wins(self, mock_req):
        """Bio-protocol override 相似度更高 → 采纳 bio 而非低相似度 pubmed。"""
        proto = Protocol.objects.create(
            name="Linker Ligation at both Ends of RNAs on Beads",
            slug="llrbio", source=Protocol.Source.CURATED, objective="",
        )
        # pubmed 返回无关标题（低相似度被拒）
        mock_req.side_effect = _pubmed_fake(
            esummary_title="Unrelated yeast paper", abstract_text="OBJECTIVE: yeast.",
        )
        bio_file = self._write_bio({
            "Linker Ligation at both Ends of RNAs on Beads": {
                "objective": "BIO: click ligation of RNA linkers on beads.",
                "source_title": "Linker Ligation at both Ends of RNAs on Beads",
                "url": "https://bio-protocol.com/x",
            }
        })
        call_command("fetch_external_objectives", "--apply", "--only=curated",
                     "--bio-protocol-file", bio_file)
        proto.refresh_from_db()
        self.assertIn("BIO:", proto.objective)

    @patch("apps.knowledge.services.pubmed_client.request_with_resilience")
    def test_bioprotocol_below_threshold_rejected(self, mock_req):
        """Bio override source_title 与协议名无关 → 低于门槛被拒，pubmed 也低 → 跳过。"""
        proto = Protocol.objects.create(
            name="Linker Ligation at both Ends of RNAs on Beads",
            slug="llrbad", source=Protocol.Source.CURATED, objective="",
        )
        mock_req.side_effect = _pubmed_fake(
            esummary_title="Unrelated yeast paper", abstract_text="OBJECTIVE: yeast.",
        )
        bio_file = self._write_bio({
            "Linker Ligation at both Ends of RNAs on Beads": {
                "objective": "SHOULD NOT BE WRITTEN",
                "source_title": "Totally different bio-protocol article title",
                "url": "https://bio-protocol.com/y",
            }
        })
        call_command("fetch_external_objectives", "--apply", "--only=curated",
                     "--bio-protocol-file", bio_file)
        proto.refresh_from_db()
        self.assertEqual(proto.objective, "", "Bio override 低相似度不得误写")

    @patch("apps.knowledge.services.pubmed_client.request_with_resilience")
    def test_only_filter_curated(self, mock_req):
        curated = Protocol.objects.create(
            name="RNA Labeling Protocol", slug="rc", source=Protocol.Source.CURATED, objective="",
        )
        bio_p = Protocol.objects.create(
            name="RNA Labeling Protocol", slug="rb", source=Protocol.Source.BIOPROCORPUS, objective="",
        )
        mock_req.side_effect = _pubmed_fake(
            esummary_title="RNA Labeling Protocol", abstract_text="OBJECTIVE: To label RNA.",
        )
        call_command("fetch_external_objectives", "--apply", "--only=curated")
        curated.refresh_from_db()
        bio_p.refresh_from_db()
        self.assertIn("label RNA", curated.objective)
        self.assertEqual(bio_p.objective, "")

    @patch("apps.knowledge.services.pubmed_client.request_with_resilience")
    def test_record_source_appends_pmid(self, mock_req):
        proto = Protocol.objects.create(
            name="RNA Labeling Protocol", slug="rcs", source=Protocol.Source.CURATED,
            objective="", references="",
        )
        mock_req.side_effect = _pubmed_fake(
            esummary_title="RNA Labeling Protocol", abstract_text="OBJECTIVE: To label RNA.",
        )
        call_command("fetch_external_objectives", "--apply", "--only=curated", "--record-source")
        proto.refresh_from_db()
        self.assertIn("PMID:123", proto.references)

    @patch("apps.knowledge.services.pubmed_client.request_with_resilience")
    def test_semantic_report_accepts(self, mock_req):
        """--semantic-report 注入语义分：token<门槛 但语义高 → 采纳。"""
        proto = Protocol.objects.create(
            name="Hybridization of Random-Primed DNA Probes", slug="hrpsem",
            source=Protocol.Source.CURATED, objective="",
        )
        mock_req.side_effect = _pubmed_fake(
            esummary_title="A rapid non-radioactive procedure for plaque hybridization using biotinylated probes",
            abstract_text="OBJECTIVE: To detect DNA by hybridization.",
        )
        sr = os.path.join(self.tmp, "sem.json")
        with open(sr, "w", encoding="utf-8") as f:
            json.dump({proto.id: eo.SEMANTIC_THRESHOLD}, f)
        call_command("fetch_external_objectives", "--apply", "--only=curated",
                     "--semantic-report", sr)
        proto.refresh_from_db()
        self.assertIn("hybridization", proto.objective)

    # ---- 确定性重放：--from-report / --allowlist ----
    # 背景：PubMed 间歇 502，联网重跑会让 apply 结果不可复现；且自动门放行的候选里
    # 混有「正文点名了另一个方法」的错配（Omni-ATAC / GRO-Seq / DNA probes），
    # 须由人工复核白名单收口。故 apply 走「零网络重放已审核报告 + 只写白名单 id」。

    def _write_report(self, entries):
        p = os.path.join(self.tmp, "report.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False)
        return p

    @patch("apps.knowledge.services.pubmed_client.request_with_resilience")
    def test_from_report_replays_without_network(self, mock_req):
        """--from-report：直接用报告里的 objective 落库，全程零网络请求。"""
        mock_req.side_effect = AssertionError("--from-report 模式不得发起网络请求")
        proto = Protocol.objects.create(
            name="Tissue NET-seq", slug="tnetseq",
            source=Protocol.Source.CURATED, objective="",
        )
        rep = self._write_report([{
            "id": proto.id, "name": proto.name, "source": proto.source,
            "pubmed": {
                "objective": "To map RNA polymerase density.",
                "pmid": "999",
                "article_title": "Native elongating transcript sequencing (NET-seq).",
                "similarity": 0.857, "semantic_similarity": 0.917,
                "accepted": True, "accept_reason": "token",
            },
            "bioprotocol": None, "chosen": "pubmed",
        }])
        call_command("fetch_external_objectives", "--apply", "--only=curated",
                     "--from-report", rep)
        proto.refresh_from_db()
        self.assertEqual(proto.objective, "To map RNA polymerase density.")
        mock_req.assert_not_called()

    def test_from_report_reevaluates_gate(self):
        """重放不盲信报告里的 accepted：低 token + 无语义分 → 仍拒（门槛是唯一权威）。"""
        proto = Protocol.objects.create(
            name="qPRO-seq", slug="qpro", source=Protocol.Source.CURATED, objective="",
        )
        rep = self._write_report([{
            "id": proto.id, "name": proto.name, "source": proto.source,
            "pubmed": {
                "objective": "GRO-Seq measures nascent transcription.",
                "pmid": "1", "article_title": "Global Run-on Sequencing (GRO-Seq).",
                "similarity": 0.375, "semantic_similarity": None,
                "accepted": True, "accept_reason": "token",
            },
            "bioprotocol": None, "chosen": "pubmed",
        }])
        call_command("fetch_external_objectives", "--apply", "--only=curated",
                     "--from-report", rep)
        proto.refresh_from_db()
        self.assertEqual(proto.objective, "", "报告 accepted=True 也不得越过当前门槛")

    def test_from_report_semantic_gate_accepts(self):
        """重放 + --semantic-report：token 低但语义达标 → 采纳。"""
        proto = Protocol.objects.create(
            name="dU-Tn5 stranded RNA-seq experiment", slug="dutn5",
            source=Protocol.Source.CURATED, objective="",
        )
        rep = self._write_report([{
            "id": proto.id, "name": proto.name, "source": proto.source,
            "pubmed": {
                "objective": "We developed a dU-adaptor-assembled Tn5 protocol.",
                "pmid": "2",
                "article_title": "A novel strand-specific RNA-sequencing protocol using dU-adaptor-assembled Tn5.",
                "similarity": 0.333, "semantic_similarity": None,
                "accepted": False, "accept_reason": "below",
            },
            "bioprotocol": None, "chosen": None,
        }])
        sr = os.path.join(self.tmp, "sem2.json")
        with open(sr, "w", encoding="utf-8") as f:
            json.dump({proto.id: eo.SEMANTIC_THRESHOLD + 0.05}, f)
        call_command("fetch_external_objectives", "--apply", "--only=curated",
                     "--from-report", rep, "--semantic-report", sr)
        proto.refresh_from_db()
        self.assertIn("dU-adaptor", proto.objective)

    def test_allowlist_limits_writes(self):
        """--allowlist：门槛放行两条，但只写白名单内那条（人工复核收口）。"""
        keep = Protocol.objects.create(name="Keep Me", slug="keepme",
                                       source=Protocol.Source.CURATED, objective="")
        drop = Protocol.objects.create(name="Drop Me", slug="dropme",
                                       source=Protocol.Source.CURATED, objective="")
        rep = self._write_report([
            {"id": keep.id, "name": keep.name, "source": keep.source,
             "pubmed": {"objective": "Kept objective.", "pmid": "3",
                        "article_title": "Keep Me", "similarity": 1.0,
                        "accepted": True, "accept_reason": "token"},
             "bioprotocol": None, "chosen": "pubmed"},
            {"id": drop.id, "name": drop.name, "source": drop.source,
             "pubmed": {"objective": "Dropped objective.", "pmid": "4",
                        "article_title": "Drop Me", "similarity": 1.0,
                        "accepted": True, "accept_reason": "token"},
             "bioprotocol": None, "chosen": "pubmed"},
        ])
        al = os.path.join(self.tmp, "allow.json")
        with open(al, "w", encoding="utf-8") as f:
            json.dump([keep.id], f)
        call_command("fetch_external_objectives", "--apply", "--only=curated",
                     "--from-report", rep, "--allowlist", al)
        keep.refresh_from_db()
        drop.refresh_from_db()
        self.assertEqual(keep.objective, "Kept objective.")
        self.assertEqual(drop.objective, "", "白名单外的协议不得写入")

    def test_allowlist_accepts_csv(self):
        """--allowlist 也接受逗号分隔 id 串（省去临时文件）。"""
        keep = Protocol.objects.create(name="Csv Keep", slug="csvkeep",
                                       source=Protocol.Source.CURATED, objective="")
        drop = Protocol.objects.create(name="Csv Drop", slug="csvdrop",
                                       source=Protocol.Source.CURATED, objective="")
        rep = self._write_report([
            {"id": p.id, "name": p.name, "source": p.source,
             "pubmed": {"objective": "Obj %s." % p.id, "pmid": str(p.id),
                        "article_title": p.name, "similarity": 1.0,
                        "accepted": True, "accept_reason": "token"},
             "bioprotocol": None, "chosen": "pubmed"}
            for p in (keep, drop)
        ])
        call_command("fetch_external_objectives", "--apply", "--only=curated",
                     "--from-report", rep, "--allowlist", str(keep.id))
        keep.refresh_from_db()
        drop.refresh_from_db()
        self.assertTrue(keep.objective)
        self.assertEqual(drop.objective, "")

    def test_from_report_missing_file_errors(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            call_command("fetch_external_objectives", "--from-report",
                         os.path.join(self.tmp, "nope.json"))


class ReplayCandidateTest(TestCase):
    """replay_candidate：对已抓取报告中的候选重放采纳门（纯函数、零网络）。"""

    def test_replay_none_and_empty(self):
        self.assertIsNone(eo.replay_candidate(None))
        self.assertIsNone(eo.replay_candidate({"objective": "", "similarity": 1.0}))

    def test_replay_token_gate(self):
        out = eo.replay_candidate({"objective": "x", "similarity": 0.9})
        self.assertTrue(out["accepted"])
        self.assertEqual(out["accept_reason"], "token")

    def test_replay_semantic_gate(self):
        out = eo.replay_candidate({"objective": "x", "similarity": 0.1},
                                  semantic_sim=eo.SEMANTIC_THRESHOLD)
        self.assertTrue(out["accepted"])
        self.assertEqual(out["accept_reason"], "semantic")

    def test_replay_below_both(self):
        out = eo.replay_candidate({"objective": "x", "similarity": 0.1},
                                  semantic_sim=0.1)
        self.assertFalse(out["accepted"])
        self.assertEqual(out["accept_reason"], "below")

    def test_replay_uses_embedded_semantic_when_not_overridden(self):
        """报告里已带 semantic_similarity 时，未显式传入则沿用报告值。"""
        out = eo.replay_candidate(
            {"objective": "x", "similarity": 0.1,
             "semantic_similarity": eo.SEMANTIC_THRESHOLD + 0.01})
        self.assertTrue(out["accepted"])
        self.assertEqual(out["accept_reason"], "semantic")


# ══════════════════════════════════════════════════════════════════
# Europe PMC 源（2026-08-08 新增）
#
# 为什么加第三个源：只读探针实测（70 条空 objective）证明
# ① resultType=core 一次请求即内嵌 abstractText（PubMed 需 esearch+efetch 两步）；
# ② 覆盖 PubMed 不索引的预印本平台（source=PPR：protocols.exchange /
#    Research Square / bioRxiv），而我们补的正是「协议」，源头天然对口；
# ③ 换源能纠正错配（id=149 上批被 PubMed 判错配，EPMC 命中真正源论文）。
# 但探针也证明 EPMC 自动门错配率（57%）高于 PubMed（33%），故落库仍须
# 「--from-report 重放 + --allowlist 人工白名单」收口。
# ══════════════════════════════════════════════════════════════════


class EuropePmcCleanAbstractTest(TestCase):
    """摘要清洗：与 PubMed XML 路径同口径「先去标签 → 再反转义」，外加剥前导 Abstract。"""

    def test_empty(self):
        self.assertEqual(clean_abstract(""), "")
        self.assertEqual(clean_abstract(None), "")

    def test_strips_inner_tags_and_unescapes_entities(self):
        out = clean_abstract("To <b>label</b> RNA with &#x3b2;-amylase &amp; urea.")
        self.assertIn("label RNA", out)
        self.assertIn("\u03b2-amylase", out)
        self.assertIn("& urea", out)
        self.assertNotIn("<b>", out)
        self.assertNotIn("&#x", out)

    def test_unescape_does_not_resurrect_tags(self):
        """顺序铁律：先去标签再反转义，&lt;b&gt; 只应变字面文本，不得被当真标签剥掉。"""
        out = clean_abstract("Use &lt;b&gt;bold&lt;/b&gt; marker.")
        self.assertIn("<b>bold</b> marker", out)

    def test_strips_leading_abstract_wrapper(self):
        """EPMC 对 PPR 源固定包装前导 'Abstract' 字样，须剥掉，否则 objective
        会以 'Abstract The step-by-step...' 开头。"""
        out = clean_abstract("Abstract The step-by-step protocol describes Hi-C.")
        self.assertTrue(out.startswith("The step-by-step"), out[:40])
        self.assertEqual(clean_abstract("Abstract: We present X."), "We present X.")

    def test_does_not_strip_word_starting_with_abstract(self):
        """'Abstracts' 不是包装词，不得误剥。"""
        out = clean_abstract("Abstracts were screened manually.")
        self.assertTrue(out.startswith("Abstracts were"))

    def test_collapses_whitespace(self):
        self.assertEqual(clean_abstract("a\n\n  b\tc"), "a b c")


class EuropePmcQueryTest(TestCase):
    def test_three_tier_queries(self):
        qs = build_queries('Micro-C "XL"')
        self.assertEqual(len(qs), 3)
        self.assertTrue(qs[0].startswith('TITLE:"'), qs[0])
        self.assertIn("OR ABSTRACT:", qs[1])
        self.assertNotIn('"', qs[2])  # 第三级全文检索，无短语引号

    def test_strips_quotes_from_name(self):
        qs = build_queries('Say "hello" now')
        self.assertNotIn('hello"', qs[0].replace('TITLE:"', '').rstrip('"'))
        for q in qs:
            self.assertNotIn('""', q)

    def test_empty_name(self):
        self.assertEqual(build_queries(""), [])
        self.assertEqual(build_queries(None), [])


class EuropePmcSearchTest(TestCase):
    @patch("apps.knowledge.services.europepmc_client.request_with_resilience")
    def test_parses_core_result_with_embedded_abstract(self, mock_req):
        mock_req.return_value = _epmc_response([_epmc_article(
            title="Agrobacterium-mediated transformation of asparagus",
            abstract="Abstract This protocol describes transformation of asparagus.",
            pmid="31589638", doi="10.1007/x", pmcid="PMC9",
        )] * 1)
        out = EuropePMCClient().search_by_protocol_name(
            "Agrobacterium-mediated transformation of asparagus", max_results=1)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["pmid"], "31589638")
        self.assertEqual(out[0]["doi"], "10.1007/x")
        self.assertEqual(out[0]["pmcid"], "PMC9")
        self.assertFalse(out[0]["is_preprint"])
        # 摘要内嵌 → 无需第二次请求取摘要
        self.assertTrue(out[0]["abstract"].startswith("This protocol describes"))
        self.assertEqual(mock_req.call_count, 1, "一级命中即停，且不再单独取摘要")

    @patch("apps.knowledge.services.europepmc_client.request_with_resilience")
    def test_falls_back_to_next_tier_when_empty(self, mock_req):
        calls = []

        def fake(method, url, source="europepmc", timeout=15, **kw):
            q = (kw.get("params") or {}).get("query", "")
            calls.append(q)
            if q.startswith("TITLE:"):
                return _epmc_response([])
            return _epmc_response([_epmc_article("s3-ATAC seq", "OBJECTIVE: To profile chromatin.")])

        mock_req.side_effect = fake
        out = EuropePMCClient().search_by_protocol_name("s3-ATAC", max_results=1)
        self.assertEqual(len(out), 1)
        self.assertGreaterEqual(len(calls), 2, "一级空应降级到二级")
        self.assertTrue(calls[0].startswith('TITLE:"'))

    @patch("apps.knowledge.services.europepmc_client.request_with_resilience")
    def test_strips_markup_from_title(self, mock_req):
        """实测 bioRxiv 条目标题内嵌裸 <i> 标签，标题也须走同一去标记路径。"""
        mock_req.return_value = _epmc_response([_epmc_article(
            title="Newly synthesized mRNA in  <i>Saccharomyces cerevisiae</i>",
            abstract="OBJECTIVE: To measure nascent mRNA.",
            doi="10.1101/2024.01.26.577353", source="PPR",
        )])
        out = EuropePMCClient().search_by_protocol_name(
            "Newly synthesized mRNA in Saccharomyces cerevisiae", max_results=1)
        self.assertEqual(out[0]["title"],
                         "Newly synthesized mRNA in Saccharomyces cerevisiae")
        self.assertNotIn("<i>", out[0]["title"])

    @patch("apps.knowledge.services.europepmc_client.request_with_resilience")
    def test_marks_preprint_source_ppr(self, mock_req):
        """PPR = protocols.exchange / Research Square / bioRxiv，PubMed 完全不索引。"""
        mock_req.return_value = _epmc_response([_epmc_article(
            title="In situ Hi-C for mosquito embryos",
            abstract="Abstract Step-by-step Hi-C for mosquito embryos.",
            pmid="", doi="10.21203/rs.3.pex-1840/v1", source="PPR",
        )])
        out = EuropePMCClient().search_by_protocol_name(
            "In situ Hi-C for mosquito embryos", max_results=1)
        self.assertTrue(out[0]["is_preprint"])
        self.assertEqual(out[0]["pmid"], "")
        self.assertEqual(out[0]["doi"], "10.21203/rs.3.pex-1840/v1")

    @patch("apps.knowledge.services.europepmc_client.request_with_resilience")
    def test_dedups_same_article_across_tiers(self, mock_req):
        art = _epmc_article("BARseq typing", "OBJECTIVE: To type cells.", doi="10.1/dup")
        mock_req.return_value = _epmc_response([art])
        out = EuropePMCClient().search_by_protocol_name("BARseq typing", max_results=5)
        self.assertEqual(len(out), 1, "同一 DOI 跨级去重")
        self.assertEqual(mock_req.call_count, 3, "未满 max_results 应走完三级")

    @patch("apps.knowledge.services.europepmc_client.request_with_resilience")
    def test_network_error_returns_empty_not_raise(self, mock_req):
        mock_req.side_effect = RuntimeError("boom")
        self.assertEqual(EuropePMCClient().search_by_protocol_name("x"), [])

    def test_empty_name_no_request(self):
        self.assertEqual(EuropePMCClient().search_by_protocol_name(""), [])


class RadioactiveGuardHelperTest(TestCase):
    """放射性/非放射性矛盾守卫提取为共享纯函数，PubMed / Europe PMC 两路复用。"""

    def test_radioactive_name_vs_nonradioactive_article(self):
        self.assertTrue(eo._radioactive_conflict(
            "Radioactive in vitro transcription",
            "A novel, non-radioactive in vitro transcription assay", ""))

    def test_nonradioactive_name_vs_radioactive_article(self):
        self.assertTrue(eo._radioactive_conflict(
            "Non-radioactive in situ hybridization",
            "Radioactive in situ hybridization with 32P probes", ""))

    def test_nonradioactive_name_matching_nonradioactive_article_is_ok(self):
        """回归：协议名本身写着「非放射性」，命中非放射性文章不是矛盾，不得误拒。"""
        self.assertFalse(eo._radioactive_conflict(
            "Non-radioactive in situ hybridization",
            "A non-radioactive in situ hybridization procedure", ""))

    def test_no_radioactivity_mentioned(self):
        self.assertFalse(eo._radioactive_conflict("RNA Labeling", "RNA Labeling", ""))


class ReferenceTagTest(TestCase):
    """归因 tag：PubMed 只有 PMID，Europe PMC 的 PPR 源只有 DOI，须分别成型。"""

    def test_pmid(self):
        self.assertEqual(eo.reference_tag("pubmed", "31589638"), "PMID:31589638")
        self.assertEqual(eo.reference_tag("europepmc", "31589638"), "PMID:31589638")

    def test_doi(self):
        self.assertEqual(eo.reference_tag("europepmc", "10.21203/rs.3.pex-1840/v1"),
                         "DOI:10.21203/rs.3.pex-1840/v1")
        self.assertEqual(eo.reference_tag("europepmc", "doi:10.1/x"), "DOI:10.1/x")

    def test_pmcid(self):
        self.assertEqual(eo.reference_tag("europepmc", "PMC123456"), "PMCID:PMC123456")

    def test_bioprotocol_url_kept_raw(self):
        url = "https://bio-protocol.org/e123"
        self.assertEqual(eo.reference_tag("bioprotocol", url), url)

    def test_empty(self):
        self.assertEqual(eo.reference_tag("pubmed", ""), "")
        self.assertEqual(eo.reference_tag("europepmc", None), "")


class EpmcCandidateTest(TestCase):
    @patch("apps.knowledge.services.europepmc_client.request_with_resilience")
    def test_accepts_high_token_match(self, mock_req):
        mock_req.return_value = _epmc_response([_epmc_article(
            title="In situ Hi-C for mosquito embryos",
            abstract="Abstract OBJECTIVE: To generate chromatin contact maps in mosquito embryos.",
            doi="10.21203/rs.3.pex-1840/v1", source="PPR",
        )])
        cand = eo.epmc_candidate(EuropePMCClient(), "In situ Hi-C for mosquito embryos")
        self.assertIsNotNone(cand)
        self.assertTrue(cand["accepted"])
        self.assertEqual(cand["accept_reason"], "token")
        self.assertIn("chromatin contact maps", cand["objective"])
        self.assertEqual(cand["source_ref"], "10.21203/rs.3.pex-1840/v1")
        self.assertTrue(cand["is_preprint"])

    @patch("apps.knowledge.services.europepmc_client.request_with_resilience")
    def test_source_ref_prefers_pmid(self, mock_req):
        mock_req.return_value = _epmc_response([_epmc_article(
            title="Agrobacterium-mediated transformation of asparagus",
            abstract="OBJECTIVE: To transform asparagus via Agrobacterium.",
            pmid="31589638", doi="10.1007/x",
        )])
        cand = eo.epmc_candidate(
            EuropePMCClient(), "Agrobacterium-mediated transformation of asparagus")
        self.assertEqual(cand["source_ref"], "31589638")

    @patch("apps.knowledge.services.europepmc_client.request_with_resilience")
    def test_rejects_radioactive_contradiction(self, mock_req):
        """id=178 实例：协议名放射性，EPMC 命中的是非放射性替代法 → 语义相反须拒。"""
        mock_req.return_value = _epmc_response([_epmc_article(
            title="A non-radioactive alternative to in vitro transcription labelling",
            abstract="OBJECTIVE: We replace radioactive labelling with a non-radioactive method.",
            pmid="7",
        )])
        cand = eo.epmc_candidate(EuropePMCClient(), "Radioactive in vitro transcription")
        self.assertIsNone(cand, "放射性矛盾不得产出候选")

    @patch("apps.knowledge.services.europepmc_client.request_with_resilience")
    def test_no_hits_returns_none(self, mock_req):
        mock_req.return_value = _epmc_response([])
        self.assertIsNone(eo.epmc_candidate(EuropePMCClient(), "Nothing Findable Here"))

    @patch("apps.knowledge.services.europepmc_client.request_with_resilience")
    def test_below_threshold_not_accepted(self, mock_req):
        mock_req.return_value = _epmc_response([_epmc_article(
            title="Completely unrelated yeast fermentation study",
            abstract="OBJECTIVE: To measure yeast growth.", pmid="8",
        )])
        cand = eo.epmc_candidate(EuropePMCClient(), "Linker Ligation Protocol")
        self.assertIsNotNone(cand)
        self.assertFalse(cand["accepted"])
        self.assertEqual(cand["accept_reason"], "below")

    @patch("apps.knowledge.services.europepmc_client.request_with_resilience")
    def test_semantic_gate_accepts_borderline(self, mock_req):
        mock_req.return_value = _epmc_response([_epmc_article(
            title="Completely unrelated yeast fermentation study",
            abstract="OBJECTIVE: To measure yeast growth.", pmid="8",
        )])
        cand = eo.epmc_candidate(EuropePMCClient(), "Linker Ligation Protocol",
                                 semantic_sim=eo.SEMANTIC_THRESHOLD)
        self.assertTrue(cand["accepted"])
        self.assertEqual(cand["accept_reason"], "semantic")


class ChooseBestMatchEpmcTest(TestCase):
    def _pm(self, sim):
        return {"objective": "p", "pmid": "1", "article_title": "A", "similarity": sim}

    def _ep(self, sim):
        return {"objective": "e", "source_ref": "10.1/x", "article_title": "E",
                "similarity": sim}

    def _bio(self, sim):
        return {"objective": "b", "url": "u", "source_title": "B", "similarity": sim}

    def test_epmc_wins_on_higher_similarity(self):
        chosen = eo.choose_best_match("x", self._pm(0.5), self._bio(0.5), self._ep(0.9))
        self.assertEqual(chosen[1], "europepmc")
        self.assertEqual(chosen[2], "10.1/x")

    def test_pubmed_wins_tie(self):
        chosen = eo.choose_best_match("x", self._pm(0.8), self._bio(0.8), self._ep(0.8))
        self.assertEqual(chosen[1], "pubmed")

    def test_epmc_beats_bio_on_tie(self):
        chosen = eo.choose_best_match("x", None, self._bio(0.8), self._ep(0.8))
        self.assertEqual(chosen[1], "europepmc")

    def test_backward_compatible_two_arg_call(self):
        chosen = eo.choose_best_match("x", self._pm(0.9), self._bio(0.1))
        self.assertEqual(chosen[1], "pubmed")

    def test_none_when_all_empty(self):
        self.assertIsNone(eo.choose_best_match("x", None, None, None))


class SourceRateTest(TestCase):
    def test_europepmc_rate_configured(self):
        """未配置会落 _DEFAULT_RATE=(1,1)，须显式声明以免限速语义靠默认值兜底。"""
        from core.datasource_client import SOURCE_RATES
        self.assertIn("europepmc", SOURCE_RATES)
        cap, rate = SOURCE_RATES["europepmc"]
        self.assertGreaterEqual(cap, 1)
        self.assertGreaterEqual(rate, 1)


class CommandEpmcTest(TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="extobj_epmc_")

    def _write_report(self, entries):
        p = os.path.join(self.tmp, "report.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False)
        return p

    @patch("apps.knowledge.services.europepmc_client.request_with_resilience")
    @patch("apps.knowledge.services.pubmed_client.request_with_resilience")
    def test_epmc_disabled_by_default(self, mock_pm, mock_ep):
        """不加 --epmc 不得发起 Europe PMC 请求（保持既有行为）。"""
        Protocol.objects.create(name="Hi-C mosquito embryos", slug="hicm0",
                                source=Protocol.Source.CURATED, objective="")
        mock_pm.side_effect = _pubmed_fake("Unrelated", "OBJECTIVE: nothing.")
        call_command("fetch_external_objectives", "--only=curated")
        mock_ep.assert_not_called()

    @patch("apps.knowledge.services.europepmc_client.request_with_resilience")
    @patch("apps.knowledge.services.pubmed_client.request_with_resilience")
    def test_epmc_flag_fills_objective(self, mock_pm, mock_ep):
        """--epmc：PubMed 低相似度被拒，Europe PMC 命中 → 采纳 EPMC。"""
        proto = Protocol.objects.create(name="In situ Hi-C for mosquito embryos",
                                        slug="hicm", source=Protocol.Source.CURATED,
                                        objective="")
        mock_pm.side_effect = _pubmed_fake("Unrelated yeast paper", "OBJECTIVE: yeast.")
        mock_ep.return_value = _epmc_response([_epmc_article(
            title="In situ Hi-C for mosquito embryos",
            abstract="Abstract OBJECTIVE: To map chromatin contacts in mosquito embryos.",
            doi="10.21203/rs.3.pex-1840/v1", source="PPR",
        )])
        call_command("fetch_external_objectives", "--apply", "--only=curated", "--epmc")
        proto.refresh_from_db()
        self.assertIn("chromatin contacts", proto.objective)

    @patch("apps.knowledge.services.europepmc_client.request_with_resilience")
    @patch("apps.knowledge.services.pubmed_client.request_with_resilience")
    def test_epmc_record_source_writes_doi_tag(self, mock_pm, mock_ep):
        """PPR 源无 PMID 只有 DOI → references 必须写 DOI: 而非错误的 PMID:10.xxx。"""
        proto = Protocol.objects.create(name="In situ Hi-C for mosquito embryos",
                                        slug="hicm2", source=Protocol.Source.CURATED,
                                        objective="", references="")
        mock_pm.side_effect = _pubmed_fake("Unrelated yeast paper", "OBJECTIVE: yeast.")
        mock_ep.return_value = _epmc_response([_epmc_article(
            title="In situ Hi-C for mosquito embryos",
            abstract="Abstract OBJECTIVE: To map chromatin contacts in mosquito embryos.",
            doi="10.21203/rs.3.pex-1840/v1", source="PPR",
        )])
        call_command("fetch_external_objectives", "--apply", "--only=curated",
                     "--epmc", "--record-source")
        proto.refresh_from_db()
        self.assertIn("DOI:10.21203/rs.3.pex-1840/v1", proto.references)
        self.assertNotIn("PMID:10.", proto.references)

    def test_from_report_replays_epmc(self):
        """确定性落库路径：--from-report 重放 europepmc 候选，零网络。"""
        proto = Protocol.objects.create(name="In situ Hi-C for mosquito embryos",
                                        slug="hicm3", source=Protocol.Source.CURATED,
                                        objective="", references="")
        rep = self._write_report([{
            "id": proto.id, "name": proto.name, "source": proto.source,
            "pubmed": None, "bioprotocol": None,
            "europepmc": {
                "objective": "To map chromatin contacts in mosquito embryos.",
                "source_ref": "10.21203/rs.3.pex-1840/v1",
                "article_title": "In situ Hi-C for mosquito embryos",
                "similarity": 1.0, "semantic_similarity": None,
                "accepted": True, "accept_reason": "token", "is_preprint": True,
            },
            "chosen": "europepmc",
        }])
        call_command("fetch_external_objectives", "--apply", "--only=curated",
                     "--from-report", rep, "--record-source")
        proto.refresh_from_db()
        self.assertEqual(proto.objective, "To map chromatin contacts in mosquito embryos.")
        self.assertIn("DOI:10.21203/rs.3.pex-1840/v1", proto.references)

    def test_from_report_epmc_reevaluates_gate(self):
        """重放不盲信报告 accepted：低 token + 无语义分 → 仍拒。"""
        proto = Protocol.objects.create(name="s3-ATAC", slug="s3atac",
                                        source=Protocol.Source.CURATED, objective="")
        rep = self._write_report([{
            "id": proto.id, "name": proto.name, "source": proto.source,
            "pubmed": None, "bioprotocol": None,
            "europepmc": {
                "objective": "ATAC profiling of mulberry fruit.",
                "source_ref": "10.1/mulberry", "article_title": "ATAC in mulberry",
                "similarity": 0.2, "semantic_similarity": None,
                "accepted": True, "accept_reason": "token",
            },
            "chosen": "europepmc",
        }])
        call_command("fetch_external_objectives", "--apply", "--only=curated",
                     "--from-report", rep)
        proto.refresh_from_db()
        self.assertEqual(proto.objective, "", "报告 accepted=True 也不得越过当前门槛")
