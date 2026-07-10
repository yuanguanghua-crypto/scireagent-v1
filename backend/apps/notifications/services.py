from datetime import timedelta

from django.utils import timezone

from apps.notifications.models import EmailOutbox, EmailTemplate


class _SafeDict(dict):
    """str.format_map 的容错字典：缺失键返回空串，避免渲染抛错。"""

    def __missing__(self, key):
        return ''


def render_template(text: str, ctx: dict) -> str:
    if not text:
        return ''
    try:
        return text.format_map(_SafeDict(ctx or {}))
    except Exception:
        return text


class EmailService:
    """邮件入队 — 渲染 EmailTemplate 写入 EmailOutbox(PENDING)，不实际发送。"""

    @staticmethod
    def enqueue(template_key: str, to, ctx: dict = None, attachments: list = None,
                subject: str = '', body_html: str = '', body_text: str = '') -> EmailOutbox:
        ctx = ctx or {}
        if isinstance(to, (list, tuple, set)):
            to_emails = ','.join(str(t) for t in to)
        else:
            to_emails = str(to)

        template = EmailTemplate.objects.filter(key=template_key).first()
        if template:
            subject = render_template(template.subject, ctx)
            body_html = render_template(template.body_html, ctx)
            body_text = render_template(template.body_text, ctx)

        outbox = EmailOutbox.objects.create(
            to_emails=to_emails,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            attachment_paths=list(attachments or []),
            status=EmailOutbox.Status.PENDING,
            next_retry_at=timezone.now(),
            template_key=template_key,
            context_json=ctx,
        )
        return outbox
