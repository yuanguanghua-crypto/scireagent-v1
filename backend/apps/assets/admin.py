from django.contrib import admin
from .models import PdfFile


@admin.register(PdfFile)
class PdfFileAdmin(admin.ModelAdmin):
    list_display = ('id', 'file', 'mime_type', 'page_count', 'extraction_state', 'created_at')
    list_filter = ('extraction_state',)
