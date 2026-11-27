"""RFQ（询价单）API —— 客户提交 + 内部查询。

## 两条面刻意分开（改动前先读）
1. **创建面**（`POST /quote-requests/`）：**匿名**可提交，无认证、权限显式声明为 `AllowAny`。
   这是获客入口；放行意图写在代码里（`permission_classes = [AllowAny]`），
   不靠「没设 DEFAULT_PERMISSION_CLASSES」这类隐式默认，也不写成语义含糊的空列表 `[]`。
2. **查询面**（`GET /quote-requests/manage/`）：**仅内部人员**（`IsProcurementOrAdmin`）。
   2026-10-22 之前**没有任何查询入口** —— 详情按 `contact_email == user.email` 过滤，
   连 staff 也是 404，运营只能进 Django admin 看客户询价。本端点补的就是这个入口。

为什么权限用 `IsProcurementOrAdmin` 而不是 `IsStaffUser`：
  询价是销售/采购线索，运营侧（含 `role=procurement`，通常 `is_staff=false`）必须能看；
  本仓库同类运维端点（`organizations/manage/`、`ar/aging/`）都用这个口径。
  ⚠️ `admin/orders/` 用的是 `IsAdminUser`（只看 is_staff）—— 那是历史不一致，别照抄。

为什么详情也要放宽：内部人点开列表某一行时走的是同一个 `QuoteRequestDetailView`。
  若不放宽，列表看得见、点进去 404。
"""
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.mixins import EnvelopeMixin
from core.permissions import IsProcurementOrAdmin

from apps.notifications.services import EmailService
from apps.quotes.models import QuoteRequest
from apps.quotes.api.v1.serializers import (
    QuoteRequestCreateSerializer,
    QuoteRequestDetailSerializer,
    QuoteRequestListSerializer,
    QuoteResponseSerializer,
)

import logging

logger = logging.getLogger(__name__)


def _is_internal(user) -> bool:
    """内部人员判定 —— 与 `core/permissions.py:IsProcurementOrAdmin` **同口径**。

    抽成函数是为了让"列表准入"和"详情放宽"两处不会各写一份而漂移。
    """
    if not (user and getattr(user, 'is_authenticated', False)):
        return False
    return bool(user.is_staff or user.role in ('procurement', 'admin'))


class QuoteRequestCreateView(generics.CreateAPIView):
    """POST /api/v1/quote-requests/ — 创建报价请求（无需登录）"""
    serializer_class = QuoteRequestCreateSerializer
    permission_classes = [AllowAny]  # 匿名询价是有意公开的获客入口，显式写死放行，不用 [] 也不用隐式默认
    authentication_classes = []

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        quote_request = serializer.save()

        # 邮件通知（客户回执 + 运营提醒）。
        # ⚠️ 整段 try/except 包住：RFQ 是**获客入口**，绝不能因为邮件服务异常而丢线索。
        #    邮件失败只记日志，不影响 201 返回。
        try:
            self._notify(quote_request)
        except Exception:
            logger.exception(
                '[quotes] RFQ #%s 创建成功但邮件入队失败（已忽略，不影响提交）',
                quote_request.pk,
            )

        # Use detail serializer for response (includes items)
        detail = QuoteRequestDetailSerializer(quote_request)
        return Response(detail.data, status=status.HTTP_201_CREATED)

    @staticmethod
    def _notify(quote_request) -> None:
        """客户回执 + 运营提醒。收件人拿不到就跳过，不报错。"""
        items_count = quote_request.items.count() if hasattr(quote_request, 'items') else 0
        ctx = {
            'rfq_id': quote_request.pk,
            'contact_name': quote_request.contact_name or '',
            'contact_email': quote_request.contact_email or '',
            'company': quote_request.company_name or '—',
            'items_count': items_count,
        }

        # ① 客户回执（客户填了邮箱才发）
        if quote_request.contact_email:
            EmailService.enqueue('rfq_submitted', to=[quote_request.contact_email], ctx=ctx)

        # ② 运营提醒（配置了收件人才发；留空表示不通知）
        internal = getattr(settings, 'RFQ_NOTIFICATION_EMAILS', None) or []
        if internal:
            EmailService.enqueue('rfq_received_internal', to=internal, ctx=ctx)


