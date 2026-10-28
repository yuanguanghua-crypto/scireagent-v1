from rest_framework.response import Response


class EnvelopeMixin:
    """Mixin for ViewSets to use envelope response helpers."""

    def success_response(self, data=None, meta=None, status_code=200):
        return Response(
            {'success': True, 'data': data, 'meta': meta or {}},
            status=status_code,
        )

    def error_response(self, message, code='error', status_code=400, details=None):
        """统一错误信封。

        `details`（2026-10-28 新增，向后兼容）：结构化补充信息，落在
        `meta.error.details`。首个使用者是缺货拦截 —— 前端要逐行列出
        「哪个 SKU、要多少、只剩多少」，只给一句 message 无法渲染。
        传 None 时**不写** details 键，旧调用方的响应体逐字节不变。
        """
        error = {'code': code, 'message': message}
        if details is not None:
            error['details'] = details
        return Response(
            {'success': False, 'data': None, 'meta': {'error': error}},
            status=status_code,
        )
