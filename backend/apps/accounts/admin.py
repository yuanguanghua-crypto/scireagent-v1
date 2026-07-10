from unfold.admin import ModelAdmin
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Organization, User


@admin.register(Organization)
class OrganizationAdmin(ModelAdmin):
    list_display = ('name', 'short_name', 'org_type', 'status', 'member_count', 'created_at')
    list_filter = ('org_type', 'status')
    search_fields = ('name', 'short_name', 'contact_email')
    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'short_name', 'org_type', 'status', 'description'),
        }),
        ('联系方式', {
            'fields': ('website', 'contact_email', 'contact_phone'),
        }),
        ('地址', {
            'fields': ('address_line1', 'address_line2', 'city', 'state', 'postal_code', 'country'),
            'classes': ('collapse',),
        }),
        ('商务', {
            'fields': ('approval_required', 'credit_limit', 'created_by'),
            'classes': ('collapse',),
        }),
    )

    def member_count(self, obj):
        return obj.members.count()
    member_count.short_description = '成员数'


@admin.register(User)
class CustomUserAdmin(BaseUserAdmin, ModelAdmin):
    list_display = ('username', 'email', 'role', 'organization', 'is_org_admin', 'is_staff', 'is_active')
    list_filter = ('role', 'is_org_admin', 'is_staff', 'is_active')

    fieldsets = BaseUserAdmin.fieldsets + (
        ('SciReagent 信息', {
            'fields': (
                'organization', 'role', 'is_org_admin',
                'nickname', 'phone', 'department', 'title', 'avatar_url',
            ),
        }),
        ('收货信息', {
            'fields': (
                'default_shipping_address', 'shipping_name', 'shipping_phone', 'shipping_email',
            ),
            'classes': ('collapse',),
        }),
        ('支付信息', {
            'fields': ('default_payment_method', 'default_po_number', 'alternate_email'),
            'classes': ('collapse',),
        }),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('SciReagent', {
            'fields': ('role', 'organization'),
        }),
    )
