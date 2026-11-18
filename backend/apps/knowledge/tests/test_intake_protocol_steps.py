"""A-070 回归测试：知识录入的协议写入路径。

复现路径（修复前实测成立）：
  `POST /api/v1/knowledge-intake/` 带 `protocol_steps` ⇒ 后端把整段步骤文本写进
  `Protocol.objective`（"目标"字段），并**一行都不写** `protocol_step` 表。
  同时 `protocol_materials` 写进 `reagents`（"含浓度用量的试剂"），
  `protocols_created` 用 `len(protocols)` ⇒ 复用的协议也被算成新建。

本文件锁住五条不变式：
  1. 步骤只进 `protocol_step` 表，且 `objective` 里**不许**出现步骤文本
  2. `objective` 只由显式字段 `protocol_objective` 承载
  3. 材料落 `materials`，`reagents` 保持空（不拿材料冒充含浓度用量的试剂）
  4. created / reused 分开计数；重复提交不把步骤翻倍
  5. 表单收了但库里没字段的项（protocol_time/difficulty）如实回报，不硬塞
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.commerce.tests.factories import ProductFactory
from apps.knowledge.models import Protocol, ProtocolStep
from apps.knowledge.services.protocol_steps_parser import parse_plain_text_steps

INTAKE_URL = '/api/v1/knowledge-intake/'


def _payload(product, **over):
    data = {
        'product_id': product.pk,
        'research_goals': [],
        'applications': [],
        'methods': [],
        'protocols': ['CuAAC RNA Labeling Protocol'],
        'protocol_steps': '',
        'protocol_materials': '',
        'confidence': 'high',
    }
    data.update(over)
    return data


class IntakeProtocolWritePathTest(TestCase):
    """写入路径：步骤 / 目标 / 材料 / 计数"""

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=UserFactory(is_staff=True))
        self.product = ProductFactory(name='Intake Target', catalog_no='SC-INTAKE-1')

    def _post(self, **over):
        resp = self.client.post(INTAKE_URL, _payload(self.product, **over), format='json')
        self.assertIn(resp.status_code, (200, 201), resp.content)
        return resp.json()['data']

    # ---------- 1. 步骤进 step 表，不进 objective ----------

    def test_steps_go_to_protocol_step_not_objective(self):
        """核心缺陷：步骤曾整段写进 objective，且 step 表零行"""
        self._post(protocol_steps='准备反应液\n加入试剂\n孵育 30 分钟\n纯化产物')

        protocol = Protocol.objects.get(name='CuAAC RNA Labeling Protocol')
        self.assertEqual(protocol.objective, '',
                         '步骤文本漏进了 objective —— A-070 原缺陷复现')
        self.assertEqual(protocol.steps.count(), 4)

        rows = list(protocol.steps.order_by('step_no'))
        self.assertEqual([r.step_no for r in rows], [1, 2, 3, 4])
        self.assertEqual(rows[0].title, '准备反应液')
        self.assertEqual(rows[0].body, '准备反应液')

    def test_one_line_with_inline_numbers_is_a_single_step(self):
        """★ 只按行切：一行里写了 `1. 2. 3.` 也只算**一步**，不按编号拆。

        2026-11-18 组织方拍板「收窄成只按行切」——编号是作者的排版习惯，
        不是结构承诺，后端不该替作者猜步骤边界。
        """
        data = self._post(protocol_steps='1. Prepare RNA 2. Add reagents 3. Incubate')
        self.assertEqual(data['steps_created'], 1, '单行被按编号切成了多步')
        row = ProtocolStep.objects.get()
        self.assertEqual(row.body, '1. Prepare RNA 2. Add reagents 3. Incubate',
                         'body 应保持作者原文')

    def test_steps_created_count_is_real(self):
        data = self._post(protocol_steps='步骤一\n步骤二')
        self.assertEqual(data['steps_created'], 2)
        self.assertEqual(ProtocolStep.objects.count(), 2)

    def test_structured_array_input_accepted_end_to_end(self):
        """格式 A 的真实形态：前端直接送结构化数组，后端原样落库。"""
        data = self._post(protocol_steps=[
            {'title': '准备反应液', 'body': '按 1:1 混合', 'duration_seconds': 300},
            {'title': '孵育', 'body': '37°C 30 分钟'},
        ])
        self.assertEqual(data['steps_created'], 2)
        rows = list(ProtocolStep.objects.order_by('step_no'))
        self.assertEqual([r.title for r in rows], ['准备反应液', '孵育'])
        self.assertEqual(rows[0].duration_seconds, 300)
        self.assertEqual(rows[0].body, '按 1:1 混合')

    # ---------- 2. objective 只由显式字段承载 ----------

    def test_objective_comes_from_explicit_field(self):
        data = self._post(
            protocol_objective='把荧光染料共价接到 RNA 上',
            protocol_steps='步骤一\n步骤二',
        )
        protocol = Protocol.objects.get(name='CuAAC RNA Labeling Protocol')
        self.assertEqual(protocol.objective, '把荧光染料共价接到 RNA 上')
        self.assertEqual(protocol.steps.count(), 2)
        self.assertEqual(data['steps_created'], 2)

    # ---------- 3. 材料落 materials，不落 reagents ----------

    def test_materials_go_to_materials_not_reagents(self):
        self._post(protocol_materials='CuSO4, THPTA, ascorbate, dye')
        protocol = Protocol.objects.get(name='CuAAC RNA Labeling Protocol')
        self.assertEqual(protocol.materials, 'CuSO4, THPTA, ascorbate, dye')
        self.assertEqual(protocol.reagents, '',
                         '材料被塞进了 reagents（那是含浓度用量的试剂字段）')

    # ---------- 4. 计数如实 + 不重复追加 ----------

    def test_created_and_reused_counted_separately(self):
        first = self._post(protocol_steps='步骤一\n步骤二')
        self.assertEqual(first['protocols_created'], 1)
        self.assertEqual(first['protocols_reused'], 0)

        second = self._post(protocol_steps='步骤一\n步骤二')
        self.assertEqual(second['protocols_created'], 0,
                         '复用被算成新建 —— 原实现用 len(protocols) 的缺陷')
        self.assertEqual(second['protocols_reused'], 1)
        self.assertEqual(Protocol.objects.filter(name='CuAAC RNA Labeling Protocol').count(), 1)

    def test_resubmit_does_not_duplicate_steps(self):
        """重复提交同一表单不该把步骤翻倍，且要明说没覆盖"""
        self._post(protocol_steps='步骤一\n步骤二')
        data = self._post(protocol_steps='步骤一\n步骤二\n步骤三')

        protocol = Protocol.objects.get(name='CuAAC RNA Labeling Protocol')
        self.assertEqual(protocol.steps.count(), 2, '重复提交把步骤追加成了 5 条')
        self.assertEqual(data['steps_created'], 0)
        self.assertTrue(any('已有步骤' in w for w in data.get('warnings', [])),
                        f'未提示"已有步骤未覆盖"：{data}')

    # ---------- 5. 多协议：只挂第一份，其余明说 ----------

    def test_multi_protocol_steps_attached_to_first_only(self):
        data = self._post(
            protocols=['Protocol Alpha', 'Protocol Beta'],
            protocol_steps='步骤一\n步骤二',
        )
        alpha = Protocol.objects.get(name='Protocol Alpha')
        beta = Protocol.objects.get(name='Protocol Beta')
        self.assertEqual(alpha.steps.count(), 2)
        self.assertEqual(beta.steps.count(), 0,
                         '同一段步骤被复制给了每个协议 —— 凭空造出假步骤')
        self.assertTrue(any('只写入' in w for w in data.get('warnings', [])),
                        f'未提示只写入第一份：{data}')

    # ---------- 6. 参考来源合并且不丢 ----------

    def test_references_combined_from_doi_and_pmid(self):
        self._post(reference_doi='10.21769/BioProtoc.2841', reference_pmid='12345678')
        protocol = Protocol.objects.get(name='CuAAC RNA Labeling Protocol')
        self.assertIn('DOI: 10.21769/BioProtoc.2841', protocol.references)
        self.assertIn('PMID: 12345678', protocol.references)

    # ---------- 7. 无字段可落的输入如实回报 ----------

    def test_unmapped_fields_reported_not_stuffed(self):
        data = self._post(
            protocol_steps='步骤一',
            protocol_time='2 hours',
            protocol_difficulty='advanced',
        )
        self.assertEqual(sorted(data.get('unmapped_fields', [])),
                         ['protocol_difficulty', 'protocol_time'])
        protocol = Protocol.objects.get(name='CuAAC RNA Labeling Protocol')
        # 不许把 "2 hours" 之类硬塞进 objective / principle 冒充
        blob = ' '.join([protocol.objective, protocol.principle, protocol.materials,
                         protocol.reagents, protocol.expected_results])
        self.assertNotIn('2 hours', blob)
        self.assertNotIn('advanced', blob)

    def test_no_warnings_when_everything_lands(self):
        data = self._post(protocol_steps='步骤一', protocol_materials='dye')
        self.assertNotIn('warnings', data, f'本不该有告警：{data}')


class ParsePlainTextStepsTest(TestCase):
    """解析器本身：形状与边界（不依赖数据库，但放在同文件便于对照）"""

    def test_multiline_one_step_per_line(self):
        rows = parse_plain_text_steps('A\nB\nC')
        self.assertEqual([r['step_no'] for r in rows], [1, 2, 3])
        self.assertEqual([r['body'] for r in rows], ['A', 'B', 'C'])

    def test_inline_numbering_not_split(self):
        """一行内的 `1. 2. 3.` 不再当结构：只算一步"""
        rows = parse_plain_text_steps('1. A 2. B 3. C')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['body'], '1. A 2. B 3. C')
        self.assertEqual(rows[0]['title'], 'A 2. B 3. C', 'title 只去掉行首编号')

    def test_volume_like_text_is_not_split(self):
        """`1.5 mL buffer` 是体积不是编号，不许被切成两步"""
        rows = parse_plain_text_steps('Add 1.5 mL buffer to the tube')
        self.assertEqual(len(rows), 1)

    def test_leading_numbering_stripped_from_title_but_body_kept(self):
        """行首编号只从 title 去掉，body 保持作者原文"""
        for text in ('1. Prepare RNA', '1) Prepare RNA', '1、Prepare RNA',
                     'Step 1: Prepare RNA'):
            rows = parse_plain_text_steps(text)
            self.assertEqual(len(rows), 1, text)
            self.assertEqual(rows[0]['title'], 'Prepare RNA', text)
            self.assertEqual(rows[0]['body'], text, text)

    def test_colon_does_not_split_title_and_body(self):
        """★ 不按冒号拆标题：冒号可能出现在比例/时间描述里"""
        text = 'Prepare reaction: heat at 70C for 5 min'
        rows = parse_plain_text_steps(text)
        self.assertEqual(rows[0]['body'], text)
        self.assertEqual(rows[0]['title'], text[:60], 'title 应是正文前 60 字符')

    def test_without_colon_body_is_kept_whole(self):
        text = 'Incubate the sample at room temperature for thirty minutes then purify'
        rows = parse_plain_text_steps(text)
        self.assertEqual(rows[0]['body'], text)
        self.assertTrue(rows[0]['title'])
        self.assertLessEqual(len(rows[0]['title']), 60)

    def test_title_truncated_to_model_limit(self):
        rows = parse_plain_text_steps('x' * 400)
        self.assertLessEqual(len(rows[0]['title']), 255)

    def test_empty_and_non_string_inputs(self):
        for bad in ('', '   ', '\n\n', None, 123, [], {}):
            self.assertEqual(parse_plain_text_steps(bad), [], repr(bad))

    def test_blank_lines_skipped(self):
        rows = parse_plain_text_steps('A\n\n\nB\n   \nC')
        self.assertEqual(len(rows), 3)

    # ---------- 结构化数组（格式 A 的首选形态）----------

    def test_structured_list_of_strings_used_as_is(self):
        """数组就是最终结论：不再按标点切、不再猜标题/正文"""
        text = 'Prepare reaction: heat at 70C for 5 min'
        rows = parse_plain_text_steps([text, 'Purify product'])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['body'], text, '结构化输入被二次切分了')
        self.assertEqual(rows[1]['body'], 'Purify product')
        self.assertEqual([r['step_no'] for r in rows], [1, 2])

    def test_structured_list_of_dicts_passthrough(self):
        rows = parse_plain_text_steps([
            {'title': 'Prepare reaction', 'body': 'heat at 70C', 'duration_seconds': 300},
            {'title': 'Purify', 'body': 'column purification', 'warnings': '避光'},
        ])
        self.assertEqual([r['title'] for r in rows], ['Prepare reaction', 'Purify'])
        self.assertEqual(rows[0]['duration_seconds'], 300)
        self.assertEqual(rows[1]['warnings'], '避光')

    def test_structured_dict_without_title_falls_back_to_body(self):
        rows = parse_plain_text_steps([{'body': 'Incubate overnight at 37C'}])
        self.assertTrue(rows[0]['title'].startswith('Incubate overnight'))
        self.assertEqual(rows[0]['body'], 'Incubate overnight at 37C')

    def test_structured_list_skips_empty_and_garbage(self):
        rows = parse_plain_text_steps(['', '  ', {'title': '', 'body': ''}, None, 123, 'Real step'])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['body'], 'Real step')
        self.assertEqual(rows[0]['step_no'], 1)
