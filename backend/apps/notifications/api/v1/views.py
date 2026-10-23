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

from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.mixins import EnvelopeMixin
from core.permissions import IsProcurementOrAdmin

from apps.notifications.models import EmailOutbox, EmailTemplate
from apps.notifications.services import (
    EmailService,
    email_delivery_is_unavailable,
    read_dispatch_heartbeat,
    render_template,
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


# ══════════════════════════════════════════════════════════════════════
# 邮件模板
# ══════════════════════════════════════════════════════════════════════

class EmailTemplateRowSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailTemplate
        fields = ['key', 'subject', 'description', 'language', 'updated_at']
        read_only_fields = fields


class EmailTemplateDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailTemplate
        fields = [
            'key', 'subject', 'body_html', 'body_text',
            'description', 'language', 'updated_at',
        ]
        read_only_fields = ['key', 'updated_at']


class EmailTemplateUpdateSerializer(serializers.Serializer):
    """只允许改文案，不允许改 key（key 是代码里的契约，改了会让 enqueue 找不到模板）。"""

    subject = serializers.CharField(required=False, max_length=500, allow_blank=False)
    body_html = serializers.CharField(required=False, allow_blank=True)
    body_text = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError('Nothing to update.')
        unknown = set(self.initial_data.keys()) - {'subject', 'body_html', 'body_text', 'description'}
        if unknown:
            raise serializers.ValidationError({
                'unsupported_fields': f'不允许修改: {sorted(unknown)}。key 是代码契约，不能改。'
            })
        return attrs


def _placeholder_report(text: str, ctx: dict) -> dict:
    """渲染后检查残留占位符 —— 这是模板最常见的坏法。

    `render_template` 用 `_SafeDict`，缺失的键会被替换成空串而**不报错**，
    所以"渲染成功"不代表"没问题"：一个写错的 `{order_no}` 会静默变空。
    这里显式把残留和空值都报出来。
    """
    import re
    rendered = render_template(text or '', ctx or {})
    leftovers = sorted(set(re.findall(r'\{([a-z_][a-z0-9_]*)\}', text or '')))
    still_there = sorted(set(re.findall(r'\{([a-z_][a-z0-9_]*)\}', rendered)))
    return {
        'rendered': rendered,
        'placeholders': leftovers,
        'unrendered': still_there,
        'missing_in_ctx': [p for p in leftovers if p not in (ctx or {})],
        'empty_after_render': not rendered.strip(),
    }


class EmailTemplateListView(EnvelopeMixin, APIView):
    """GET /api/v1/ops/email-templates/"""

    permission_classes = [IsProcurementOrAdmin]

    def get(self, request):
        rows = EmailTemplateRowSerializer(
            EmailTemplate.objects.order_by('key'), many=True
        ).data
        return self.success_response(rows)


class EmailTemplateDetailView(EnvelopeMixin, APIView):
    """GET / PATCH /api/v1/ops/email-templates/<key>/"""

    permission_classes = [IsProcurementOrAdmin]

    def get(self, request, key):
        tpl = EmailTemplate.objects.filter(key=key).first()
        if not tpl:
            return Response({'detail': 'Template not found.'}, status=status.HTTP_404_NOT_FOUND)
        return self.success_response(EmailTemplateDetailSerializer(tpl).data)

    def patch(self, request, key):
        tpl = EmailTemplate.objects.filter(key=key).first()
        if not tpl:
            return Response({'detail': 'Template not found.'}, status=status.HTTP_404_NOT_FOUND)

        ser = EmailTemplateUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        for field, value in ser.validated_data.items():
            setattr(tpl, field, value)
        tpl.save(update_fields=list(ser.validated_data.keys()) + ['updated_at'])

        logger.info('[ops] 邮件模板 %s 被 %s 修改', key, request.user.pk)
        return self.success_response(EmailTemplateDetailSerializer(tpl).data)


class EmailTemplatePreviewView(EnvelopeMixin, APIView):
    """POST /api/v1/ops/email-templates/<key>/preview/ — 试渲染，不写库不发信。

    请求体可传：
      - `ctx`：自己的上下文
      - 不传则自动用**最近一条同模板的真实 outbox 记录**的 context_json ——
        比手编示例可靠得多（真实字段名、真实格式）。
      - `overrides`：临时覆盖 body/subject，用于"编辑未保存先预览"
    """

    permission_classes = [IsProcurementOrAdmin]

    def post(self, request, key):
        tpl = EmailTemplate.objects.filter(key=key).first()
        if not tpl:
            return Response({'detail': 'Template not found.'}, status=status.HTTP_404_NOT_FOUND)

        body = request.data or {}
        ctx = body.get('ctx')
        if ctx is None:
            last = EmailOutbox.objects.filter(template_key=key).order_by('-id').first()
            ctx = (last.context_json if last else {}) or {}

        subject_src = body.get('subject_override') or tpl.subject
        html_src = body.get('body_html_override')
        text_src = body.get('body_text_override')
        html_src = tpl.body_html if html_src is None else html_src
        text_src = tpl.body_text if text_src is None else text_src

        subj = _placeholder_report(subject_src, ctx)
        html = _placeholder_report(html_src, ctx)
        text = _placeholder_report(text_src, ctx)
        return self.success_response({
            'key': key,
            'ctx_used': ctx,
            'ctx_source': 'request' if body.get('ctx') is not None else 'last_outbox_record',
            'subject': subj,
            'html': html,
            'text': text,
            'warnings': [
                w for w in [
                    '有占位符在渲染后仍然存在（可能写成了 {{x}} 或嵌套花括号）'
                    if (subj['unrendered'] or html['unrendered'] or text['unrendered']) else None,
                    f'上下文中缺少: {sorted(set(html["missing_in_ctx"]) | set(text["missing_in_ctx"]))}'
                    if (html['missing_in_ctx'] or text['missing_in_ctx']) else None,
                    '渲染后正文为空' if (html['empty_after_render'] and text['empty_after_render']) else None,
                ] if w
            ],
        })


class EmailTemplateSendTestView(EnvelopeMixin, APIView):
    """POST /api/v1/ops/email-templates/<key>/send-test/ — 发一封测试信给**自己**。

    ★ 收件人固定为当前登录账号的邮箱，不接受前端指定 ——
      否则这个端点就成了"用公司域名给任意人发信"的滥发通道。
    """

    permission_classes = [IsProcurementOrAdmin]

    def post(self, request, key):
        tpl = EmailTemplate.objects.filter(key=key).first()
        if not tpl:
            return Response({'detail': 'Template not found.'}, status=status.HTTP_404_NOT_FOUND)

        to = (getattr(request.user, 'email', '') or '').strip()
        if not to:
            return Response(
                {'detail': '当前账号没有邮箱，无法发送测试信。'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        body = request.data or {}
        ctx = body.get('ctx')
        if ctx is None:
            last = EmailOutbox.objects.filter(template_key=key).order_by('-id').first()
            ctx = (last.context_json if last else {}) or {}
        # 测试信必须能点开：把链接类占位符兜底成站点地址，避免发出空链接
        ctx.setdefault('verify_url', getattr(settings, 'FRONTEND_BASE_URL', ''))
        ctx.setdefault('reset_url', getattr(settings, 'FRONTEND_BASE_URL', ''))

        if email_delivery_is_unavailable():
            return Response(
                {'detail': f'当前邮件后端 {getattr(settings, "EMAIL_BACKEND", "")} 不投递，测试信发不出去。'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 自己渲染，再以 use_template=False 入队 —— 这样"编辑未保存先试发"发的是草稿，
        # 而不是库里已存的旧版本。
        subj_src = body.get('subject_override') or tpl.subject
        html_src = body.get('body_html_override')
        text_src = body.get('body_text_override')
        html_src = tpl.body_html if html_src is None else html_src
        text_src = tpl.body_text if text_src is None else text_src

        try:
            EmailService.enqueue(
                key,
                to=[to],
                ctx=ctx,
                subject=render_template(subj_src, ctx),
                body_html=render_template(html_src, ctx),
                body_text=render_template(text_src, ctx),
                use_template=False,
            )
        except Exception as exc:      # noqa: BLE001
            logger.exception('[ops] 发送模板测试信失败 key=%s', key)
            return Response({'detail': f'发送失败: {type(exc).__name__}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return self.success_response({
            'queued': True,
            'to': to,
            'note': '已入队，cron 会在 1 分钟内投递；可在投递队列里看状态',
        })


# ══════════════════════════════════════════════════════════════════════
# 投递队列
# ══════════════════════════════════════════════════════════════════════

class EmailOutboxRowSerializer(serializers.ModelSerializer):
    to_emails = serializers.SerializerMethodField()

    class Meta:
        model = EmailOutbox
        fields = [
            'id', 'template_key', 'to_emails', 'subject', 'status',
            'retry_count', 'next_retry_at', 'sent_at', 'last_error', 'created_at',
        ]
        read_only_fields = fields

    def get_to_emails(self, obj):
        # 运营台不展示客户完整邮箱（与系统状态页口径一致）
        first = (obj.to_emails or '').split(',')[0].strip()
        return ('***@' + first.split('@', 1)[1]) if '@' in first else '***'


class EmailOutboxListView(EnvelopeMixin, APIView):
    """GET /api/v1/ops/email-outbox/?status=failed&limit=50"""

    permission_classes = [IsProcurementOrAdmin]

    def get(self, request):
        qs = EmailOutbox.objects.order_by('-id')
        st = request.query_params.get('status')
        if st in EmailOutbox.Status.values:
            qs = qs.filter(status=st)
        key = request.query_params.get('template_key')
        if key:
            qs = qs.filter(template_key=key)
        try:
            limit = min(int(request.query_params.get('limit', 50)), 300)
        except (TypeError, ValueError):
            limit = 50
        total = qs.count()
        return self.success_response(
            EmailOutboxRowSerializer(qs[:limit], many=True).data,
            meta={'pagination': {'count': total, 'limit': limit}},
        )


class EmailOutboxActionView(EnvelopeMixin, APIView):
    """POST /api/v1/ops/email-outbox/<id>/(retry|discard)/

    - `retry`：重置为 pending、清零重试次数、去掉下次重试时间 ⇒ cron 下一轮会重发
    - `discard`：标记 failed（不再重试）。用于那些明知发不出去的（比如历史空邮件）

    ⚠️ 已 `sent` 的记录**不允许重试** —— 那会重复打扰收件人。
    """

    permission_classes = [IsProcurementOrAdmin]

    def post(self, request, pk, action):
        if action not in ('retry', 'discard'):
            return Response({'detail': 'Unsupported action.'}, status=status.HTTP_400_BAD_REQUEST)

        mail = EmailOutbox.objects.filter(pk=pk).first()
        if not mail:
            return Response({'detail': 'Outbox record not found.'}, status=status.HTTP_404_NOT_FOUND)

        if mail.status == EmailOutbox.Status.SENT:
            return Response(
                {'detail': '该邮件已发送成功，不允许重试（会重复打扰收件人）。'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if action == 'retry':
            if email_delivery_is_unavailable():
                return Response(
                    {'detail': '当前邮件通道不投递，重试只会再失败一次。请先修好发信配置。'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            mail.status = EmailOutbox.Status.PENDING
            mail.retry_count = 0
            mail.next_retry_at = None
            mail.last_error = ''
            mail.save(update_fields=['status', 'retry_count', 'next_retry_at', 'last_error', 'updated_at'])
        else:
            mail.status = EmailOutbox.Status.FAILED
            mail.next_retry_at = None
            mail.save(update_fields=['status', 'next_retry_at', 'updated_at'])

        logger.info('[ops] outbox #%s 被 %s 执行 %s', pk, request.user.pk, action)
        return self.success_response({
            'id': pk, 'status': mail.status, 'action': action,
        })
