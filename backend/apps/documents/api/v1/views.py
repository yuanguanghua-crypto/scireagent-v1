from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.conf import settings
import os

from core.mixins import EnvelopeMixin
from core.permissions import IsAdminOrReadOnly
from ...models import Batch, Coa, SdsRevision, PubChemCache
from .serializers import (
    BatchSerializer, CoaSerializer, CoaQcUpdateSerializer,
    CoaApproveSerializer, CoaCreateSerializer,
    SdsRevisionSerializer, SdsGenerateSerializer, SdsApproveSerializer,
    PubChemCacheSerializer,
)
from ...services.workflow import (
    create_coa, update_coa_qc_results, approve_coa, withdraw_coa,
    generate_sds, approve_sds, withdraw_sds,
)


class BatchViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    """批次管理"""
    queryset = Batch.objects.select_related('sku', 'sku__product').all()
    serializer_class = BatchSerializer
    permission_classes = [IsAdminOrReadOnly]

    def permission_denied(self, request, message=None, code=None):
        """匿名（未认证）写操作统一返回 403，而非 DRF 默认的 401。

        仅覆盖本期 documents 视图；匿名读（SAFE_METHODS）通过权限判定，
        不会触发本方法，故仍返回 200。
        """
        raise PermissionDenied(detail=message, code=code)

    def get_queryset(self):
        qs = super().get_queryset()
        sku_id = self.request.query_params.get('sku_id')
        product_id = self.request.query_params.get('product_id')
        if sku_id:
            qs = qs.filter(sku_id=sku_id)
        if product_id:
            qs = qs.filter(sku__product_id=product_id)
        return qs


class CoaViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    """COA 管理"""
    queryset = Coa.objects.select_related('batch', 'batch__sku', 'batch__sku__product').all()
    serializer_class = CoaSerializer
    permission_classes = [IsAdminOrReadOnly]

    def permission_denied(self, request, message=None, code=None):
        """匿名（未认证）写操作统一返回 403，而非 DRF 默认的 401。

        仅覆盖本期 documents 视图；匿名读（SAFE_METHODS）通过权限判定，
        不会触发本方法，故仍返回 200。
        """
        raise PermissionDenied(detail=message, code=code)

    def get_queryset(self):
        qs = super().get_queryset()
        product_id = self.request.query_params.get('product_id')
        batch_id = self.request.query_params.get('batch_id')
        status_filter = self.request.query_params.get('status')
        if product_id:
            qs = qs.filter(batch__sku__product_id=product_id)
        if batch_id:
            qs = qs.filter(batch_id=batch_id)
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    @action(detail=False, methods=['post'], url_path='create-coa')
    def create_coa_action(self, request):
        """创建 Batch + COA 草稿"""
        ser = CoaCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            coa = create_coa(
                sku_id=ser.validated_data['sku_id'],
                lot_number=ser.validated_data['lot_number'],
                produced_at=ser.validated_data['produced_at'],
                retest_at=ser.validated_data.get('retest_at'),
            )
            return Response(CoaSerializer(coa).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['put'], url_path='qc-results')
    def update_qc_results(self, request, pk=None):
        """更新 QC 实测值"""
        coa = self.get_object()
        ser = CoaQcUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        coa = update_coa_qc_results(coa.id, ser.validated_data)
        return Response(CoaSerializer(coa).data)

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        """审批 COA + 生成 PDF"""
        coa = self.get_object()
        ser = CoaApproveSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            coa = approve_coa(
                coa.id,
                qc_analyst=ser.validated_data.get('qc_analyst', ''),
                qa_approval=ser.validated_data.get('qa_approval', ''),
            )
            return Response(CoaSerializer(coa).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='withdraw')
    def withdraw(self, request, pk=None):
        """撤回 COA → 状态回退到 draft（保留旧 PDF 文件）"""
        coa = self.get_object()
        try:
            coa = withdraw_coa(coa.id)
            return Response(CoaSerializer(coa).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'], url_path='download')
    def download(self, request, pk=None):
        """下载 COA PDF

        ★ 2026-09-22 修 B9：加**发布状态门控**。
        此前只判 `pdf_path` 是否存在，而本 ViewSet 的 `IsAdminOrReadOnly` 放行**匿名 GET**、
        `withdraw_coa` 又刻意**保留 pdf**（见 services/workflow.py:118-124），
        ⇒ 已撤回(draft) 的 COA **仍可被匿名下载**（实测 200 + application/pdf），
        违反 L1 `COA_SDS_PRD.md:80`「仅 status=PUBLISHED 允许下载」。

        口径（2026-09-22 用户拍板）：**对外一律 404；staff 仍可下载**（内部复核与审计需留痕，
        故**不删 pdf**、只加门控）。
        """
        coa = self.get_object()
        is_staff = bool(getattr(request.user, 'is_authenticated', False) and request.user.is_staff)
        if coa.status != Coa.Status.PUBLISHED and not is_staff:
            return Response({'error': '该 COA 尚未发布'}, status=status.HTTP_404_NOT_FOUND)
        if not coa.pdf_path:
            return Response({'error': 'PDF 尚未生成'}, status=status.HTTP_404_NOT_FOUND)
        filepath = os.path.join(settings.MEDIA_ROOT, coa.pdf_path)
        if not os.path.exists(filepath):
            return Response({'error': 'PDF 文件不存在'}, status=status.HTTP_404_NOT_FOUND)
        return FileResponse(
            open(filepath, 'rb'),
            content_type='application/pdf',
            filename=f'{coa.doc_id}.pdf',
        )


class SdsRevisionViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    """SDS 修订版管理"""
    queryset = SdsRevision.objects.select_related('product').all()
    serializer_class = SdsRevisionSerializer
    permission_classes = [IsAdminOrReadOnly]

    def permission_denied(self, request, message=None, code=None):
        """匿名（未认证）写操作统一返回 403，而非 DRF 默认的 401。

        仅覆盖本期 documents 视图；匿名读（SAFE_METHODS）通过权限判定，
        不会触发本方法，故仍返回 200。
        """
        raise PermissionDenied(detail=message, code=code)

    def get_queryset(self):
        qs = super().get_queryset()
        product_id = self.request.query_params.get('product_id')
        if product_id:
            qs = qs.filter(product_id=product_id)
        return qs

    @action(detail=False, methods=['post'], url_path='generate')
    def generate(self, request):
        """生成新版本 SDS（调 PubChem）"""
        ser = SdsGenerateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            sds = generate_sds(product_id=ser.validated_data['product_id'])
            return Response(SdsRevisionSerializer(sds).data, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': f'SDS 生成失败: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        """审批 SDS + 生成 PDF + 设为当前版本（B1：响应携带 compliance 合规警告）"""
        sds = self.get_object()
        try:
            sds, compliance = approve_sds(sds.id)
            data = SdsRevisionSerializer(sds).data
            data['compliance'] = compliance
            return Response(data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='withdraw')
    def withdraw(self, request, pk=None):
        """撤回 SDS → 清空 Product.current_sds 指针（PDF 文件保留）"""
        sds = self.get_object()
        try:
            sds = withdraw_sds(sds.id)
            return Response(SdsRevisionSerializer(sds).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'], url_path='download')
    def download(self, request, pk=None):
        """下载 SDS PDF"""
        sds = self.get_object()
        if not sds.pdf_path:
            return Response({'error': 'PDF 尚未生成'}, status=status.HTTP_404_NOT_FOUND)
        filepath = os.path.join(settings.MEDIA_ROOT, sds.pdf_path)
        if not os.path.exists(filepath):
            return Response({'error': 'PDF 文件不存在'}, status=status.HTTP_404_NOT_FOUND)
        return FileResponse(
            open(filepath, 'rb'),
            content_type='application/pdf',
            filename=f'SDS-{sds.product.catalog_no}-v{sds.revision_no}.pdf',
        )


class PubChemCacheViewSet(EnvelopeMixin, viewsets.ReadOnlyModelViewSet):
    """PubChem 缓存查询"""
    queryset = PubChemCache.objects.all()
    serializer_class = PubChemCacheSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        cas = self.request.query_params.get('cas')
        if cas:
            qs = qs.filter(cas_number=cas)
        return qs
