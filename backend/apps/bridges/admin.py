from unfold.admin import ModelAdmin
from django.contrib import admin

from .models import (
    ProductMethod, MethodProtocol, ProductReference,
    ProductCompatibility, ProductProduct,
)


@admin.register(ProductMethod)
class ProductMethodAdmin(ModelAdmin):
    list_display = ('product', 'method', 'role', 'evidence_level', 'display_order')
    list_filter = ('role', 'evidence_level')
    search_fields = ('product__name', 'product__catalog_no', 'method__name')
    autocomplete_fields = ('product', 'method')
    fieldsets = (
        (None, {
            'fields': ('product', 'method'),
        }),
        ('详情', {
            'fields': ('role', 'evidence_level', 'display_order'),
        }),
    )


@admin.register(MethodProtocol)
class MethodProtocolAdmin(ModelAdmin):
    list_display = ('method', 'protocol', 'display_order', 'featured', 'status')
    list_filter = ('featured', 'status')
    search_fields = ('method__name', 'protocol__name')
    autocomplete_fields = ('method', 'protocol')
    fieldsets = (
        (None, {
            'fields': ('method', 'protocol'),
        }),
        ('详情', {
            'fields': ('display_order', 'featured', 'status'),
        }),
    )


@admin.register(ProductReference)
class ProductReferenceAdmin(ModelAdmin):
    list_display = ('product', 'reference', 'citation_role', 'display_order')
    list_filter = ('citation_role',)
    search_fields = ('product__name', 'reference__title')
    autocomplete_fields = ('product', 'reference')
    fieldsets = (
        (None, {
            'fields': ('product', 'reference'),
        }),
        ('详情', {
            'fields': ('citation_role', 'display_order'),
        }),
    )


@admin.register(ProductCompatibility)
class ProductCompatibilityAdmin(ModelAdmin):
    list_display = ('source_product', 'target_product', 'compatibility', 'verdict')
    list_filter = ('verdict',)
    search_fields = ('source_product__name', 'target_product__name')
    autocomplete_fields = ('source_product', 'target_product', 'compatibility')
    fieldsets = (
        (None, {
            'fields': ('source_product', 'target_product', 'compatibility'),
        }),
        ('详情', {
            'fields': ('verdict', 'notes'),
        }),
    )


@admin.register(ProductProduct)
class ProductProductAdmin(ModelAdmin):
    list_display = ('source_product', 'target_product', 'relation_type', 'direction', 'strength')
    list_filter = ('relation_type', 'direction')
    search_fields = ('source_product__name', 'target_product__name')
    autocomplete_fields = ('source_product', 'target_product')
    fieldsets = (
        (None, {
            'fields': ('source_product', 'target_product'),
        }),
        ('关系', {
            'fields': ('relation_type', 'direction', 'strength', 'notes'),
        }),
    )
