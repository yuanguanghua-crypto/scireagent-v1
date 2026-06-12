from django.contrib import admin
from .models import Order, OrderItem, Quote, QuoteItem, Basket, Wishlist


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_no', 'user', 'status', 'grand_total', 'currency', 'created_at')
    list_filter = ('status', 'currency')
    search_fields = ('order_no',)
    inlines = [OrderItemInline]


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
