"""
TDD for recompute_relevance_basis 管理命令。

范围极窄：仅重算 ProductProtocol.relevance_basis 这一个派生字段，复用
apps.bridges.services.relevance.fuse_relevance 推导（禁止复制分支逻辑）。

契约（见 apps/bridges/management/commands/recompute_relevance_basis.py）：
- 默认 dry-run：绝不写库。
- --apply：bulk_update 仅变化行、仅更新 relevance_basis，分批 --batch-size（默认 1000）。
- 幂等：--apply 跑完再跑，变化数 = 0。
- 不触碰 relevance_score / tier / link_source / score_a / score_b / score_c。
- --limit N：只处理前 N 行（按 id）。
- --out <jsonl>：每条变更写一行审计 {"id","product_id","protocol_id","old","new"}。
"""
import io
import json

from django.core.management import call_command
from django.test import TestCase

from apps.bridges.models import ProductProtocol
from apps.bridges.tests.factories import ProductProtocolFactory


def _stale_pp(**kwargs):
    """构造一行 ProductProtocol，显式给定分数与（可能陈旧的）relevance_basis。"""
    defaults = dict(
        score_a=0.0, score_b=0.0, score_c=0.0,
        relevance_score=0.0,
        relevance_basis='',
        tier='weak',
        link_source='inherited',
    )
    defaults.update(kwargs)
    return ProductProtocolFactory(**defaults)


class RecomputeRelevanceBasisDryRunTest(TestCase):
    """默认 dry-run 绝不写库。"""

    def test_dry_run_does_not_write(self):
        # score_b>0 且 score_a>0 → 应为 combined，但库里陈旧为 vendor_only
        pp = _stale_pp(score_a=0.5, score_b=0.3, relevance_basis='vendor_only')
        before = ProductProtocol.objects.get(id=pp.id).relevance_basis
        self.assertEqual(before, 'vendor_only')

        out = io.StringIO()
        call_command('recompute_relevance_basis', stdout=out)

        after = ProductProtocol.objects.get(id=pp.id).relevance_basis
        # 关键断言：dry-run 不落库
        self.assertEqual(after, 'vendor_only', "dry-run 不应修改任何数据")
        # 输出应报告存在失配
        self.assertIn('失配', out.getvalue())

    def test_dry_run_report_counts(self):
        _stale_pp(score_a=0.5, score_b=0.3, relevance_basis='vendor_only')  # -> combined
        _stale_pp(score_a=0.0, score_b=0.3, relevance_basis='vendor_only')  # -> bioz_aligned
        _stale_pp(score_a=0.6, score_b=0.0, relevance_basis='embedding_break')  # -> vendor_only
        # 一条本就正确
        _stale_pp(score_a=0.5, score_b=0.3, relevance_basis='combined')

        out = io.StringIO()
        call_command('recompute_relevance_basis', stdout=out)
        text = out.getvalue()
        self.assertIn('扫描总行数', text)
        self.assertIn('失配', text)
        self.assertIn('终态分布', text)
        # 3 条失配（前 3 条）——必须精确断言计数行，断言裸字符 '3' 不足为证
        self.assertIn('失配（需修正）行数：3', text)


