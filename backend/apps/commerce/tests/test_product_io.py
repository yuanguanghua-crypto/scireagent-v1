"""A-028：产品列表 CSV 导出 / 导入。

## 范围（用户拍板）
- 格式 **CSV**（零新依赖；`openpyxl` 不在 requirements.txt）
- **只导/导产品主表**（SKU 是一对多，塞进单表会让字段重复、也无法定位改哪个 SKU）
- 导入**只更新已有**（按 `catalog_no` 匹配），新建走页面
- 导出**沿用列表页筛选**（内部复用 `ProductViewSet.get_queryset()` + `filter_queryset()`）

## 本文件钉住
① 导出：表头齐、带 BOM（Excel 中文不乱码）、筛选生效、非 admin 403
② 导入 dry-run：**不写库**
③ 导入 apply：白名单字段真的写进去了
④ 导入非法目录号 → 逐行报错
⑤ **status/archived/slug 不可通过导入改**（明确报错，不静默忽略）
⑥ **任一行有错 ⇒ 整体不写**（不做部分成功）
⑦ 中文列名与英文 key 都能识别
"""
import io

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.commerce.models import Product

User = get_user_model()
EXPORT_URL = '/api/v1/products/export/'
IMPORT_URL = '/api/v1/products/import/'

HEADER = '目录号,产品名称,CAS号,SMILES,InChI,分子式,分子量,纯度,浓度,储存条件,运输条件,货期,保质期,仅限研究用途,分类（只读）'


def _admin():
    return User.objects.create_user(
        username='io_admin', email='io_admin@x.com', password='x',
        role='admin', is_staff=True)


def _product(**over):
    defaults = dict(
        name='IO Reagent', slug='io-reagent', catalog_no='SC-IO-1',
        cas='63-39-2', formula='C9H15N2O15P3', molecular_weight=484.14,
        purity='hplc', concentration='100mM', status='active',
    )
    defaults.update(over)
    return Product.objects.create(**defaults)


def _csv(rows, header=HEADER):
    return (header + '\n' + '\n'.join(rows) + '\n').encode('utf-8')


class ProductExportTest(TestCase):
    def setUp(self):
        self.admin = _admin()
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        _product(catalog_no='SC-IO-1', name='Alpha')
        _product(catalog_no='SC-IO-2', name='Beta', slug='beta')

    def test_export_returns_csv_with_header(self):
        r = self.client.get(EXPORT_URL)
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertIn('text/csv', r['Content-Type'])
        self.assertIn('attachment', r['Content-Disposition'])
        body = r.content.decode('utf-8-sig')
        first = body.splitlines()[0]
        self.assertIn('目录号', first)
        self.assertIn('产品名称', first)

    def test_export_has_bom_for_excel(self):
        """带 BOM 才能让 Excel 双击打开时中文不乱码。"""
        r = self.client.get(EXPORT_URL)
        self.assertTrue(r.content.startswith('\ufeff'.encode('utf-8')))

    def test_export_contains_all_products(self):
        body = self.client.get(EXPORT_URL).content.decode('utf-8-sig')
        self.assertIn('SC-IO-1', body)
        self.assertIn('SC-IO-2', body)

    def test_export_respects_search_filter(self):
        """★ 导出的必须是「屏幕上看到的那批」—— 筛选要生效。"""
        body = self.client.get(EXPORT_URL, {'search': 'Alpha'}).content.decode('utf-8-sig')
        self.assertIn('SC-IO-1', body)
        self.assertNotIn('SC-IO-2', body)

    def test_export_forbidden_for_non_admin(self):
        c = APIClient()
        c.force_authenticate(User.objects.create_user(
            username='io_res', email='r@x.com', password='x', role='researcher'))
        self.assertIn(c.get(EXPORT_URL).status_code, (401, 403))