class QuoteRequestDetailView(generics.RetrieveAPIView):
    """GET /api/v1/quote-requests/:id/ — 报价请求详情（需登录）

    - 内部人员（`is_staff` 或 `role∈(procurement, admin)`）：**任意** RFQ
    - 普通客户：只读 `contact_email` 与自己邮箱一致的那些
    """

    serializer_class = QuoteRequestDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = QuoteRequest.objects.prefetch_related('items__product', 'items__sku')
        if _is_internal(self.request.user):
            return qs
        # Users can only see their own quote requests
        return qs.filter(contact_email=self.request.user.email)


class QuoteRequestManageListView(EnvelopeMixin, APIView):
    """GET /api/v1/quote-requests/manage/ — 运营台「RFQ 收件箱」分页列表。

    查询参数：
      `page_size`  默认 100 / 上限 500（与 `organizations/manage/` 一致）
      `search`     模糊匹配 联系人 / 邮箱 / 公司 / 备注
      `status`     pending / reviewing / quoted / closed（非法值忽略，不报错）
    """

    permission_classes = [IsProcurementOrAdmin]

    DEFAULT_PAGE_SIZE = 100
    MAX_PAGE_SIZE = 500

    def get(self, request):
        try:
            page_size = int(request.query_params.get('page_size') or self.DEFAULT_PAGE_SIZE)
        except (TypeError, ValueError):
            page_size = self.DEFAULT_PAGE_SIZE
        # 上下夹紧：防 page_size=0（空）或超大值（一次拉全表）
        page_size = max(1, min(page_size, self.MAX_PAGE_SIZE))

        qs = QuoteRequest.objects.all().order_by('-created_at').prefetch_related('items')

        status_f = (request.query_params.get('status') or '').strip()
        if status_f in QuoteRequest.Status.values:
            qs = qs.filter(status=status_f)

        search = (request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(contact_name__icontains=search)
                | Q(contact_email__icontains=search)
                | Q(company_name__icontains=search)
                | Q(notes__icontains=search)
            )

        total = qs.count()
        rows = QuoteRequestListSerializer(qs[:page_size], many=True).data
        return self.success_response(
            rows,
            meta={'pagination': {'count': total, 'page': 1, 'page_size': page_size}},
        )


class QuoteRequestQuoteView(EnvelopeMixin, APIView):
    """POST /api/v1/quote-requests/:id/quote/ — 运营填写报价并通知客户。

    权限口径与查询面一致（`IsProcurementOrAdmin`）：销售/采购线索归运营侧管，
    含 `role=procurement` 但 `is_staff=false` 的账号。

    **状态机**：填报价即把状态推进到 `QUOTED`（已报价）。这是唯一会写该状态的入口 ——
    此前 `QUOTED` 只在枚举里定义、全仓没有任何代码会写入它（报价功能是断的）。

    邮件失败不回滚报价：报价是事实，通知是附带动作，与 COA 审批同一处理方式。
    """

    permission_classes = [IsProcurementOrAdmin]

    def post(self, request, pk):
        quote_request = QuoteRequest.objects.filter(pk=pk).first()
        if not quote_request:
            return Response(
                {'detail': 'Quote request not found.'}, status=status.HTTP_404_NOT_FOUND,
            )

        ser = QuoteResponseSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        quote_request.quoted_total = data.get('quoted_total')
        quote_request.quoted_currency = (data.get('quoted_currency') or 'USD').upper()
        quote_request.quoted_valid_until = data.get('quoted_valid_until')
        quote_request.quoted_note = data.get('quoted_note') or ''
        quote_request.quoted_at = timezone.now()
        quote_request.status = QuoteRequest.Status.QUOTED
        quote_request.save(update_fields=[
            'quoted_total', 'quoted_currency', 'quoted_valid_until',
            'quoted_note', 'quoted_at', 'status', 'updated_at',
        ])

        mailed = False
        if data.get('notify_customer', True) and quote_request.contact_email:
            try:
                items_count = quote_request.items.count()
                total = quote_request.quoted_total
                EmailService.enqueue(
                    'quote_ready',
                    to=[quote_request.contact_email],
                    ctx={
                        'rfq_id': quote_request.pk,
                        'contact_name': quote_request.contact_name or 'there',
                        'items_count': items_count,
                        'quoted_total': f'{total:,.2f}' if total is not None else '—',
                        'quoted_currency': quote_request.quoted_currency,
                        'quoted_valid_until': (
                            str(quote_request.quoted_valid_until)
                            if quote_request.quoted_valid_until else '—'
                        ),
                        'quoted_note': quote_request.quoted_note or '',
                    },
                )
                mailed = True
            except Exception:
                logger.exception(
                    '[quotes] RFQ #%s 报价已保存但通知邮件入队失败（报价不回滚）',
                    quote_request.pk,
                )

        return self.success_response({
            'id': quote_request.pk,
            'status': quote_request.status,
            'quoted_total': str(quote_request.quoted_total) if quote_request.quoted_total is not None else None,
            'quoted_currency': quote_request.quoted_currency,
            'customer_notified': mailed,
        })


