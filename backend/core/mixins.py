from rest_framework.response import Response


class EnvelopeMixin:
    """Mixin for ViewSets to use envelope response helpers."""

    def success_response(self, data=None, meta=None, status_code=200):
        return Response(
            {'success': True, 'data': data, 'meta': meta or {}},
            status=status_code,
        )

    def error_response(self, message, code='error', status_code=400):
        return Response(
            {'success': False, 'data': None, 'meta': {'error': {'code': code, 'message': message}}},
            status=status_code,
        )