class ProductImportTest(TestCase):
    def setUp(self):
        self.admin = _admin()
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.p = _product(catalog_no='SC-IO-1', name='Old Name')

    def _post(self, content, apply=False):
        """`apply` 必须走 **query string**（`?apply=1`）——
        作为 post 的 kwargs 会被当成 DRF 的额外参数，后端读不到。"""
        f = io.BytesIO(content)
        f.name = 'products.csv'
        url = IMPORT_URL + ('?apply=1' if apply else '')
        return self.client.post(url, {'file': f}, format='multipart')

    def _row(self, catalog_no='SC-IO-1', name='New Name', cas='63-39-2',
             **over):
        vals = {
            '目录号': catalog_no, '产品名称': name, 'CAS号': cas,
            'SMILES': '', 'InChI': '', '分子式': '', '分子量': '',
            '纯度': '', '浓度': '', '储存条件': '', '运输条件': '',
            '货期': '', '保质期': '', '仅限研究用途': 'true', '分类（只读）': '',
        }
        vals.update({k: v for k, v in over.items()})
        return ','.join(str(vals[label]) for label in HEADER.split(','))

    # ── ② dry-run 不写库 ──────────────────────────────────────
    def test_dry_run_does_not_write(self):
        r = self._post(_csv([self._row(name='Changed')]))
        self.assertEqual(r.status_code, 200, r.content[:300])
        d = r.json()['data']
        self.assertEqual(d['will_update'], 1)
        self.assertFalse(d['applied'])
        self.p.refresh_from_db()
        self.assertEqual(self.p.name, 'Old Name', 'dry-run 绝不能写库')

    # ── ③ apply 真的写 ───────────────────────────────────────
    def test_apply_updates_whitelisted_field(self):
        r = self._post(_csv([self._row(name='Changed')]), apply=True)
        d = r.json()['data']
        self.assertTrue(d['applied'])
        self.p.refresh_from_db()
        self.assertEqual(self.p.name, 'Changed')

    def test_unchanged_row_counts_as_unchanged(self):
        r = self._post(_csv([self._row(name='Old Name')]), apply=True)
        d = r.json()['data']
        self.assertEqual(d['unchanged'], 1)
        self.assertEqual(d['will_update'], 0)

    # ── ④ 非法目录号 ────────────────────────────────────────
    def test_unknown_catalog_no_reports_error(self):
        r = self._post(_csv([self._row(catalog_no='SC-NOT-EXIST')]))
        d = r.json()['data']
        self.assertEqual(len(d['errors']), 1)
        self.assertIn('不存在', d['errors'][0]['error'])
        self.assertEqual(d['errors'][0]['line'], 2)

    # ── ⑤ 禁止字段 ──────────────────────────────────────────
    def test_status_column_rejected(self):
        header = HEADER + ',status'
        row = self._row() + ',archived'
        r = self._post(_csv([row], header=header))
        d = r.json()['data']
        self.assertTrue(any(e['field'] == 'status' for e in d['errors']),
                        f'status 应被拒，实得 {d["errors"]}')
        self.p.refresh_from_db()
        self.assertEqual(self.p.status, 'active')

    # ── ⑥ 任一行错 ⇒ 整体不写 ───────────────────────────────
    def test_any_error_blocks_all_writes(self):
        rows = [self._row(catalog_no='SC-IO-1', name='ShouldNotApply'),
                self._row(catalog_no='SC-NOT-EXIST')]
        r = self._post(_csv(rows), apply=True)
        d = r.json()['data']
        self.assertFalse(d['applied'], '有错行时不得写入任何一行')
        self.p.refresh_from_db()
        self.assertEqual(self.p.name, 'Old Name',
                         '★ 合法行也不能写 —— 部分成功最难排查')

    # ── ⑦ 中英列名都认 ──────────────────────────────────────
    def test_english_header_also_accepted(self):
        header = 'catalog_no,name,cas'
        r = self._post(_csv(['SC-IO-1,English Name,63-39-2'], header=header), apply=True)
        d = r.json()['data']
        self.assertTrue(d['applied'], d)
        self.p.refresh_from_db()
        self.assertEqual(self.p.name, 'English Name')

    def test_missing_key_column_rejected(self):
        r = self._post(_csv(['x,y'], header='name,cas'))
        self.assertEqual(r.status_code, 400, r.content[:300])
        self.assertEqual(r.json()['meta']['error']['code'], 'MISSING_KEY')

    def test_molecular_weight_non_numeric_reports_error(self):
        r = self._post(_csv([self._row(分子量='abc')]))
        d = r.json()['data']
        self.assertTrue(any(e['field'] == 'molecular_weight' for e in d['errors']),
                        d['errors'])
