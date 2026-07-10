from unfold.admin import ModelAdmin
from unfold.decorators import action
from django.contrib import admin
from django import forms
from django.utils.safestring import mark_safe

from .models import ProductClass, CatalogGroup, Product, SKU, ProductDocument
from .services.seo_generator import generate_seo
from apps.bridges.models import ProductMethod, ProductReference, ProductCompatibility, ProductProduct


# ── SKU Form ─────────────────────────────────────────

class SKUInlineForm(forms.ModelForm):
    class Meta:
        model = SKU
        fields = '__all__'
        widgets = {
            'price': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
        }


# ── Inlines ──────────────────────────────────────────

class SKUInline(admin.TabularInline):
    model = SKU
    form = SKUInlineForm
    extra = 0
    fields = ('sku_code', 'pack_size', 'price', 'currency', 'inventory_status', 'is_default')
    verbose_name = 'SKU'
    verbose_name_plural = 'SKUs'


class ProductMethodInline(admin.TabularInline):
    """Inline for Product ↔ Method bridge — researcher adds without navigating away."""
    model = ProductMethod
    extra = 0
    autocomplete_fields = ('method',)
    fields = ('method', 'role', 'evidence_level', 'display_order')
    classes = ('collapse',)
    verbose_name = 'Method'
    verbose_name_plural = 'Methods'


class ProductReferenceInline(admin.TabularInline):
    """Inline for Product ↔ Reference bridge."""
    model = ProductReference
    extra = 0
    autocomplete_fields = ('reference',)
    fields = ('reference', 'citation_role', 'display_order')
    classes = ('collapse',)
    verbose_name = 'Reference'
    verbose_name_plural = 'References'


class ProductCompatibilityInline(admin.TabularInline):
    """Inline for Product ↔ Product compatibility facts."""
    model = ProductCompatibility
    fk_name = 'source_product'
    extra = 0
    autocomplete_fields = ('target_product', 'compatibility')
    fields = ('target_product', 'compatibility', 'verdict', 'notes')
    classes = ('collapse',)
    verbose_name = 'Compatibility'
    verbose_name_plural = 'Compatibility'


class ProductProductInline(admin.TabularInline):
    """Inline for Product ↔ Product relations (substitutes, complements, etc.)."""
    model = ProductProduct
    fk_name = 'source_product'
    extra = 0
    autocomplete_fields = ('target_product',)
    fields = ('target_product', 'relation_type', 'direction', 'strength')
    classes = ('collapse',)
    verbose_name = 'Related Product'
    verbose_name_plural = 'Related Products'


# ── ProductClass ─────────────────────────────────────

@admin.register(ProductClass)
class ProductClassAdmin(ModelAdmin):
    list_display = ('name', 'parent', 'sort_order')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


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
    inlines = [SKUInline, ProductMethodInline, ProductReferenceInline,
               ProductCompatibilityInline, ProductProductInline]
    list_per_page = 50
    save_on_top = True
    # Product editing moved to Vue workspace; Django Admin is read-only snapshot
    readonly_fields = ['name', 'slug', 'catalog_no', 'cas', 'synonyms',
                       'status', 'research_use_only', 'display_priority',
                       'overview', 'smiles', 'inchi', 'formula', 'molecular_weight',
                       'purity', 'concentration', 'storage', 'shipping',
                       'lead_time', 'shelf_life', 'handling_notes',
                       'product_class', 'catalog_group',
                       'category_l1', 'category_l2',
                       'seo_title', 'seo_description']
    actions = None  # disable batch actions (no write allowed)

    # ── 扁平化：所有字段在一个 section ───────────────
    fieldsets = (
        (None, {
            'fields': (
                'name', 'slug', 'catalog_no', 'cas', 'synonyms',
                'status', 'research_use_only', 'display_priority',
                'overview',
                # 化学结构
                'smiles', 'inchi', 'formula', 'molecular_weight',
                # 科学参数
                ('purity', 'concentration'),
                ('storage', 'shipping'),
                ('lead_time', 'shelf_life'),
                'handling_notes',
                # 分类
                'product_class', 'catalog_group',
                'category_l1', 'category_l2',
                # SEO
                'seo_title', 'seo_description',
            ),
        }),
    )

    # ── 加载自定义 JS（L1→L2 联动）─────────────────
    class Media:
        js = ('admin/js/category_chained.js',)


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
