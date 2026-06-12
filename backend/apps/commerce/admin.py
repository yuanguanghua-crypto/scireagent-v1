from django.contrib import admin
from .models import ProductClass, CatalogGroup, Product, SKU


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
    list_display = ('name', 'cas', 'purity', 'product_class', 'status', 'research_use_only')
    list_filter = ('status', 'product_class', 'research_use_only')
    search_fields = ('name', 'cas', 'smiles', 'inchi')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [SKUInline]


@admin.register(SKU)
class SKUAdmin(admin.ModelAdmin):
    list_display = ('sku_code', 'product', 'pack_size', 'price', 'currency', 'inventory_status')
    list_filter = ('inventory_status', 'currency')
    search_fields = ('sku_code',)
