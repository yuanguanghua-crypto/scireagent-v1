"""运营台「系统状态」—— 一眼看清邮件通道、投递队列、调度心跳、数据库。

## 为什么需要这个页面

2026-10 这一个月里反复踩同类问题，每次都要进容器跑 shell 才知道：
- `EMAIL_BACKEND` 悄悄变成 console（邮件只打日志，用户收不到）
- 49 条 outbox 被误标 SENT、或长期 pending 没人投递
- cron 到底在不在跑（队列空时完全看不出来）
- 域名未验证导致 Resend 403

这些事实本该在界面上可见，而不是靠人记命令。本模块把它们变成一个 GET。

## 权限

`IsProcurementOrAdmin` —— 与运维台（`/ops/*`）同口径。内部人员需要排障，
但普通注册用户不该看到队列详情和失败原因（可能含客户邮箱片段）。
"""
import logging

from django.conf import settings
from django.db import connection
from django.db.models import Count, Max

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsProcurementOrAdmin

from apps.notifications.models import EmailOutbox
from apps.notifications.services import (
    email_delivery_is_unavailable,
    read_dispatch_heartbeat,
)

logger = logging.getLogger(__name__)

# 超过这个分钟数没心跳，就认为调度大概率停了（cron 是每分钟一次）。
# 阈值给 15 分钟是为了容忍偶发的一次失败，又不至于让"停了 2 小时"看起来正常。
STALE_MINUTES = 15


class SystemStatusView(APIView):
    """GET /api/v1/ops/system-status/ — 运营台系统状态。"""

    permission_classes = [IsProcurementOrAdmin]

    def get(self, request):
        return Response({
            'email': self._email(),
            'queue': self._queue(),
            'dispatch': self._dispatch(),
            'database': self._database(),
            'counts': self._counts(),
        }, status=status.HTTP_200_OK)

    # ── 邮件通道 ──────────────────────────────────────────────
    @staticmethod
    def _email():
        backend = getattr(settings, 'EMAIL_BACKEND', '') or ''
        return {
            'backend': backend,
            # 这是全站唯一的"邮件能不能真发出去"判据（console/dummy/filebased ⇒ 不可用）
            'delivery_available': not email_delivery_is_unavailable(),
            'from_email': getattr(settings, 'DEFAULT_FROM_EMAIL', ''),
            # 配置了谁就用谁；密钥本身绝不出现在响应里
            'provider': (
                'resend' if getattr(settings, 'RESEND_API_KEY', '')
                else 'mailgun' if getattr(settings, 'MAILGUN_API_KEY', '')
                else 'none'
            ),
        }

    # ── 投递队列 ──────────────────────────────────────────────
    @staticmethod
    def _queue():
        by_status = {
            row['status']: row['n']
            for row in EmailOutbox.objects.values('status').annotate(n=Count('id'))
        }
        recent_failures = list(
            EmailOutbox.objects
            .filter(status=EmailOutbox.Status.FAILED)
            .order_by('-id')
            .values('id', 'template_key', 'to_emails', 'retry_count', 'last_error', 'created_at')[:5]
        )
        for f in recent_failures:
            # 收件人可能是客户邮箱：只留域名部分，避免运营台页面泄露完整地址
            to = f.get('to_emails') or ''
            first = to.split(',')[0].strip()
            f['to_emails'] = ('***@' + first.split('@', 1)[1]) if '@' in first else '***'
            f['last_error'] = (f.get('last_error') or '')[:200]
        last_sent = EmailOutbox.objects.filter(
            status=EmailOutbox.Status.SENT
        ).aggregate(t=Max('sent_at'))['t']
        return {
            'counts': {
                'pending': by_status.get(EmailOutbox.Status.PENDING, 0),
                'sent': by_status.get(EmailOutbox.Status.SENT, 0),
                'failed': by_status.get(EmailOutbox.Status.FAILED, 0),
                'total': sum(by_status.values()),
            },
            'last_sent_at': last_sent.isoformat() if last_sent else None,
            'recent_failures': recent_failures,
        }

    # ── 调度心跳 ──────────────────────────────────────────────
    @staticmethod
    def _dispatch():
        iso, minutes = read_dispatch_heartbeat()
        return {
            'last_run_at': iso,
            'minutes_ago': minutes,
            'stale': (minutes is None) or (minutes > STALE_MINUTES),
            'stale_threshold_minutes': STALE_MINUTES,
            # 说清局限：心跳文件是投递命令自己写的，容器重建后首次执行前会是 None
            'note': 'heartbeat 由 send_outbox_emails 每次执行时写入；为 null 说明该命令从未在本容器内跑过',
        }

    # ── 数据库 ────────────────────────────────────────────────
    @staticmethod
    def _database():
        try:
            with connection.cursor() as cur:
                cur.execute('SELECT 1')
                cur.fetchone()
            return {'ok': True, 'vendor': connection.vendor, 'name': connection.settings_dict.get('NAME')}
        except Exception as exc:            # noqa: BLE001 - 任何异常都算 DB 不可用
            logger.warning('[ops] 系统状态：数据库探测失败', exc_info=True)
            return {'ok': False, 'vendor': connection.vendor, 'error': str(exc)[:200]}

    # ── 关键表计数（让运营对体量有数）────────────────────────
    @staticmethod
    def _counts():
        from django.contrib.auth import get_user_model
        U = get_user_model()
        out = {'users': U.objects.count(), 'users_unverified': U.objects.filter(email_verified=False).count()}
        try:
            from apps.commerce.models import Product
            out['products'] = Product.objects.count()
        except Exception:
            pass
        try:
            from apps.transactions.models import Order
            out['orders'] = Order.objects.count()
        except Exception:
            pass
        try:
            from apps.quotes.models import QuoteRequest
            out['rfq_total'] = QuoteRequest.objects.count()
            out['rfq_quoted'] = QuoteRequest.objects.filter(status='quoted').count()
        except Exception:
            pass
        return out
