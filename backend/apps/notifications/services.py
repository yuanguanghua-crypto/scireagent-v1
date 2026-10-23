from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from apps.notifications.models import EmailOutbox, EmailTemplate

# 这些后端发出去的信 **到不了任何用户**（控制台日志 / 直接丢弃 / 落地成文件）。
# 判据放在这里（邮件服务模块）而不是某个视图里，是为了让「注册放行」与「投递任务守卫」
# 共用同一处定义，不会各写一份而漂移。
#
# ⚠️ 刻意**不**包含 `locmem`：它是 Django 测试专用后端，单测靠 `mail.outbox` 断言邮件内容；
#    把它算作不可达会让全部邮件测试失效，而生产不会用 locmem。
_UNREACHABLE_EMAIL_BACKENDS = (
    'console.EmailBackend',
    'dummy.EmailBackend',
    'filebased.EmailBackend',
)


# ── 投递调度心跳 ──────────────────────────────────────────────────────
# 放 MEDIA_ROOT 下：那里是 named volume，重建容器不丢；容器内可写。
# 比 /tmp 可靠（重建即丢），比新建一张表轻（不为一行业务造表）。
HEARTBEAT_DIR = '.health'
HEARTBEAT_FILE = 'email_dispatch.heartbeat'


def _heartbeat_path() -> Path:
    return Path(settings.MEDIA_ROOT) / HEARTBEAT_DIR / HEARTBEAT_FILE


def record_dispatch_heartbeat() -> None:
    """由 `send_outbox_emails` 每次执行时调用。失败不抛 —— 心跳不能影响投递。"""
    import logging
    try:
        p = _heartbeat_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(datetime.now(dt_timezone.utc).isoformat(), encoding='utf-8')
    except Exception:
        logging.getLogger(__name__).warning(
            '[notifications] 写调度心跳失败（不影响投递）', exc_info=True)


def read_dispatch_heartbeat():
    """返回 (iso_str|None, minutes_ago|None)。文件不存在或损坏都返回 (None, None)。"""
    p = _heartbeat_path()
    try:
        if not p.exists():
            return None, None
        raw = p.read_text(encoding='utf-8').strip()
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=dt_timezone.utc)
        return raw, round((datetime.now(dt_timezone.utc) - dt).total_seconds() / 60, 1)
    except Exception:
        return None, None


def email_delivery_is_unavailable() -> bool:
    """当前是否处于「发出去也到不了用户」的降级配置。

    一旦配置了真实发信通道（Mailgun / Resend / SMTP），本函数自动返回 False，
    注册的邮箱验证强制与投递任务守卫同时恢复，不需要改代码。
    """
    backend = getattr(settings, 'EMAIL_BACKEND', '') or ''
    return any(marker in backend for marker in _UNREACHABLE_EMAIL_BACKENDS)


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