class QuoteRequestCloseView(EnvelopeMixin, APIView):
    """POST /api/v1/quote-requests/<id>/close/ —— 关闭询价（A-223，2026-11-26 新增）。

    ## 改前是什么样
    已报价的 RFQ **没有任何关闭入口**（QA Batch 16 实测：RFQ #10 状态 `quoted`，
    详情面板找不到关闭按钮）。`Status.CLOSED` 在枚举里定义了，但**全仓没有写它的
    代码路径** —— 与 `QUOTED` 当年"枚举有、能力无"的情况完全一样。

    后果：收件箱只增不减。客户撤回、重复提交、明显无效的询价都清不出去，
    运营的待办列表会一直堆着已经处理完的单子。

    ## 状态机
    `pending` / `quoted` → `closed`；已 `closed` 再关 ⇒ **409**（幂等，不重复写）。
    为什么允许从 `pending` 关闭：垃圾询价/客户撤回也要能清出去，
    否则"待处理"这个数字永远只增不减。

    ## 留痕
    可选 `reason` 追加到 `notes`（前缀 `[关闭]`）。不覆盖原备注 ——
    客户填的需求描述是原始事实，不能被后加的运营备注冲掉。
    """

    permission_classes = [IsProcurementOrAdmin]

    def post(self, request, pk):
        q = get_object_or_404(QuoteRequest, pk=pk)
        if q.status == QuoteRequest.Status.CLOSED:
            return self.error_response(
                '该询价已关闭，无需重复操作。', code='ALREADY_CLOSED', status_code=409,
            )

        reason = (request.data.get('reason') or '').strip()
        q.status = QuoteRequest.Status.CLOSED
        if reason:
            q.notes = (q.notes + '\n' if q.notes else '') + f'[关闭] {reason}'
            q.save(update_fields=['status', 'notes'])
        else:
            q.save(update_fields=['status'])

        return self.success_response(QuoteRequestDetailSerializer(q).data)


class QuoteRequestStartReviewView(EnvelopeMixin, APIView):
    """POST /api/v1/quote-requests/<id>/review/ —— 把询价标为「审核中」（A-020，P0）。

    ## 改前是什么样
    状态枚举里有 `reviewing`，但**没有任何写入口**（QA 三批均报：「三处 RFQ 详情均无
    状态修改入口；Pending 无法改为 Reviewing」）。运营拿到一条询价后无法表示
    "我已经在看这条了"，收件箱里 pending 与"没人管"永远分不开。

    ## 状态机
    只允许 `pending` → `reviewing`。已在 reviewing 或更往后 ⇒ **409**（幂等，不重复写）。
    为什么不做成通用 status setter：`quoted` 必须由填报价动作产生（要带金额/通知客户），
    `closed` 有专门的 close 端点（带原因、幂等）。开放一个任意 setter 等于绕过这些闸门。
    """

    permission_classes = [IsProcurementOrAdmin]

    def post(self, request, pk):
        q = get_object_or_404(QuoteRequest, pk=pk)
        if q.status == QuoteRequest.Status.REVIEWING:
            return self.error_response(
                '该询价已在审核中，无需重复操作。', code='ALREADY_REVIEWING', status_code=409,
            )
        if q.status != QuoteRequest.Status.PENDING:
            return self.error_response(
                f'当前状态为 {q.status}，只有待处理（pending）的询价可以转为审核中。',
                code='INVALID_TRANSITION', status_code=409,
            )
        q.status = QuoteRequest.Status.REVIEWING
        q.save(update_fields=['status'])
        return self.success_response(QuoteRequestDetailSerializer(q).data)


