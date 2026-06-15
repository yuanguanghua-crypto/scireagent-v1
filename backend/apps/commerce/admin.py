from unfold.admin import ModelAdmin
from django.contrib import admin

from .models import ProductClass, CatalogGroup, Product, SKU, ProductDocument


# ── Inlines ──────────────────────────────────────────

class SKUInline(admin.TabularInline):
    model = SKU
    extra = 0
    fields = ('sku_code', 'pack_size', 'price', 'currency', 'inventory_status', 'is_default')
    verbose_name = 'SKU'
    verbose_name_plural = 'SKUs（规格）'


# ── ProductClass ─────────────────────────────────────

@admin.register(ProductClass)
class ProductClassAdmin(ModelAdmin):
    list_display = ('name', 'parent', 'sort_order')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'parent', 'sort_order'),
        }),
    )


# ── CatalogGroup ─────────────────────────────────────

@admin.register(CatalogGroup)
class CatalogGroupAdmin(ModelAdmin):
    list_display = ('name', 'locale', 'active')
    list_filter = ('active', 'locale')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


# ── Product ──────────────────────────────────────────

@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = ('catalog_no', 'name', 'cas', 'formula', 'purity', 'category_l1', 'status', 'display_priority')
    list_filter = ('status', 'product_class', 'research_use_only', 'category_l1')
    search_fields = ('name', 'cas', 'catalog_no', 'smiles', 'inchi', 'formula')
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ('product_class', 'catalog_group')
    inlines = [SKUInline]
    list_per_page = 50
    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'slug', 'catalog_no', 'cas', 'synonyms', 'status', 'research_use_only', 'display_priority'),
        }),
        ('化学结构', {
            'fields': ('smiles', 'inchi', 'formula', 'molecular_weight', 'structure_svg'),
            'classes': ('collapse',),
        }),
        ('科学参数', {
            'fields': ('purity', 'concentration', 'storage', 'shipping', 'lead_time', 'handling_notes', 'shelf_life'),
            'classes': ('collapse',),
        }),
        ('分类', {
            'fields': ('product_class', 'catalog_group', 'category_l1', 'category_l2'),
            'classes': ('collapse',),
        }),
        ('内容', {
            'fields': ('overview',),
            'classes': ('collapse',),
        }),
        ('SEO', {
            'fields': ('seo_title', 'seo_description'),
            'classes': ('collapse',),
        }),
    )


# ── SKU ──────────────────────────────────────────────

@admin.register(SKU)
class SKUAdmin(ModelAdmin):
    list_display = ('sku_code', 'product', 'pack_size', 'price', 'currency', 'inventory_status', 'is_default')
    list_filter = ('inventory_status', 'currency', 'is_default')
    search_fields = ('sku_code', 'product__name', 'product__catalog_no')
    autocomplete_fields = ('product',)
    fieldsets = (
        (None, {
            'fields': ('product', 'sku_code', 'pack_size'),
        }),
        ('价格与库存', {
            'fields': ('price', 'currency', 'inventory_status', 'is_default'),
        }),
        ('参数', {
            'fields': ('concentration', 'lead_time'),
            'classes': ('collapse',),
        }),
    )


# ── ProductDocument ──────────────────────────────────

@admin.register(ProductDocument)
class ProductDocumentAdmin(ModelAdmin):
    list_display = ('product', 'document_type', 'language', 'version', 'original_filename', 'created_at')
    list_filter = ('document_type', 'language')
    search_fields = ('product__name', 'original_filename')
    autocomplete_fields = ('product',)
    fieldsets = (
        (None, {
            'fields': ('product', 'document_type', 'language', 'version'),
        }),
        ('文件', {
            'fields': ('file', 'original_filename'),
        }),
    )
