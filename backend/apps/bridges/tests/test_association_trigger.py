"""R1 触发点不变试 / 行为测试。

验证：
- CommerceService.activate_product 存在并调用 AssociationService.process_product（MUST-1 触发点聚合）
- 无合格派生数据时返回 REVIEW（非 FAILED），product 保持 ACTIVE（Q2 管线已运行≠产出边）
- ProductCreateUpdateSerializer 的 DRAFT→ACTIVE 转换触发 activate_product；非 active 转换不触发
"""
import pytest
from unittest.mock import patch

from apps.bridges.tests.factories import ProductFactory
from apps.commerce.services.commerce_service import CommerceService
from apps.bridges.services.association_service import AssociationService

pytestmark = pytest.mark.django_db


class TestCommerceActivateProduct:
    def test_activate_product_calls_pipeline(self):
        """MUST-1：激活入口必须聚合调用关联管线。"""
        p = ProductFactory(status='active')
        spy = patch.object(
            AssociationService,
            'process_product',
            return_value={'execution_result': 'SUCCESS', 'scientific_quality': 'REVIEW',
                          'derived_created': 0, 'derived_deleted': 0, 'verified_touched': 0},
        )
        with spy as sp:
            CommerceService.activate_product(p.id)
        sp.assert_called_once_with(p.id)

    def test_activate_product_no_eligible_yields_review_not_failed(self):
        """Q2：无合格派生数据时管线 SUCCESS + REVIEW，product 保持 ACTIVE，不抛。"""
        p = ProductFactory(status='active')
        result = CommerceService.activate_product(p.id)
        assert result['execution_result'] == 'SUCCESS'
        assert result['scientific_quality'] == 'REVIEW'
        assert result['derived_created'] == 0
        p.refresh_from_db()
        assert p.status == 'active'

    def test_activate_product_on_draft_is_pipeline_noop(self):
        """DRAFT 产品调 process_product 应早退（A1 已覆盖），activate 不抛、不产边。"""
        p = ProductFactory(status='draft')
        result = CommerceService.activate_product(p.id)
        assert result['execution_result'] == 'SKIPPED'
        assert result['derived_created'] == 0


class TestSerializerTrigger:
    def test_draft_to_active_triggers_activate_product(self):
        """MUST-1：DRAFT→ACTIVE 唯一转换点必须触发关联管线。"""
        from apps.commerce.api.v1.serializers import ProductCreateUpdateSerializer
        p = ProductFactory(status='draft')
        with patch('apps.commerce.api.v1.serializers.CommerceService.activate_product') as sp:
            ser = ProductCreateUpdateSerializer(instance=p, data={'status': 'active'}, partial=True)
            ser.is_valid(raise_exception=True)
            ser.save()
        sp.assert_called_once_with(p.id)

    def test_non_active_transition_does_not_trigger(self):
        """已是 active 再传 active（无状态跃迁）不应触发管线。"""
        from apps.commerce.api.v1.serializers import ProductCreateUpdateSerializer
        p = ProductFactory(status='active')
        with patch('apps.commerce.api.v1.serializers.CommerceService.activate_product') as sp:
            ser = ProductCreateUpdateSerializer(instance=p, data={'status': 'active'}, partial=True)
            ser.is_valid(raise_exception=True)
            ser.save()
        sp.assert_not_called()