class QuoteRequestRespondView(EnvelopeMixin, APIView):
    """POST /api/v1/quote-requests/<id>/respond/ —— 客户接受 / 拒绝报价（A-264）。

    body: `{"action": "accept" | "reject", "note": "可选说明"}`

    ## 改前是什么样
    枚举里**没有** accepted / rejected，客户侧四个页面（/orders、/po/orders、
    /po/reorder、/po/downloads）也没有任何入口 ⇒ 「收到报价后答复」这件事
    在整个系统里无处表达。运营只能靠邮件/电话私下确认，系统里永远停在 `quoted`。

    ## 归属与状态机
    - 只有**该询价的客户本人**（`user` 是自己，或 `contact_email` 与自己邮箱一致）能答复；
    - 只有 `quoted` 状态可答复（未报价 / 已答复 ⇒ 409，幂等）；
    - 答复后状态变 `accepted` / `rejected`，并记录 `customer_responded_at`。
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        action = (request.data.get('action') or '').strip().lower()
        if action not in ('accept', 'reject'):
            return self.error_response(
                "action 必须是 'accept' 或 'reject'。", code='INVALID_ACTION', status_code=400,
            )

        q = get_object_or_404(QuoteRequest, pk=pk)
        user = request.user
        mine = (q.user_id and q.user_id == user.id) or (
            q.contact_email and user.email and q.contact_email.lower() == user.email.lower()
        )
        if not mine and not _is_internal(user):
            # 不区分"不存在"与"不是你的"，避免探测他人 RFQ 是否存在
            return self.error_response(
                'Quote request not found.', code='NOT_FOUND', status_code=404,
            )

        if q.status != QuoteRequest.Status.QUOTED:
            return self.error_response(
                f'当前状态为 {q.status}，只有已报价（quoted）的询价可以答复。',
                code='INVALID_TRANSITION', status_code=409,
            )

        note = (request.data.get('note') or '').strip()
        q.status = (
            QuoteRequest.Status.ACCEPTED if action == 'accept'
            else QuoteRequest.Status.REJECTED
        )
        q.customer_responded_at = timezone.now()
        fields = ['status', 'customer_responded_at']
        if note:
            # 追加而不是覆盖：客户填的需求描述是原始事实
            label = '[客户接受]' if action == 'accept' else '[客户拒绝]'
            q.notes = (q.notes + '\n' if q.notes else '') + f'{label} {note}'
            fields.append('notes')
        q.save(update_fields=fields)
        return self.success_response(QuoteRequestDetailSerializer(q).data)


class MyQuoteRequestListView(EnvelopeMixin, APIView):
    """GET /api/v1/quote-requests/mine/ —— 我提交过的询价（A-170）。

    ## 改前是什么样
    客户侧 `/orders` 只列订单，**没有 RFQ 入口**（QA Batch 15：RFQ #11 明明能通过
    `GET /quote-requests/11/` 取到 200，界面上却没有任何入口）。运营报了价，客户
    既看不到、也不知道该去哪看。

    ## 归属口径
    与详情端点一致：`user` 是自己 **或** `contact_email` 与自己邮箱一致（历史上
    有些 RFQ 是匿名提交后补绑用户的）。按 `-created_at` 排序。
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        qs = (QuoteRequest.objects
              .prefetch_related('items__product', 'items__sku')
              .filter(Q(user=user) | Q(contact_email__iexact=user.email or ''))
              .order_by('-created_at'))
        return self.success_response(QuoteRequestDetailSerializer(qs, many=True).data)
