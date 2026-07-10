from django.contrib import admin

from apps.inventory.models import Inventory, Allocation


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'sku', 'batch', 'location', 'available', 'allocated', 'on_hand')
    list_filter = ('location',)
    search_fields = ('sku__sku_code',)


@admin.register(Allocation)
class AllocationAdmin(admin.ModelAdmin):
    list_display = ('id', 'order_item', 'inventory', 'quantity', 'status')
    list_filter = ('status',)
