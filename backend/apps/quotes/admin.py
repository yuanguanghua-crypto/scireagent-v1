from unfold.admin import ModelAdmin
from django.contrib import admin

from .models import QuoteRequest, QuoteRequestItem


class QuoteRequestItemInline(admin.TabularInline):
    model = QuoteRequestItem
    extra = 0
    fields = ('product', 'sku', 'quantity', 'note')
    autocomplete_fields = ('product', 'sku')
    verbose_name = '询价项'
    verbose_name_plural = '询价项'


@admin.register(QuoteRequest)
class QuoteRequestAdmin(ModelAdmin):
    list_display = ('id', 'contact_name', 'contact_email', 'company_name', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('contact_name', 'contact_email', 'company_name')
    autocomplete_fields = ('user',)
    inlines = [QuoteRequestItemInline]
    fieldsets = (
        ('基本信息', {
            'fields': ('user', 'status'),
        }),
        ('联系人', {
            'fields': ('contact_name', 'contact_email', 'contact_phone', 'company_name', 'country'),
        }),
        ('备注', {
            'fields': ('notes',),
            'classes': ('collapse',),
        }),
    )
