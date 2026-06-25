from unfold.admin import ModelAdmin
from django.contrib import admin
from .models import Batch, Coa, SdsRevision, PubChemCache


@admin.register(Batch)
class BatchAdmin(ModelAdmin):
    list_display = ('lot_number', 'sku', 'produced_at', 'retest_at', 'created_at')
    list_filter = ('produced_at',)
    search_fields = ('lot_number', 'sku__sku_code', 'sku__product__name')
    autocomplete_fields = ('sku',)


@admin.register(Coa)
class CoaAdmin(ModelAdmin):
    list_display = ('doc_id', 'batch', 'status', 'qc_analyst', 'qa_approval', 'approved_at')
    list_filter = ('status',)
    search_fields = ('doc_id', 'product_name', 'catalog_number')
    readonly_fields = ('pdf_path', 'created_at', 'updated_at')


@admin.register(SdsRevision)
class SdsRevisionAdmin(ModelAdmin):
    list_display = ('product', 'revision_no', 'signal_word', 'revised_at', 'created_at')
    list_filter = ('signal_word',)
    search_fields = ('product__name', 'product__catalog_no')
    readonly_fields = ('pdf_path', 'created_at')


@admin.register(PubChemCache)
class PubChemCacheAdmin(ModelAdmin):
    list_display = ('cas_number', 'cid', 'fetched_at')
    search_fields = ('cas_number',)
    readonly_fields = ('data_json', 'fetched_at')
