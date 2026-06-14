from django.contrib import admin
from .models import ProductClass, CatalogGroup, Product, SKU, ProductDocument


@admin.register(ProductClass)
class ProductClassAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'sort_order')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(CatalogGroup)
class CatalogGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'locale', 'active')
    list_filter = ('active', 'locale')
    prepopulated_fields = {'slug': ('name',)}


class SKUInline(admin.TabularInline):
    model = SKU
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'catalog_no', 'cas', 'formula', 'purity', 'category_l1', 'status', 'research_use_only')
    list_filter = ('status', 'product_class', 'research_use_only', 'category_l1')
    search_fields = ('name', 'cas', 'catalog_no', 'smiles', 'inchi', 'formula')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [SKUInline]


@admin.register(SKU)
class SKUAdmin(admin.ModelAdmin):
    list_display = ('sku_code', 'product', 'pack_size', 'price', 'currency', 'inventory_status', 'is_default')
    list_filter = ('inventory_status', 'currency', 'is_default')
    search_fields = ('sku_code',)


class ProductDocumentInline(admin.TabularInline):
    model = ProductDocument
    extra = 0


@admin.register(ProductDocument)
class ProductDocumentAdmin(admin.ModelAdmin):
    list_display = ('product', 'document_type', 'language', 'version', 'original_filename', 'created_at')
    list_filter = ('document_type', 'language')
    search_fields = ('product__name', 'original_filename')
