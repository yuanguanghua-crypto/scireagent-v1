"""custom_exception_handler 错误消息友好化测试。

回归：DRF 字段级校验错误（{field: [ErrorDetail]}）曾被 str(data) 整体转字符串，
导致前端弹出 {'catalog_no': [ErrorDetail(string='...', code='unique')]} 这种 repr。
"""
from rest_framework.exceptions import ValidationError
from core.exceptions import _get_error_message


class TestGetErrorMessage:
    def test_field_error_dict_unwrapped(self):
        """字段级错误应展开为 'field: message'，而非 dict repr"""
        err = ValidationError({'catalog_no': ['产品 with this 目录号 already exists.']})
        msg = _get_error_message(err.detail)
        assert msg == 'catalog_no: 产品 with this 目录号 already exists.'
        # 关键：不能是 repr 形态
        assert 'ErrorDetail' not in msg
        assert msg.startswith('catalog_no:')

    def test_non_field_errors_no_prefix(self):
        """non_field_errors 不带字段名前缀"""
        err = ValidationError({'non_field_errors': ['不可同时为空']})
        assert _get_error_message(err.detail) == '不可同时为空'

    def test_detail_key(self):
        """含 detail 的 dict（如 PermissionDenied）直接取 detail"""
        err = ValidationError({'detail': '权限不足'})
        assert _get_error_message(err.detail) == '权限不足'

    def test_top_level_list(self):
        """顶层列表错误用分号连接"""
        err = ValidationError(['错误一', '错误二'])
        assert _get_error_message(err.detail) == '错误一; 错误二'

    def test_nested_serializer_errors(self):
        """嵌套 serializer 错误展开成 'parent: child: message'"""
        err = ValidationError({'skus': [{'sku_code': ['该 SKU 已存在']}]})
        msg = _get_error_message(err.detail)
        assert msg == 'skus: sku_code: 该 SKU 已存在'

    def test_multiple_fields_joined(self):
        """多字段错误用分号连接"""
        err = ValidationError({
            'catalog_no': ['已存在'],
            'name': ['该字段是必填项'],
        })
        msg = _get_error_message(err.detail)
        assert 'catalog_no: 已存在' in msg
        assert 'name: 该字段是必填项' in msg
