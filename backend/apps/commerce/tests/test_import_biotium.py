"""Biotium 导入命令（import_biotium）DB 路径测试。

用小型 fixture 验证：
  - 产品以 status=draft 落库（不激活）
  - 140 黄金集结构图（PNG base64）写入 structure_image 并加 data: URL 前缀
  - mw/formula 映射正确（字符串 mw → float）
  - Ex/Em 光谱写入 overview 文本
  - 幂等：二次运行不重复创建
"""
import json
import tempfile

from django.core.management import call_command
from django.test import TestCase

from apps.commerce.models import Product


FIXTURE = [
    {
        "catalog_no": "BIOT-TEST-1", "product_name": "Test Fluorescent Dye",
        "vendor": "biotium", "ex_em": "490/525 纳米", "product_type": "discrete_dye",
        "extras": {
            "mw": "466.20", "formula": "C20H18N2O2", "cid": 65182,
            "structure_image_b64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC",
        },
    },
    {
        "catalog_no": "BIOT-TEST-2", "product_name": "Test Rabbit Antibody",
        "vendor": "biotium", "product_type": "biologic",
        "extras": {"cas_validated": "False", "cas_warn": "cas_missing"},
    },
]


class ImportBiotiumTest(TestCase):
    def _write_fixture(self):
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl",
                                          encoding="utf-8", delete=False)
        for r in FIXTURE:
            tmp.write(json.dumps(r, ensure_ascii=False) + "\n")
        tmp.close()
        return tmp.name

    def test_import_creates_draft_with_structure(self):
        path = self._write_fixture()
        call_command("import_biotium", file=path, dry_run=False)

        self.assertEqual(Product.objects.count(), 2)

        p1 = Product.objects.get(catalog_no="BIOT-TEST-1")
        self.assertEqual(p1.status, "draft")
        self.assertEqual(p1.molecular_weight, 466.20)
        self.assertEqual(p1.formula, "C20H18N2O2")
        self.assertTrue(p1.structure_image.startswith("data:image/png;base64,"))
        self.assertIn("Ex/Em: 490/525 纳米", p1.overview)

        p2 = Product.objects.get(catalog_no="BIOT-TEST-2")
        self.assertEqual(p2.status, "draft")
        self.assertEqual(p2.structure_image, "")
        self.assertNotIn("Ex/Em", p2.overview)

    def test_import_idempotent(self):
        path = self._write_fixture()
        call_command("import_biotium", file=path, dry_run=False)
        call_command("import_biotium", file=path, dry_run=False)
        # 不重复创建
        self.assertEqual(Product.objects.count(), 2)

    def test_dry_run_no_writes(self):
        path = self._write_fixture()
        call_command("import_biotium", file=path, dry_run=True)
        self.assertEqual(Product.objects.count(), 0)
