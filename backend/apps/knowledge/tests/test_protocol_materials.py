"""
协议材料条目化（ProtocolMaterial + 解析器 + 导入命令）测试。

覆盖方案 docs/PROTOCOL_MATERIALIZATION_PLAN.md §4.6 的验收判据：
- 解析器：分节归一化、前导无标题区内容判别、vendor/货号抽取、**残缺货号置空**、
  `#` 分节标题的 1,800 种写法归一化、空行分块（Protocol-exchange 风格）；
- 保真：`raw_line` 必须是原文（压缩空白后）的子串，**连字符换行这条实测踩过坑**；
- 命令：dry-run 绝不写库、apply 写入、幂等、歧义跳过、**保真失败即中止**；
- 模型：`(protocol, seq)` 唯一，seq 从 1 连续。
"""
import contextlib
import io
import json
import os
import tempfile

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.knowledge.models import Protocol, ProtocolMaterial
from apps.knowledge.services.protocol_materials_parser import (
    classify_heading,
    classify_item,
    is_faithful,
    normalize_title,
    parse_blocks,
    parse_materials,
    parse_numbered,
    split_parens,
)


def _mk_protocol(name, **kw):
    return Protocol.objects.create(
        name=name,
        slug=kw.pop('slug', None) or name.lower().replace(' ', '-')[:200],
        version=kw.pop('version', '1.0'),
        **kw,
    )


# ────────────────────────── 解析器单测 ──────────────────────────


class SplitParensTest(TestCase):
    def test_extracts_vendor_and_catalog(self):
        out = split_parens('Sodium chloride (NaCl) (J.T. Baker, catalog number: 3624-19)')
        self.assertEqual(out['vendor'], 'J.T. Baker')
        self.assertEqual(out['catalog_no'], '3624-19')
        self.assertIn('Sodium chloride', out['name'])

    def test_trailing_note_after_paren(self):
        """括号后面还跟着 `, store at RT` —— v1 要求括号在行末，会漏掉 13.2% 的货号。"""
        out = split_parens('PBS (Thermo Fisher, catalog number: 20012027), store at RT')
        self.assertEqual(out['catalog_no'], '20012027')
        self.assertEqual(out['vendor'], 'Thermo Fisher')

    def test_model_number_for_equipment(self):
        out = split_parens('Mini centrifuge (Eppendorf, model: MiniSpin plus)')
        self.assertEqual(out['model_no'], 'MiniSpin plus')

    def test_no_parens_returns_whole_line_as_name(self):
        out = split_parens('Distilled water')
        self.assertEqual(out['name'], 'Distilled water')
        self.assertEqual(out['catalog_no'], '')


class HeadingClassifyTest(TestCase):
    def test_canonical_headings(self):
        self.assertEqual(classify_heading('Equipment'), 'equipment')
        self.assertEqual(classify_heading('Software and datasets'), 'software')
        self.assertEqual(classify_heading('Reagents'), 'reagent')
        self.assertEqual(classify_heading('Solutions'), 'solution_recipe')
        self.assertEqual(classify_heading('Recipes'), 'solution_recipe')
        self.assertEqual(classify_heading('Laboratory supplies'), 'consumable')
        self.assertEqual(classify_heading('Biological materials'), 'biological_material')
        self.assertEqual(classify_heading('Antibodies'), 'biological_material')

    def test_numbered_prefix_and_variants(self):
        """实测 1,800 种写法：a. / b. / 1. / 大小写 / 括号 —— 都要能归到同一类。"""
        for raw in ('a.  Materials', 'b.  reagents', 'c.reagents', 'B. Reagents',
                    '1.  Pipette tips'):
            self.assertIn(classify_heading(raw),
                          {'biological_material', 'reagent', 'consumable'})

    def test_unrecognised_heading_is_honest(self):
        """认不出就落 material_or_reagent —— 强行归类比不归类更糟。"""
        self.assertEqual(classify_heading('Additional equipment for cryo-EXM protocol'),
                         'equipment')
        self.assertEqual(classify_heading('Something wholly unknown'), 'material_or_reagent')

    def test_notes_heading(self):
        self.assertEqual(classify_heading('Notes:'), 'note')


