"""process_product 系统错误 → FAILED 路径测试（MUST-3 / Q2 / T2.1）。

验证：rebuild 抛系统异常时，process_product 返回 FAILED、内层 atomic 回滚派生边、
产品仍保持 ACTIVE（Q2：管线故障可恢复，不要求成功产出边）。

注：MUST-3 文本写"系统错误→rollback（Product 保持 DRAFT）"，但与已落地的
serializer 行为（先 save ACTIVE 再调管线、异常保持 ACTIVE）及既有 R1 测试冲突。
本测试以"产品保持 ACTIVE"为准（Q2，as-built），MUST-3 是否改为 DRAFT 待负责人拍板。
"""
import pytest
from unittest.mock import patch

from apps.bridges.tests.factories import ProductFactory
from apps.bridges.models import ProductMethodRelation
from apps.bridges.services.association_service import AssociationService

pytestmark = pytest.mark.django_db


class TestProcessProductFailure:
    def test_system_error_yields_failed_and_keeps_active(self):
        """rebuild 抛 RuntimeError → FAILED，derived 回滚，product 保持 ACTIVE。"""
        p = ProductFactory(status='active')
        real_before = ProductMethodRelation.objects.filter(
            product=p, relation_type='derived_relevance'
        ).count()
        with patch(
            'apps.bridges.services.association_service.rebuild_derived_for_product',
            side_effect=RuntimeError('db boom'),
        ):
            result = AssociationService.process_product(p.id)
        assert result['execution_result'] == 'FAILED'
        assert result['scientific_quality'] is None
        p.refresh_from_db()
        assert p.status == 'active'
        after = ProductMethodRelation.objects.filter(
            product=p, relation_type='derived_relevance'
        ).count()
        assert after == real_before  # 回滚：派生边无净变化
