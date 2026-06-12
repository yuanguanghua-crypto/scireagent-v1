from django.db import models
from core.models import TimeStampedModel


class PdfFile(TimeStampedModel):
    """PDF 文件资产"""
    file = models.FileField(upload_to='pdfs/%Y%m%d/', verbose_name='文件')
    checksum = models.CharField(max_length=64, blank=True, default='', verbose_name='校验和')
    mime_type = models.CharField(max_length=100, default='application/pdf', verbose_name='MIME类型')
    page_count = models.IntegerField(null=True, blank=True, verbose_name='页数')
    extraction_state = models.CharField(max_length=20, default='pending', verbose_name='提取状态')

    class Meta:
        db_table = 'pdf_file'
        verbose_name = 'PDF文件'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'PDF {self.id}: {self.file.name}'
