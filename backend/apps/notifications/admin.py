from django.contrib import admin

from apps.notifications.models import EmailOutbox, EmailTemplate


@admin.register(EmailOutbox)
class EmailOutboxAdmin(admin.ModelAdmin):
    list_display = ('id', 'to_emails', 'subject', 'status', 'retry_count', 'sent_at')
    list_filter = ('status',)
    search_fields = ('to_emails', 'subject', 'template_key')


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ('id', 'key', 'subject', 'language')
    search_fields = ('key', 'subject')
