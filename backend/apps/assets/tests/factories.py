import factory
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.assets.models import PdfFile


class PdfFileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PdfFile

    file = factory.LazyAttribute(
        lambda _: SimpleUploadedFile(
            name='test.pdf',
            content=b'%PDF-1.4 minimal pdf content',
            content_type='application/pdf',
        )
    )
    checksum = factory.LazyFunction(lambda: 'a' * 64)
    mime_type = 'application/pdf'
