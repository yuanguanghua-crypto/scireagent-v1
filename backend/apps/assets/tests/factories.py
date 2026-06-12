import factory
from apps.assets.models import PdfFile


class PdfFileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PdfFile
    checksum = factory.LazyFunction(lambda: 'a' * 64)
    mime_type = 'application/pdf'
