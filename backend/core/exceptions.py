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
    """把 DRF 的 response.data 转成给用户看的单行消息。

    DRF 字段级校验错误形如 {'catalog_no': [ErrorDetail(...)]}，
    直接 str() 会得到 "{'catalog_no': [ErrorDetail(string='...', code='unique')]}"，
    这种 repr 形态会原样泄漏到前端弹窗。这里递归展开成 'catalog_no: ...'。
    """
    # ErrorDetail 是 str 的子类，单条直接转字符串即可
    if isinstance(data, (list, tuple)):
        parts = [_format_field_errors(None, item) for item in data]
        return '; '.join(p for p in parts if p)
    if isinstance(data, dict):
        return '; '.join(_format_field_errors(k, v) for k, v in data.items())
    return str(data)


def _format_field_errors(field, value):
    """递归把字段值展开成可读字符串。

    - dict：嵌套 serializer，展开成 'child: message'（'detail'/'non_field_errors' 不加前缀）
    - list/tuple：元素若为 dict 则递归展开，多个错误用 ', ' 连接
    - 其它（含 ErrorDetail，是 str 子类）：str(value)
    field 为 None 表示这是顶层列表元素，不加前缀。
    """
    if isinstance(value, dict):
        nested = '; '.join(_format_field_errors(k, v) for k, v in value.items())
        text = nested
    elif isinstance(value, (list, tuple)):
        parts = []
        for v in value:
            if isinstance(v, dict):
                parts.append('; '.join(_format_field_errors(k, v2) for k, v2 in v.items()))
            else:
                parts.append(str(v))
        text = ', '.join(p for p in parts if p)
    else:
        text = str(value)

    if field is None or field in ('detail', 'non_field_errors'):
        return text
    return f'{field}: {text}' if text else ''
