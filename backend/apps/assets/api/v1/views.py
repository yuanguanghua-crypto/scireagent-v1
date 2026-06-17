from rest_framework import viewsets
from core.mixins import EnvelopeMixin
from core.permissions import IsAdminOrReadOnly
from apps.assets.models import PdfFile
from apps.assets.api.v1.serializers import PdfFileSerializer


class PdfFileViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    queryset = PdfFile.objects.all()
    serializer_class = PdfFileSerializer
    permission_classes = [IsAdminOrReadOnly]
