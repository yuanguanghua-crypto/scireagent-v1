from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Organization, User


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'org_type', 'status', 'member_count', 'created_at')
    list_filter = ('org_type', 'status')
    search_fields = ('name', 'short_name')

    def member_count(self, obj):
        return obj.members.count()

    member_count.short_description = 'Members'


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        'username', 'email', 'role', 'organization', 'is_org_admin',
        'is_staff', 'is_active',
    )
    list_filter = ('role', 'is_org_admin', 'is_staff', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        ('SciReagent Info', {
            'fields': (
                'organization', 'role', 'is_org_admin', 'nickname', 'phone',
                'department', 'title', 'avatar_url', 'default_shipping_address',
                'alternate_email',
            ),
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('SciReagent Info', {
            'fields': ('role',),
        }),
    )