class RecomputeRelevanceBasisApplyTest(TestCase):
    """--apply 修正陈旧 basis。"""

    def test_apply_fixes_vendor_only_to_combined(self):
        # score_a>0 且 score_b>0 → combined
        pp = _stale_pp(score_a=0.5, score_b=0.3, relevance_basis='vendor_only')
        call_command('recompute_relevance_basis', '--apply')
        pp.refresh_from_db()
        self.assertEqual(pp.relevance_basis, 'combined')

    def test_apply_fixes_vendor_only_to_bioz_aligned(self):
        # score_a=0 且 score_b>0 → bioz_aligned
        pp = _stale_pp(score_a=0.0, score_b=0.3, relevance_basis='vendor_only')
        call_command('recompute_relevance_basis', '--apply')
        pp.refresh_from_db()
        self.assertEqual(pp.relevance_basis, 'bioz_aligned')

    def test_apply_fixes_embedding_break_to_vendor_only(self):
        pp = _stale_pp(score_a=0.6, score_b=0.0, relevance_basis='embedding_break')
        call_command('recompute_relevance_basis', '--apply')
        pp.refresh_from_db()
        self.assertEqual(pp.relevance_basis, 'vendor_only')

    def test_apply_idempotent(self):
        _stale_pp(score_a=0.5, score_b=0.3, relevance_basis='vendor_only')
        _stale_pp(score_a=0.0, score_b=0.3, relevance_basis='vendor_only')
        _stale_pp(score_a=0.6, score_b=0.0, relevance_basis='embedding_break')

        call_command('recompute_relevance_basis', '--apply', stdout=io.StringIO())
        out2 = io.StringIO()
        call_command('recompute_relevance_basis', '--apply', stdout=out2)
        # 第二次运行：变化数必须为 0（精确断言计数行，不用裸字符 '0'）
        self.assertIn('失配（需修正）行数：0', out2.getvalue())

    def test_apply_does_not_touch_other_fields(self):
        # 哨兵值：apply 绝不得改动这些字段（score_a/b/c/relevance_score/tier/link_source）
        pp = _stale_pp(
            score_a=0.5, score_b=0.3, score_c=0.111,
            relevance_score=0.987,
            tier='document',
            link_source='auto',
            relevance_basis='vendor_only',
        )
        before_updated = ProductProtocol.objects.get(id=pp.id).updated_at
        before_computed = ProductProtocol.objects.get(id=pp.id).computed_at
        call_command('recompute_relevance_basis', '--apply')
        pp.refresh_from_db()
        # basis 被修正
        self.assertEqual(pp.relevance_basis, 'combined')
        # 其余字段一律不变
        self.assertAlmostEqual(pp.relevance_score, 0.987)
        self.assertEqual(pp.tier, 'document')
        self.assertEqual(pp.link_source, 'auto')
        self.assertAlmostEqual(pp.score_a, 0.5)
        self.assertAlmostEqual(pp.score_b, 0.3)
        self.assertAlmostEqual(pp.score_c, 0.111)
        # 契约（有意为之，非疏漏）：bulk_update(fields=['relevance_basis']) 不刷 auto_now 时间戳。
        # 语义解释：本次只"修复标签"，三轴分数未被重算，故 computed_at（计算时间）保持原值更准确；
        # 且全仓无任何业务代码读取 ProductProtocol 的 updated_at/computed_at（已 grep 核实），
        # 故不刷新不产生功能影响。若未来引入依赖这两个时间戳的增量同步，须改本测试并同步改命令。
        self.assertEqual(pp.updated_at, before_updated)
        self.assertEqual(pp.computed_at, before_computed)

    def test_already_correct_rows_not_counted(self):
        # 本就正确的行不应计入变更
        correct = _stale_pp(score_a=0.5, score_b=0.3, relevance_basis='combined')
        out = io.StringIO()
        call_command('recompute_relevance_basis', '--apply', stdout=out)
        correct.refresh_from_db()
        self.assertEqual(correct.relevance_basis, 'combined')
        # 0 失配（仅此一条且本就正确）
        self.assertIn('失配（需修正）行数：0', out.getvalue())


class RecomputeRelevanceBasisLimitTest(TestCase):
    """--limit 只处理前 N 行。"""

    def test_limit_applies(self):
        # 3 条陈旧（score_a>0 & score_b>0 -> combined，但陈旧为 vendor_only）
        pps = [
            _stale_pp(score_a=0.5, score_b=0.3, relevance_basis='vendor_only'),
            _stale_pp(score_a=0.5, score_b=0.3, relevance_basis='vendor_only'),
            _stale_pp(score_a=0.5, score_b=0.3, relevance_basis='vendor_only'),
        ]
        call_command('recompute_relevance_basis', '--apply', '--limit', '1')
        # 仅第 1 条（按 id 最小）被修正
        pps[0].refresh_from_db()
        pps[1].refresh_from_db()
        pps[2].refresh_from_db()
        self.assertEqual(pps[0].relevance_basis, 'combined')
        self.assertEqual(pps[1].relevance_basis, 'vendor_only')  # 未处理
        self.assertEqual(pps[2].relevance_basis, 'vendor_only')  # 未处理


class RecomputeRelevanceBasisAuditTest(TestCase):
    """--out 写 JSONL 审计。"""

    def test_audit_jsonl_written(self):
        import tempfile
        import os
        _stale_pp(score_a=0.5, score_b=0.3, relevance_basis='vendor_only')  # -> combined
        _stale_pp(score_a=0.0, score_b=0.3, relevance_basis='vendor_only')  # -> bioz_aligned

        with tempfile.TemporaryDirectory() as tmp:
            audit = os.path.join(tmp, 'audit.jsonl')
            call_command('recompute_relevance_basis', '--apply', '--out', audit)
            with open(audit, encoding='utf-8') as f:
                lines = [ln for ln in f.read().splitlines() if ln.strip()]
            self.assertEqual(len(lines), 2)
            rec = json.loads(lines[0])
            # 键顺序固定
            self.assertEqual(list(rec.keys()),
                             ['id', 'product_id', 'protocol_id', 'old', 'new'])
            self.assertIn(rec['new'], ('combined', 'bioz_aligned'))
