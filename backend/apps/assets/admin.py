from unfold.admin import ModelAdmin
from django.contrib import admin
from .models import PdfFile


@admin.register(PdfFile)
class PdfFileAdmin(ModelAdmin):
    list_display = ('id', 'file', 'mime_type', 'page_count', 'extraction_state', 'created_at')
    list_filter = ('extraction_state',)
    search_fields = ('file',)
    fieldsets = (
        (None, {
            'fields': ('file', 'mime_type', 'page_count'),
        }),
        ('提取状态', {
            'fields': ('extraction_state', 'checksum'),
        }),
    )
