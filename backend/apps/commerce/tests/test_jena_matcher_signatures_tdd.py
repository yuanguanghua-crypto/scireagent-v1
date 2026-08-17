"""TDD RED → GREEN: #473-B1 / #470 修复 jena 匹配输出暴露化学一致性信号。

根因（已钉死）：jena_matcher._match_jena_no_cache 内部用 signatures_conflict 做糖型/
碱基一致性约束（拒收跨碱基错配），但**命中/未命中的 source dict 都不携带该信号**，
导致前端/auto_links 无法透明展示"为何匹配"或"为何被拒"，共轭物误报( #470 )无归因。

修复：每个 source（命中与未命中）都附带 signatures_conflict(bool)：命中=候选与目标签名
是否冲突；未命中且因冲突被拒= True（暴露拒因）；未命中且无候选可评= None（不适用）。
"""
import json
import os
import shutil
import tempfile
from unittest.mock import patch

from django.test import TestCase

from apps.commerce.services import jena_matcher


FIXTURE = [
    {
        "jena_catalog_no": "NU-1001",
        "product_name": "dATP - Solution",
        "systematic_name": "2'-Deoxyadenosine-5'-triphosphate, Sodium salt",
        "cas_number": "1927-31-7",
        "category_path": "Nucleotides & Nucleosides|dNTPs",
    },
    {
        "jena_catalog_no": "NU-1213",
        "product_name": "6-Thio-dGTP",
        "category_path": "Nucleotides & Nucleosides|Modified Nucleotides",
    },
]


def _build_index(records, filename="jena_sign_tdd.jsonl"):
    tmpdir = tempfile.mkdtemp()
    path = os.path.join(tmpdir, filename)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    from apps.commerce.services.jena_index import JenaIndex
    idx = JenaIndex(data_dir=tmpdir, jsonl_filename=filename)
    idx.build()
    return idx, tmpdir


class SignaturesConflictExposedTest(TestCase):
    def setUp(self):
        self.index, self.tmpdir = _build_index(FIXTURE)
        self._patch = patch.object(jena_matcher, "_get_index", return_value=self.index)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_matched_source_exposes_signatures_conflict_false(self):
        """CAS 精确命中同化合物 → source 须带 signatures_conflict 且为 False。"""
        r = jena_matcher.match_jena("1927-31-7", namespace="cas")
        self.assertTrue(r["matched"])
        src = r["sources"][0]
        self.assertIn("signatures_conflict", src)
        self.assertIsInstance(src["signatures_conflict"], bool)
        self.assertFalse(src["signatures_conflict"])

    def test_rejected_conjugate_exposes_signatures_conflict_true(self):
        """请求 dTTP(碱基T) 经 synonym 命中 6-Thio-dGTP(碱基G) → 因糖型/碱基冲突被拒；
        source 须带 signatures_conflict=True 暴露拒因（#470 透明标注前提）。"""
        r = jena_matcher.match_jena(
            "2-Thio-dTTP", namespace="name",
            synonyms=["6-Thio-dG"], request_name="2-Thio-dTTP",
        )
        self.assertFalse(r["matched"])
        rej = next(s for s in r["sources"] if not s["matched"])
        self.assertIn("signatures_conflict", rej)
        self.assertTrue(rej["signatures_conflict"])
