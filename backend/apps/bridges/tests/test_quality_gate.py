"""T2.1 质量闸门二维结果模型测试。

run_quality_gate 为纯函数、不触 DB；product 仅作占位（供冲突探测器扩展）。
edges 元素：(product_id, method_id, source_rc_id, prio_int)，prio: primary=0/secondary=1/conditional=2。
"""
import pytest

from apps.bridges.services.quality_gate import (
    run_quality_gate,
    EXEC_SUCCESS,
    QUALITY_ACCEPTABLE,
    QUALITY_REVIEW,
)

pytestmark = pytest.mark.django_db


class TestQualityGate:
    def test_empty_edges_is_success_review(self):
        """宁 miss：空边 → SUCCESS + REVIEW（非 FAILED）。"""
        from apps.commerce.models import Product
        p = Product(status='active')
        result, quality = run_quality_gate(p, [])
        assert result == EXEC_SUCCESS
        assert quality == QUALITY_REVIEW

    def test_nonempty_edges_is_success_acceptable(self):
        """有可靠派生边（primary）→ SUCCESS + ACCEPTABLE。"""
        from apps.commerce.models import Product
        p = Product(status='active')
        edges = [(1, 10, 100, 0)]  # prio 0 = primary
        result, quality = run_quality_gate(p, edges)
        assert result == EXEC_SUCCESS
        assert quality == QUALITY_ACCEPTABLE

    def test_all_low_confidence_is_review(self):
        """全部边仅 conditional（prio 2）→ 残缺 / 证据不足 → REVIEW。"""
        from apps.commerce.models import Product
        p = Product(status='active')
        edges = [(1, 11, 101, 2), (1, 12, 102, 2)]
        result, quality = run_quality_gate(p, edges)
        assert result == EXEC_SUCCESS
        assert quality == QUALITY_REVIEW

    def test_mixed_confidence_is_acceptable(self):
        """含 primary/secondary 的边 → ACCEPTABLE（非全低置信）。"""
        from apps.commerce.models import Product
        p = Product(status='active')
        edges = [(1, 11, 101, 2), (1, 12, 102, 1)]  # conditional + secondary
        result, quality = run_quality_gate(p, edges)
        assert result == EXEC_SUCCESS
        assert quality == QUALITY_ACCEPTABLE

    def test_gate_never_returns_failed(self):
        """本函数不触 DB、不抛系统错误路径；FAILED 由 process_product 映射。"""
        from apps.commerce.models import Product
        p = Product(status='active')
        for edges in ([], [(1, 1, 1, 0)], [(1, 1, 1, 2)]):
            result, _ = run_quality_gate(p, edges)
            assert result == EXEC_SUCCESS
