"""Word 文档解析 API 端点。

POST /api/v1/products/parse-word/ — 上传 .docx 文件，返回结构化产品数据。
"""
from django.core.exceptions import ValidationError
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser
from rest_framework import status

from core.mixins import EnvelopeMixin
from core.permissions import IsStaffUser
from apps.commerce.services.word_parser import (
    WordParserService, FileUnreadableError, FileTooLargeError,
)


class WordParseView(EnvelopeMixin, APIView):
    """解析 Word (.docx) 产品说明文档，返回结构化字段 JSON。"""

    permission_classes = [IsStaffUser]
    parser_classes = [MultiPartParser]

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return self.error_response('请上传文件', code='FILE_REQUIRED',
                                       status_code=status.HTTP_400_BAD_REQUEST)

        if not file.name.lower().endswith('.docx'):
            return self.error_response('仅支持 .docx 格式', code='UNSUPPORTED_FORMAT',
                                       status_code=status.HTTP_400_BAD_REQUEST)

        try:
            service = WordParserService()
            result = service.parse(file)
        except ValidationError as e:
            return self.error_response(str(e), code='UNSUPPORTED_FORMAT',
                                       status_code=status.HTTP_400_BAD_REQUEST)
        except FileUnreadableError:
            return self.error_response('文件无法读取，可能已损坏或加密',
                                       code='FILE_UNREADABLE',
                                       status_code=status.HTTP_400_BAD_REQUEST)
        except FileTooLargeError:
            return self.error_response('文件大小超过 10MB 限制',
                                       code='FILE_TOO_LARGE',
                                       status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

        return self.success_response(result)