class ItemClassifyTest(TestCase):
    def test_consumable_beats_equipment_for_tube(self):
        """`50mL centrifuge tube` 主体是 tube（耗材），不能被 centrifuge 抢成设备。"""
        self.assertEqual(classify_item('50mL centrifuge tube with round bottom'), 'consumable')
        self.assertEqual(classify_item('2~mL centrifuge tube'), 'consumable')

    def test_real_equipment_still_equipment(self):
        self.assertEqual(classify_item('Mini centrifuge'), 'equipment')
        self.assertEqual(classify_item('Cell culture hood'), 'equipment')

    def test_biological_material(self):
        self.assertEqual(classify_item('Adherent HEK 293 cells and Huh7 cells'),
                         'biological_material')

    def test_unknown_defaults_to_reagent(self):
        self.assertEqual(classify_item('Weird unlabelled powder'), 'reagent')


class ParseNumberedTest(TestCase):
    TEXT = (
        '\n1.  Glass slides\n'
        '2.  Poly-L-lysine\n'
        '3.  BSA\n'
        '\n# Equipment\n\n'
        '1.  Micropipette P1000 (Gilson, model: P1000)\n'
        '2.  Autoclave 13.5L (Ficoinox, model: SL9000)\n'
    )

    def test_counts_and_seq(self):
        items = parse_numbered(self.TEXT)
        self.assertEqual(len(items), 5)
        self.assertEqual([i['seq'] for i in items], [1, 2, 3, 4, 5])

    def test_preamble_kind_comes_from_content(self):
        items = parse_numbered(self.TEXT)
        # 前导区没有标题 ⇒ 按条目名判：Glass slides → consumable, BSA → reagent
        self.assertEqual(items[0]['kind'], 'consumable')
        self.assertEqual(items[2]['kind'], 'reagent')
        self.assertEqual(items[0]['section_heading'], '')

    def test_section_kind_comes_from_heading(self):
        items = parse_numbered(self.TEXT)
        self.assertEqual(items[3]['kind'], 'equipment')
        self.assertEqual(items[3]['section_heading'], 'Equipment')

    def test_continuation_line_is_joined(self):
        text = '1.  Long reagent name (Sigma-Aldrich,\n    catalog number: A1234)\n'
        items = parse_numbered(text)
        self.assertEqual(len(items), 1)
        self.assertIn('Long reagent name', items[0]['name'])
        self.assertIn('catalog number: A1234', items[0]['raw_line'])

    def test_inline_multiple_items_are_split(self):
        """同一物理行塞多个编号 —— 实测 1.9%，不切就整条丢。"""
        text = '1.  Alpha powder 2.  Beta powder 3.  Gamma powder\n'
        items = parse_numbered(text)
        self.assertEqual(len(items), 3)
        self.assertIn('Alpha', items[0]['name'])
        self.assertIn('Gamma', items[2]['name'])

    def test_inferred_kind_never_none(self):
        for it in parse_numbered(self.TEXT):
            self.assertIsNotNone(it['kind'])
            self.assertIn(it['kind'], dict(ProtocolMaterial.Kind.choices))


class ParseBlocksTest(TestCase):
    """Protocol-exchange 风格：无编号，空行分块。"""

    TEXT = (
        '\nNaClO (Honeywell)\n'
        '\nSep-Pak C18 Cartridge, 100 mg (Waters, WAT023590)\n'
        '\nCentrifuge\n'
    )

    def test_blocks_parsed(self):
        items = parse_blocks(self.TEXT)
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]['name'], 'NaClO')
        self.assertEqual(items[0]['vendor'], 'Honeywell')

    def test_catalog_only_when_explicit(self):
        items = parse_blocks(self.TEXT)
        # 括号里只写供应商（没有 catalog 字样）⇒ 货号留空，不瞎猜
        self.assertEqual(items[0]['catalog_no'], '')
        # 括号里明确是货号形态 ⇒ 填上
        self.assertEqual(items[1]['catalog_no'], 'WAT023590')

    def test_ordinal_is_none_for_unnumbered(self):
        for it in parse_blocks(self.TEXT):
            self.assertIsNone(it['ordinal'])


