from rest_framework import serializers
from core.serializers import BaseModelSerializer
from apps.notifications.models import EmailOutbox, EmailTemplate


class EmailOutboxSerializer(BaseModelSerializer):
    """只读 — Outbox 由 Service 写入，cron 发送。"""
    class Meta:
        model = EmailOutbox
        fields = [
            'id', 'to_emails', 'cc_emails', 'subject',
            'status', 'retry_count', 'next_retry_at', 'sent_at',
            'template_key', 'created_at',
        ]


class EmailTemplateSerializer(BaseModelSerializer):
    """CRUD — Admin 可改模板内容。"""
    class Meta:
        model = EmailTemplate
        fields = [
            'id', 'key', 'subject', 'body_html', 'body_text',
            'description', 'language', 'created_at', 'updated_at',
        ]
