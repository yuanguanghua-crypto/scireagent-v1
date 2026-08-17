"""TDD RED → GREEN: 收口缺口 S_B 接通暴露的潜伏 bug — compute_axis_b 遇 list 值字段崩溃。

根因: 真实 Bioz 记录 techniques 是 list(bioz_client._parse_records: techniques=[] or []),
而 compute_axis_b 直接用 ' '.join([... lit.get('techniques') ...]) 拼字符串 →
TypeError: sequence item 1: expected str instance, list found。此前 S_B 恒为死轴,
该路径从未被真实数据执行, bug 潜伏; 重键接通后首次触发。

修复: 新增 _field_to_text 规整器(list→空格连接), compute_axis_b 经其取各字段文本。

本测试用 mock _extract_domains 控制 domain 匹配, 与 vocab 解耦, 断言:
1. list 值 techniques 不再抛 TypeError;
2. 仅与协议 Q 重叠的文献计入 lit_n。
"""
import re
from unittest.mock import patch

from django.test import TestCase

from apps.bridges.services import relevance as REL


class ComputeAxisBTddTest(TestCase):
    def test_field_to_text_flattens_list(self):
        self.assertEqual(REL._field_to_text(["a", "b"]), "a b")
        self.assertEqual(REL._field_to_text("x"), "x")
        self.assertEqual(REL._field_to_text(None), "")
        self.assertEqual(REL._field_to_text([]), "")

    @patch.object(REL, "_extract_domains")
    def test_no_typeerror_on_list_techniques_and_counts(self, mock_ext):
        def fake_ext(text):
            return set(re.findall(r"[a-z0-9\-]+", (text or "").lower()))

        mock_ext.side_effect = fake_ext

        class P:
            name = "rna protocol"
            objective = ""; principle = ""; materials = ""
            reagents = ""; expected_results = ""; references = ""

        lit_ok = {"article_title": "study", "techniques": ["rna", "seq"],
                  "long": "", "medium": "", "short": ""}
        lit_no = {"article_title": "other", "techniques": ["fish"],
                  "long": "", "medium": "", "short": ""}

        # 红灯: list 值 techniques 此前抛 TypeError; 修复后返回 (S_B, lit_n)
        sb, n = REL.compute_axis_b(None, P(), bioz_lits=[lit_ok, lit_no])
        self.assertEqual(n, 1)  # 仅 lit_ok 与 Q('rna') 重叠
        self.assertAlmostEqual(sb, min(1.0, 1 / REL.BIOZ_TYP_CAP))
