from django.db.models import Q, Count

from rest_framework import mixins, viewsets
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from core.mixins import EnvelopeMixin
from core.permissions import IsProcurementOrAdmin
from apps.inventory.models import Inventory, InventoryMovement, StockShortageAlert
from apps.inventory.services import InventoryService, InsufficientInventoryError
from apps.inventory.api.v1 import serializers as srl


def _service_error(e):
    """服务层业务错误（超卖/非法入参）→ 400，走 envelope 错误渲染。"""
    return DRFValidationError(str(e))


class InventoryViewSet(EnvelopeMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                       viewsets.GenericViewSet):
    """库存查询（内部工具：procurement/admin）。"""
    permission_classes = [IsProcurementOrAdmin]
    serializer_class = srl.InventoryListSerializer

    def get_queryset(self):
        # ⚠️ 不可在此 prefetch movements 的 slice queryset：related manager 会在 slice 上
        #    再 filter ⇒ "Cannot filter a query once a slice has been taken"（实测 500，
        #    且空表测试抓不到 —— prefetch_one_level 仅在有行时执行）。
        #    movements 仅 retrieve 需要 ⇒ 在 retrieve() 内单独全量 prefetch。
        qs = Inventory.objects.select_related('sku', 'sku__product', 'batch')
        q = self.request.query_params
        search = (q.get('search') or '').strip()
        if search:
            qs = qs.filter(Q(sku__sku_code__icontains=search) |
                           Q(sku__product__name__icontains=search))
        location = q.get('location') or ''
        if location:
            qs = qs.filter(location=location)
        low = q.get('low_stock') or ''
        if low != '':
            try:
                qs = qs.filter(available__lte=int(low))
            except ValueError:
                pass
        return qs

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return srl.InventoryDetailSerializer
        return srl.InventoryListSerializer

    def retrieve(self, request, *args, **kwargs):
        # ★ v4.1 缺陷修复：不存在的 pk 必须返回 404 而非 500。
        #   生产实测：`GET /api/v1/inventory/1/`（不存在的 pk）→ 500，
        #   堆栈 apps.inventory.models.Inventory.DoesNotExist at views.py:56。
        #   同类遗漏点在 InventoryAdjustView 已修（见下方 exists() 检查），
        #   此处补齐 —— 用 RetrieveModelMixin 的标准处理，避免直接 .get() 抛异常。
        try:
            inv = (Inventory.objects
                   .select_related('sku', 'sku__product', 'batch')
                   .prefetch_related('movements')
                   .get(pk=kwargs['pk']))
        except Inventory.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound(f"Inventory {kwargs['pk']} not found")
        return self.success_response(srl.InventoryDetailSerializer(inv).data)


class InventoryReceiptView(EnvelopeMixin, APIView):
    """入库：(sku, batch, location) 累加可分配量（无则建行），写 RECEIPT 流水。"""
    permission_classes = [IsProcurementOrAdmin]

    def post(self, request):
        ser = srl.ReceiptSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        vd = ser.validated_data
        try:
            inv = InventoryService.receipt(
                vd['sku_id'], vd['location'], vd['quantity'],
                batch_id=vd.get('batch_id'), user=request.user, reason=vd['reason'],
            )
        except (ValueError, InsufficientInventoryError) as e:
            raise _service_error(e)
        return self.success_response(srl.InventoryListSerializer(inv).data)


class InventoryAdjustView(EnvelopeMixin, APIView):
    """盘点调整：available += delta（结果不可为负），写 ADJUST 流水。"""
    permission_classes = [IsProcurementOrAdmin]

    def post(self, request, pk):
        ser = srl.AdjustSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        vd = ser.validated_data
        # ★ v4.1 对抗性自测 Fix 3：不存在库存 ID 返回 404 而非 500
        if not Inventory.objects.filter(pk=pk).exists():
            from rest_framework.exceptions import NotFound
            raise NotFound(f'Inventory {pk} not found')
        try:
            inv = InventoryService.adjust(pk, vd['delta'], user=request.user, reason=vd['reason'])
        except (ValueError, InsufficientInventoryError) as e:
            raise _service_error(e)
        return self.success_response(srl.InventoryListSerializer(inv).data)


class InventoryMovementListView(EnvelopeMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """变动流水查询（可按 inventory_id 过滤）。"""
    permission_classes = [IsProcurementOrAdmin]
    serializer_class = srl.InventoryMovementSerializer

    def get_queryset(self):
        qs = InventoryMovement.objects.select_related('inventory__sku')
        inv = self.request.query_params.get('inventory_id') or ''
        if inv.isdigit():
            qs = qs.filter(inventory_id=int(inv))
        return qs


# ── 缺货拦截告警台（2026-10-28 新增）──────────────────────────────────────────
class StockShortageAlertListView(EnvelopeMixin, APIView):
    """GET /api/v1/inventory/shortage-alerts/ — 客户因缺货被拦下的下单记录。

    运营在这里看到「谁 / 什么时候 / 想买什么 SKU / 要多少 / 当时可用多少 / 被拦几次」，
    据此决定补库存还是联系客户换产品。
    """

    permission_classes = [IsProcurementOrAdmin]

    def get(self, request):
        p = request.query_params
        qs = StockShortageAlert.objects.select_related('user', 'sku', 'handled_by')

        status_filter = (p.get('status') or '').strip()
        if status_filter:
            qs = qs.filter(status=status_filter)

        search = (p.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(sku_code__icontains=search)
                | Q(product_name__icontains=search)
                | Q(user_email__icontains=search)
                | Q(user_name__icontains=search)
            )

        try:
            page = max(1, int(p.get('page') or 1))
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = min(200, max(1, int(p.get('page_size') or 20)))
        except (TypeError, ValueError):
            page_size = 20

        total = qs.count()
        rows = qs[(page - 1) * page_size: page * page_size]

        # 徽标计数：各状态条数（4 态恒返回，前端不用兜底）
        raw = dict(StockShortageAlert.objects.values_list('status').annotate(n=Count('id')))
        counts = {choice: raw.get(choice, 0) for choice in StockShortageAlert.Status.values}

        return Response({
            'success': True,
            'data': srl.StockShortageAlertSerializer(rows, many=True).data,
            'meta': {
                'pagination': {'page': page, 'pageSize': page_size, 'count': total},
                'counts': counts,
            },
        })


class StockShortageResolveView(EnvelopeMixin, APIView):
    """POST /api/v1/inventory/shortage-alerts/{id}/resolve/ — 标记已补货/已联系/已忽略。"""

    permission_classes = [IsProcurementOrAdmin]

    def post(self, request, pk):
        from django.utils import timezone
        from django.shortcuts import get_object_or_404

        obj = get_object_or_404(StockShortageAlert, pk=pk)
        ser = srl.StockShortageResolveSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        new_status = ser.validated_data['status']

        obj.status = new_status
        note = (ser.validated_data.get('note') or '').strip()
        if note:
            obj.note = note
        if new_status == StockShortageAlert.Status.NEW:
            obj.handled_by = None
            obj.handled_at = None
        else:
            obj.handled_by = request.user
            obj.handled_at = timezone.now()
        obj.save(update_fields=['status', 'note', 'handled_by', 'handled_at', 'updated_at'])
        return self.success_response(srl.StockShortageAlertSerializer(obj).data)
