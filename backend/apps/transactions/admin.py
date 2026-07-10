from unfold.admin import ModelAdmin
from django.contrib import admin

from .models import (
    Order, OrderItem, Invoice, PaymentRecord,
    ShippingRecord, Quote, QuoteItem, Basket, Wishlist,
)


# ── Inlines ──────────────────────────────────────────

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ('product', 'sku', 'quantity', 'unit_price', 'subtotal')
    autocomplete_fields = ('product', 'sku')
    readonly_fields = ('subtotal',)
    verbose_name = '订单项'
    verbose_name_plural = '订单项'


class QuoteItemInline(admin.TabularInline):
    model = QuoteItem
    extra = 0
    fields = ('product', 'sku', 'quantity', 'unit_price', 'note')
    autocomplete_fields = ('product', 'sku')
    verbose_name = '报价项'
    verbose_name_plural = '报价项'


# ── Order ────────────────────────────────────────────

@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = ('order_no', 'user', 'organization', 'status', 'payment_method', 'grand_total', 'currency', 'created_at')
    list_filter = ('status', 'currency', 'payment_method')
    search_fields = ('order_no', 'po_number', 'user__username')
    autocomplete_fields = ('user', 'organization')
    inlines = [OrderItemInline]
    readonly_fields = ('grand_total',)
    fieldsets = (
        ('基本信息', {
            'fields': ('order_no', 'user', 'organization', 'status'),
        }),
        ('支付', {
            'fields': ('payment_method', 'po_number', 'po_contact', 'payment_terms', 'payment_due_date'),
        }),
        ('金额', {
            'fields': ('subtotal', 'tax_total', 'grand_total', 'currency'),
        }),
        ('收货地址', {
            'fields': ('shipping_name', 'shipping_address', 'shipping_phone', 'shipping_email'),
            'classes': ('collapse',),
        }),
        ('账单地址', {
            'fields': ('billing_name', 'billing_address'),
            'classes': ('collapse',),
        }),
        ('备注', {
            'fields': ('notes', 'internal_notes'),
            'classes': ('collapse',),
        }),
    )


# ── Invoice ──────────────────────────────────────────

@admin.register(Invoice)
class InvoiceAdmin(ModelAdmin):
    list_display = ('invoice_no', 'order', 'status', 'grand_total', 'due_date', 'paid_at')
    list_filter = ('status',)
    search_fields = ('invoice_no', 'order__order_no')
    autocomplete_fields = ('order',)
    fieldsets = (
        ('基本信息', {
            'fields': ('order', 'invoice_no', 'status'),
        }),
        ('金额', {
            'fields': ('subtotal', 'tax_total', 'grand_total', 'currency'),
        }),
        ('日期', {
            'fields': ('issued_at', 'due_date', 'paid_at'),
        }),
        ('其他', {
            'fields': ('payment_ref', 'notes'),
            'classes': ('collapse',),
        }),
    )


# ── PaymentRecord ────────────────────────────────────

@admin.register(PaymentRecord)
class PaymentRecordAdmin(ModelAdmin):
    list_display = ('id', 'invoice', 'method', 'amount', 'currency', 'status', 'verified_by', 'verified_at')
    list_filter = ('status', 'method')
    search_fields = ('invoice__invoice_no', 'reference')
    autocomplete_fields = ('invoice', 'verified_by')
    fieldsets = (
        (None, {
            'fields': ('invoice', 'method', 'amount', 'currency'),
        }),
        ('验证', {
            'fields': ('reference', 'proof_file', 'status', 'verified_by', 'verified_at'),
        }),
        ('备注', {
            'fields': ('notes',),
            'classes': ('collapse',),
        }),
    )


# ── ShippingRecord ───────────────────────────────────

@admin.register(ShippingRecord)
class ShippingRecordAdmin(ModelAdmin):
    list_display = ('order', 'status', 'carrier', 'tracking_number', 'shipped_at')
    list_filter = ('status',)
    search_fields = ('order__order_no', 'tracking_number')
    autocomplete_fields = ('order',)
    fieldsets = (
        ('基本信息', {
            'fields': ('order', 'status', 'carrier'),
        }),
        ('物流', {
            'fields': ('tracking_number', 'tracking_url'),
        }),
        ('时间', {
            'fields': ('shipped_at', 'estimated_delivery', 'delivered_at'),
        }),
        ('备注', {
            'fields': ('notes',),
            'classes': ('collapse',),
        }),
    )


# ── Quote ────────────────────────────────────────────

@admin.register(Quote)
class QuoteAdmin(ModelAdmin):
    list_display = ('quote_no', 'contact_name', 'company_name', 'status', 'grand_total', 'created_at')
    list_filter = ('status',)
    search_fields = ('quote_no', 'contact_name', 'company_name')
    autocomplete_fields = ('user',)
    inlines = [QuoteItemInline]
    fieldsets = (
        ('基本信息', {
            'fields': ('quote_no', 'user', 'status'),
        }),
        ('联系人', {
            'fields': ('contact_name', 'contact_email', 'contact_phone', 'company_name', 'country'),
        }),
        ('金额', {
            'fields': ('subtotal', 'grand_total', 'valid_until'),
        }),
        ('备注', {
            'fields': ('remark',),
            'classes': ('collapse',),
        }),
    )


# ── Basket ───────────────────────────────────────────

@admin.register(Basket)
class BasketAdmin(ModelAdmin):
    list_display = ('user', 'product', 'sku', 'quantity')
    search_fields = ('user__username', 'product__name', 'product__catalog_no')
    autocomplete_fields = ('user', 'product', 'sku')


# ── Wishlist ─────────────────────────────────────────

@admin.register(Wishlist)
class WishlistAdmin(ModelAdmin):
    list_display = ('name', 'user', 'created_at')
    search_fields = ('name', 'user__username')
    autocomplete_fields = ('user',)
    filter_horizontal = ('products',)
