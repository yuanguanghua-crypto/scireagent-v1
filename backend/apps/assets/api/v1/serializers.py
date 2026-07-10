from core.serializers import BaseModelSerializer
from apps.assets.models import PdfFile


class PdfFileSerializer(BaseModelSerializer):
    class Meta:
        model = PdfFile
        fields = ['id', 'file', 'checksum', 'mime_type', 'page_count', 'extraction_state', 'created_at']
