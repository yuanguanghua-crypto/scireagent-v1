"""RFQ（询价单）API —— 客户提交 + 内部查询。

## 两条面刻意分开（改动前先读）
1. **创建面**（`POST /quote-requests/`）：**匿名**可提交，无认证、无权限。这是获客入口。
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
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
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
    permission_classes = []  # AllowAny — anonymous users can submit RFQ
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
