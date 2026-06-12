from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        error_data = {
            'code': _get_error_code(response.status_code),
            'message': _get_error_message(response.data),
        }
        if isinstance(response.data, dict):
            error_data['details'] = {k: v for k, v in response.data.items() if k not in ('detail',)}

        response.data = {
            'success': False,
            'data': None,
            'meta': {'error': error_data},
        }

    return response


def _get_error_code(status_code):
    codes = {
        400: 'validation_error',
        401: 'unauthorized',
        403: 'forbidden',
        404: 'not_found',
        409: 'conflict',
        429: 'rate_limited',
        500: 'server_error',
    }
    return codes.get(status_code, 'error')


def _get_error_message(data):
    if isinstance(data, dict) and 'detail' in data:
        return str(data['detail'])
    if isinstance(data, list):
        return '; '.join(str(item) for item in data)
    return str(data)