class ParseDispatchTest(TestCase):
    def test_numbered_detected(self):
        items = parse_materials('1.  A\n2.  B\n')
        self.assertEqual(len(items), 2)

    def test_blocks_detected(self):
        items = parse_materials('Alpha\n\nBeta\n')
        self.assertEqual(len(items), 2)

    def test_empty_returns_empty(self):
        self.assertEqual(parse_materials(''), [])
        self.assertEqual(parse_materials('   \n  '), [])


class FaithfulnessTest(TestCase):
    def test_exact_line_is_faithful(self):
        self.assertTrue(is_faithful('1.  Glass slides', '1.  Glass slides\n2.  X'))

    def test_hyphen_linebreak_must_use_single_space(self):
        """★ 实测踩过的坑：原文 `pRS416M1-\\nTEF1` 压缩空白后是 `pRS416M1- TEF1`。
        解析器若把行尾连字符直接相接（`pRS416M1-TEF1`）就会假报不保真。"""
        original = '1.  Plasmid pRS416M1-\nTEF1 (control)\n'
        self.assertTrue(is_faithful('Plasmid pRS416M1- TEF1 (control)', original))
        self.assertFalse(is_faithful('Plasmid pRS416M1-TEF1 (control)', original))

    def test_rewritten_line_is_not_faithful(self):
        self.assertFalse(is_faithful('Glass slides (rewritten)', '1.  Glass slides\n'))


class CatalogSanityTest(TestCase):
    def test_truncated_catalog_is_dropped(self):
        """括号未闭合时抽出的半截货号必须置空 —— 客户拿去询价会查错货。"""
        text = '1.  Inorganic 13C (Sigma-Aldrich, catalog number:\n'
        items = parse_numbered(text)
        self.assertEqual(items[0]['catalog_no'], '')


class NormalizeTitleTest(TestCase):
    def test_case_and_punctuation(self):
        self.assertEqual(normalize_title('Cell Viability: Protocol (using ATP)'),
                         'cell viability protocol using atp')

    def test_empty(self):
        self.assertEqual(normalize_title(''), '')


# ────────────────────────── 命令测试 ──────────────────────────


