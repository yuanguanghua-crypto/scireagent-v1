from django.contrib import admin
from .models import ProductMethod, MethodProtocol, ProductReference, ProductCompatibility, ProductProduct


@admin.register(ProductMethod)
class ProductMethodAdmin(admin.ModelAdmin):
    list_display = ('product', 'method', 'role', 'evidence_level', 'display_order')
    list_filter = ('role', 'evidence_level')


@admin.register(MethodProtocol)
class MethodProtocolAdmin(admin.ModelAdmin):
    list_display = ('method', 'protocol', 'display_order', 'featured', 'status')
    list_filter = ('featured', 'status')


@admin.register(ProductReference)
class ProductReferenceAdmin(admin.ModelAdmin):
    list_display = ('product', 'reference', 'citation_role', 'display_order')
    list_filter = ('citation_role',)


@admin.register(ProductCompatibility)
class ProductCompatibilityAdmin(admin.ModelAdmin):
    list_display = ('source_product', 'target_product', 'compatibility', 'verdict')
    list_filter = ('verdict',)


@admin.register(ProductProduct)
class ProductProductAdmin(admin.ModelAdmin):
    list_display = ('source_product', 'target_product', 'relation_type', 'direction')
    list_filter = ('relation_type', 'direction')
