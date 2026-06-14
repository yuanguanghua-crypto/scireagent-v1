from django.contrib import admin
from .models import Order, OrderItem, Invoice, PaymentRecord, ShippingRecord, Quote, QuoteItem, Basket, Wishlist


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_no', 'user', 'organization', 'status', 'payment_method', 'po_number', 'grand_total', 'currency', 'created_at')
    list_filter = ('status', 'currency', 'payment_method')
    search_fields = ('order_no', 'po_number', 'user__username')
    inlines = [OrderItemInline]


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_no', 'order', 'status', 'grand_total', 'due_date', 'paid_at')
    list_filter = ('status',)
    search_fields = ('invoice_no', 'order__order_no')


@admin.register(PaymentRecord)
class PaymentRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'invoice', 'method', 'amount', 'status', 'verified_by', 'verified_at')
    list_filter = ('status', 'method')
    search_fields = ('invoice__invoice_no', 'reference')


@admin.register(ShippingRecord)
class ShippingRecordAdmin(admin.ModelAdmin):
    list_display = ('order', 'status', 'carrier', 'tracking_number', 'shipped_at')
    list_filter = ('status',)
    search_fields = ('order__order_no', 'tracking_number')


class QuoteItemInline(admin.TabularInline):
    model = QuoteItem
    extra = 0


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = ('quote_no', 'contact_name', 'company_name', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('quote_no', 'contact_name', 'company_name')
    inlines = [QuoteItemInline]


@admin.register(Basket)
class BasketAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'sku', 'quantity')


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'created_at')