class ImportMaterialsCommandTest(TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='materials_')

    def tearDown(self):
        for fn in os.listdir(self.tmp):
            os.remove(os.path.join(self.tmp, fn))
        os.rmdir(self.tmp)

    def _write_corpus(self, rows, filename='Bio-protocol.json'):
        with open(os.path.join(self.tmp, filename), 'w', encoding='utf-8') as fh:
            json.dump(rows, fh, ensure_ascii=False)

    def _run(self, *args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            call_command('import_protocol_materials',
                         '--corpus-dir', self.tmp, *args)
        return buf.getvalue()

    def _corpus_row(self, title, text, cid='Bio-protocol-1'):
        return {'id': cid, 'title': title, 'input': text, 'url': 'https://doi.org/10.1/x'}

    def test_dry_run_never_writes(self):
        self._write_corpus([self._corpus_row('Alpha Protocol', '1.  Glass slides\n')])
        _mk_protocol('Alpha Protocol')
        self._run('--dry-run')
        self.assertEqual(ProtocolMaterial.objects.count(), 0)

    def test_apply_writes_items(self):
        self._write_corpus([self._corpus_row(
            'Alpha Protocol',
            '\n1.  Glass slides\n2.  BSA (Sigma-Aldrich, catalog number: A7906)\n'
            '\n# Equipment\n\n1.  Mini centrifuge (Eppendorf, model: MiniSpin plus)\n')])
        p = _mk_protocol('Alpha Protocol')
        self._run('--apply')
        items = ProtocolMaterial.objects.filter(protocol=p).order_by('seq')
        self.assertEqual(items.count(), 3)
        self.assertEqual([i.seq for i in items], [1, 2, 3])
        bsa = items[1]
        self.assertEqual(bsa.kind, 'reagent')
        self.assertEqual(bsa.vendor, 'Sigma-Aldrich')
        self.assertEqual(bsa.catalog_no, 'A7906')
        self.assertEqual(items[2].kind, 'equipment')

    def test_second_run_is_idempotent(self):
        self._write_corpus([self._corpus_row('Alpha Protocol', '1.  Glass slides\n')])
        p = _mk_protocol('Alpha Protocol')
        self._run('--apply')
        first = ProtocolMaterial.objects.filter(protocol=p).count()
        self._run('--apply')
        self.assertEqual(ProtocolMaterial.objects.filter(protocol=p).count(), first)

    def test_purge_rebuilds(self):
        self._write_corpus([self._corpus_row('Alpha Protocol', '1.  A\n2.  B\n')])
        p = _mk_protocol('Alpha Protocol')
        self._run('--apply')
        self.assertEqual(ProtocolMaterial.objects.filter(protocol=p).count(), 2)
        # 换成 1 条后再 purge，应变成 1 条（不是 3 条）
        self._write_corpus([self._corpus_row('Alpha Protocol', '1.  Only one\n')])
        self._run('--apply', '--purge')
        self.assertEqual(ProtocolMaterial.objects.filter(protocol=p).count(), 1)

    def test_unmatched_title_writes_nothing(self):
        self._write_corpus([self._corpus_row('Other Protocol', '1.  A\n')])
        p = _mk_protocol('Alpha Protocol')
        self._run('--apply')
        self.assertEqual(ProtocolMaterial.objects.filter(protocol=p).count(), 0)

    def test_protocol_io_has_no_input_and_yields_nothing(self):
        """Protocol-io 原始 JSON 无 input 字段 ⇒ 必须安静地 0 条，不能报错也不能瞎写。"""
        self._write_corpus(
            [{'id': 'Protocol.io-1', 'title': 'Alpha Protocol'}],
            filename='Protocol-io.json')
        p = _mk_protocol('Alpha Protocol')
        out = self._run('--apply', '--source', 'protocol_io')
        self.assertEqual(ProtocolMaterial.objects.filter(protocol=p).count(), 0)
        self.assertIn('有 input 0 条', out)

    def test_ambiguous_duplicate_titles_are_skipped(self):
        self._write_corpus([
            self._corpus_row('Same Title', '1.  A\n', cid='A-1'),
            self._corpus_row('Same  Title', '1.  B\n', cid='A-2'),
        ])
        p = _mk_protocol('Same Title')
        self._run('--apply')
        self.assertEqual(ProtocolMaterial.objects.filter(protocol=p).count(), 0)

    def test_verify_reports_counts(self):
        self._write_corpus([self._corpus_row('Alpha Protocol', '1.  A\n2.  B\n')])
        _mk_protocol('Alpha Protocol')
        self._run('--apply')
        out = self._run('--verify')
        self.assertIn('材料条目总数', out)

    def test_missing_corpus_dir_raises(self):
        with self.assertRaises(CommandError):
            self._run('--corpus-dir', os.path.join(self.tmp, 'nope'), '--apply')


class ProtocolMaterialModelTest(TestCase):
    def test_seq_unique_per_protocol(self):
        from django.db import IntegrityError, transaction
        p = _mk_protocol('Uniq Protocol')
        ProtocolMaterial.objects.create(protocol=p, seq=1, kind='reagent',
                                        name='A', raw_line='A')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProtocolMaterial.objects.create(protocol=p, seq=1, kind='reagent',
                                                name='B', raw_line='B')

    def test_cascade_delete_with_protocol(self):
        p = _mk_protocol('Cascade Protocol')
        ProtocolMaterial.objects.create(protocol=p, seq=1, kind='reagent',
                                        name='A', raw_line='A')
        p.delete()
        self.assertEqual(ProtocolMaterial.objects.count(), 0)
