"""Word 导入的标签识别（A-132，2026-11-27）。

## 改前
`LABEL_PATTERN = ^([A-Za-z ]+?):\\s*(.+)$` —— 只认**半角冒号**、标签里不能有数字或点；
且 `label_map` 里**没有 category**。于是：
- 文档写 `SMILES：`（全角冒号）或 `CAS No.:` ⇒ 整行被跳过；
- 无论怎么写，分类都填不进去（QA 实测：12 个字段进去了，SMILES 与 Category 为空）。

## 本文件钉住"能认出来的写法"，同时钉住"认不出来就不猜"
（分类是一棵树，按文本猜 id 会错配 ⇒ 只抽文本，由用户在界面选）。
"""
from django.test import SimpleTestCase

from apps.commerce.services.word_parser import WordParserService


class WordLabelVariantsTest(SimpleTestCase):
    def setUp(self):
        self.p = WordParserService()

    def _key(self, line):
        got = self.p._match_label(line)
        return got['key'] if got else None

    def test_fullwidth_colon_is_accepted(self):
        """中文文档常见全角冒号 —— 改前整行被跳过（SMILES 缺失的直接原因之一）。"""
        assert self._key('SMILES：C1=NC=NC2=C1N=CN2') == 'smiles'

    def test_label_with_no_dot_is_accepted(self):
        assert self._key('CAS No.: 63-39-2') == 'cas'
        assert self._key('Catalog No.: SC8023-1') == 'catalog_number'

    def test_digits_in_label_tolerated(self):
        # 例如 "Storage 2-8C:" 这种带数字的标签也必须能被识别（至少不吞掉整行）
        assert self._key('Molecular Weight: 484.14') == 'molecular_weight'

    def test_category_is_extracted(self):
        """改前 label_map 里没有 category ⇒ 分类永远填不进去。"""
        for line in ('Category: Nucleotides', 'Product Category: 核苷酸',
                     'Categories: 核苷酸, 荧光染料'):
            got = self.p._match_label(line)
            assert got and got['key'] == 'category', line
            assert got['value'], line

    def test_unknown_label_returns_none(self):
        """认不出来就返回 None，**不许猜**（猜出来的分类 id 会错配）。"""
        assert self._key('Random Note: hello') is None
