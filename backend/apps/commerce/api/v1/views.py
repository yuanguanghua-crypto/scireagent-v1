import os
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import BasePermission
from rest_framework.views import APIView
from core.mixins import EnvelopeMixin
from core.permissions import IsAdminOrReadOnly
from core.jsonld import build_product_jsonld
from apps.commerce.models import (
    Product, SKU, ProductClass, CatalogGroup, ProductDocument, AuditLog,
)


class IsSuperUser(BasePermission):
    """仅超管（is_superuser）可操作。区别于 IsAdminUser（=is_staff）。

    用于 hard-delete：物理删除是破坏性操作，必须限制在超管，普通 staff 仅能软删。
    """
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and request.user.is_superuser
        )
from apps.commerce.api.v1.serializers import (
    ProductListSerializer, ProductDetailSerializer, ProductCreateUpdateSerializer,
    SKUSerializer, ProductClassSerializer, CatalogGroupSerializer, ProductDocumentSerializer,
)
from apps.commerce import selectors

# ── File Upload Validation ──
ALLOWED_UPLOAD_EXTENSIONS = {
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.csv', '.txt', '.zip',
}
MAX_UPLOAD_SIZE_MB = 10  # 10 MB limit


def _validate_uploaded_file(file_obj):
    """Validate file extension and size. Returns error message or None."""
    ext = os.path.splitext(file_obj.name)[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        return f'File type "{ext}" is not allowed. Allowed types: {", ".join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}'
    if file_obj.size > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        return f'File size exceeds the {MAX_UPLOAD_SIZE_MB}MB limit.'
    return None


class ProductViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    queryset = Product.objects.select_related('product_class').prefetch_related('skus', 'documents').all()
    serializer_class = ProductListSerializer
    permission_classes = [IsAdminOrReadOnly]
    search_fields = ['name', 'cas', 'smiles', 'inchi', 'catalog_no', 'formula']
    ordering_fields = ['name', 'created_at', 'catalog_no', 'aggregate_relevance_score']
    filterset_fields = ['product_class_id', 'research_use_only']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProductDetailSerializer
        if self.action in ('create', 'update', 'partial_update'):
            return ProductCreateUpdateSerializer
        return ProductListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        # ── Plan B：回收站默认隐藏软删产品（仅 list 过滤）──
        # 详情类操作（retrieve/destroy/restore/hard-delete）必须能定位 archived 对象，
        # 否则已软删产品无法恢复；staff 显式 ?archived=1 在 list 中可见回收站。
        if self.action == 'list':
            show_archived = (
                self.request.query_params.get('archived') == '1'
                and user and user.is_authenticated and user.is_staff
            )
            if not show_archived:
                qs = qs.exclude(archived=True)
        query = self.request.query_params.get('search', '')
        if query:
            qs = selectors.filter_products(query)
        # Filter by category_l1 slug → recursive descendant match
        cat1 = self.request.query_params.get('category_l1', '')
        if cat1:
            ids = selectors.get_descendant_product_class_ids(cat1)
            if ids:
                qs = qs.filter(product_class_id__in=ids)
        # Filter by category_l2 name → find L2 ProductClass by name → recursive
        cat2 = self.request.query_params.get('category_l2', '')
        if cat2:
            from apps.commerce.models import ProductClass as PC
            l2_pc = PC.objects.filter(name__icontains=cat2, parent__isnull=False).first()
            if l2_pc:
                ids = selectors.get_descendant_product_class_ids(l2_pc)
                if ids:
                    qs = qs.filter(product_class_id__in=ids)
        # 非 staff（匿名/普通用户）只看 active，下架/草稿不进公开列表，
        # 且忽略客户端传入的 status 过滤参数（防止绕过）。
        if not (user and user.is_authenticated and user.is_staff):
            # 库里 status 存的是原始字符串（如 'active'），而 Product.Status.ACTIVE 是枚举成员；
            # 必须用 .value 才能匹配，否则公开列表恒为 0（预埋 bug，2026-08-10 修复）。
            qs = qs.filter(status=Product.Status.ACTIVE.value)
        return qs

    def filter_queryset(self, queryset):
        """S5 前端接入：按知识关联分排序时强制 NULLS LAST。

        DRF OrderingFilter 在 PostgreSQL 上对 DESC 默认把 NULL 排到最前，
        而 dev SQLite 排到最后。为让「知识关联最强」降序时「无关联商品沉底」
        在两种库行为一致，显式用 F(...).desc/asc(nulls_last=True) 覆盖默认排序。
        """
        qs = super().filter_queryset(queryset)
        ordering = self.request.query_params.get('ordering', '')
        if 'aggregate_relevance_score' in ordering:
            from django.db.models import F
            desc = ordering.startswith('-')
            expr = (
                F('aggregate_relevance_score').desc(nulls_last=True)
                if desc
                else F('aggregate_relevance_score').asc(nulls_last=True)
            )
            qs = qs.order_by(expr)
        return qs

    @action(detail=True, methods=['post'], url_path='archive')
    def archive(self, request, pk=None):
        """下架产品：status 置为 archived，前台不可见，保留全部数据，可恢复。"""
        product = self.get_object()
        product.status = Product.Status.ARCHIVED
        product.save(update_fields=['status'])
        serializer = self.get_serializer(product)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # ── Plan B：删除默认软归档 + 全程审计 ──────────────
    def perform_create(self, serializer):
        instance = serializer.save()
        AuditLog.log(self.request.user, AuditLog.ACTION_CREATE, instance)

    def perform_update(self, serializer):
        instance = serializer.save()
        AuditLog.log(self.request.user, AuditLog.ACTION_UPDATE, instance)

    def perform_destroy(self, instance):
        """Plan B：默认软归档（archived=True），不物理删除，可恢复 + 审计。

        注意：不调用 instance.delete()，故不会触发 post_delete 兜底信号，
        避免产生 HARD_DELETE 噪声日志。
        """
        user = getattr(self.request, 'user', None)
        AuditLog.log(user, AuditLog.ACTION_DELETE, instance)
        instance.archived = True
        instance.save(update_fields=['archived'])

    def destroy(self, request, *args, **kwargs):
        """覆盖 destroy 返回 200（避免 DRF 204 无 body + axios 兼容问题）。"""
        instance = self.get_object()
        label = str(instance)
        self.perform_destroy(instance)
        return Response(
            {'success': True, 'data': {'deleted': label, 'soft_archived': True}},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['post'], url_path='restore')
    def restore(self, request, pk=None):
        """从回收站恢复：archived=False + 审计。"""
        product = self.get_object()
        AuditLog.log(request.user, AuditLog.ACTION_RESTORE, product)
        product.archived = False
        product.save(update_fields=['archived'])
        serializer = self.get_serializer(product)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='hard-delete',
            permission_classes=[IsSuperUser])
    def hard_delete(self, request, pk=None):
        """物理删除（仅超管 IsAdminUser）。仍写审计（带操作人）；
        post_delete 兜底信号对同一对象不再重复记，避免噪声。"""
        product = self.get_object()
        AuditLog.log(request.user, AuditLog.ACTION_HARD_DELETE, product)
        product._explicit_hard_delete_logged = True  # 抑制兜底信号重复记
        product.delete()
        return Response(
            {'success': True, 'data': {'deleted': str(product), 'hard': True}},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['get'], url_path='json-ld')
    def json_ld(self, request, pk=None):
        """Return JSON-LD structured data for a single product."""
        product = self.get_object()
        data = build_product_jsonld(product, request)
        return Response(data)

    @action(detail=True, methods=['post'], url_path='documents',
            parser_classes=[MultiPartParser, FormParser])
    def upload_document(self, request, pk=None):
        """Upload a document for a product."""
        product = self.get_object()
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)
        # Validate file type and size
        validation_error = _validate_uploaded_file(file_obj)
        if validation_error:
            return Response({'error': validation_error}, status=status.HTTP_400_BAD_REQUEST)
        doc = ProductDocument.objects.create(
            product=product,
            document_type=request.data.get('document_type', 'datasheet'),
            language=request.data.get('language', 'en'),
            version=request.data.get('version', '1.0'),
            file=file_obj,
            original_filename=file_obj.name,
        )
        return Response(ProductDocumentSerializer(doc).data, status=status.HTTP_201_CREATED)

    @upload_document.mapping.get
    def list_documents(self, request, pk=None):
        """List documents for a product."""
        product = self.get_object()
        docs = product.documents.all()
        return Response(ProductDocumentSerializer(docs, many=True).data)

    @action(detail=True, methods=['post'], url_path='generate-seo')
    def generate_seo(self, request, pk=None):
        """自动生成产品 SEO 标题和描述（仅在字段为空时生成）。"""
        product = self.get_object()
        from apps.commerce.services.seo_generator import generate_seo as _gen_seo
        _, changed = _gen_seo(product)
        if changed:
            product.save(update_fields=['seo_title', 'seo_description'])
        serializer = self.get_serializer(product)
        return self.success_response(serializer.data, meta={'changed': changed})


class SKUViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    queryset = SKU.objects.select_related('product').all().order_by('id')
    serializer_class = SKUSerializer
    filterset_fields = ['product_id', 'inventory_status']
    search_fields = ['sku_code']


class ProductClassViewSet(EnvelopeMixin, viewsets.ReadOnlyModelViewSet):
    queryset = ProductClass.objects.all().order_by('sort_order', 'id')
    serializer_class = ProductClassSerializer


class CatalogGroupViewSet(EnvelopeMixin, viewsets.ReadOnlyModelViewSet):
    queryset = CatalogGroup.objects.filter(active=True).order_by('name')
    serializer_class = CatalogGroupSerializer


class ProductDocumentViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    queryset = ProductDocument.objects.select_related('product').all().order_by('-created_at')
    serializer_class = ProductDocumentSerializer
    filterset_fields = ['product_id', 'document_type']
    parser_classes = [MultiPartParser, FormParser]

    def create(self, request, *args, **kwargs):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)
        # Validate file type and size
        validation_error = _validate_uploaded_file(file_obj)
        if validation_error:
            return Response({'error': validation_error}, status=status.HTTP_400_BAD_REQUEST)
        data = request.data.copy()
        data['original_filename'] = file_obj.name
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProductDetailAPIView(EnvelopeMixin, APIView):
    """GET /api/v1/products/:id/detail/ — Aggregated product detail."""

    def get(self, request, pk):
        from django.shortcuts import get_object_or_404
        from apps.knowledge.models import Application, Method, Protocol, Reference
        from apps.bridges.models import ProductMethod, MethodProtocol, ProductReference
        from apps.commerce.api.v1.serializers_v2 import (
            ProductFullSerializer, ApplicationBriefSerializer,
            MethodBriefSerializer, ProtocolBriefSerializer,
            ReferenceBriefSerializer, RelatedProductSerializer,
            ProductBriefSerializer, FAQSerializer,
        )
        from apps.commerce.services.faq_service import generate_faq
        from apps.commerce.services.product_relationship_service import get_related_products

        product = get_object_or_404(Product, pk=pk, status__in=['active', 'published'])

        # Get related entities via bridge tables
        method_ids = list(
            ProductMethod.objects.filter(product=product).values_list('method_id', flat=True)
        )
        methods = Method.objects.filter(id__in=method_ids, status='active')
        applications = Application.objects.filter(
            methods__id__in=method_ids, status='active'
        ).distinct()

        # Protocols via MethodProtocol bridge
        protocol_ids = list(
            MethodProtocol.objects.filter(method_id__in=method_ids).values_list('protocol_id', flat=True)
        )
        protocols = Protocol.objects.filter(id__in=protocol_ids, status='published')

        # References via ProductReference bridge
        references = Reference.objects.filter(
            product_references__product=product
        )

        # Related products
        related = get_related_products(product, limit=10)

        # FAQ
        faq = generate_faq(product)

        # JSON-LD structured data for SEO
        product_data = ProductFullSerializer(product).data
        base_url = f'{request.scheme}://{request.get_host()}'
        product_data['jsonld'] = {
            '@context': 'https://schema.org',
            '@type': 'Product',
            'name': product.name,
            'description': product.overview or product.name,
            'sku': product.catalog_no or '',
            'brand': {
                '@type': 'Brand',
                'name': 'SciReagent',
            },
        }
        if product.cas:
            product_data['jsonld']['gtin13'] = product.cas
        if product.molecular_weight:
            product_data['jsonld']['weight'] = {
                '@type': 'QuantitativeValue',
                'value': product.molecular_weight,
                'unitCode': 'GRM',
            }

        return Response({
            'product': product_data,
            'applications': ApplicationBriefSerializer(applications, many=True).data,
            'protocols': ProtocolBriefSerializer(protocols, many=True).data,
            'references': ReferenceBriefSerializer(references, many=True).data,
            'related_products': related,
            'faq': faq,
            'compatibility': {
                'methods': MethodBriefSerializer(methods, many=True).data,
                'protocols': ProtocolBriefSerializer(protocols, many=True).data,
                'products': ProductBriefSerializer(
                    Product.objects.filter(id__in=[r['id'] for r in related]) if related else []
                , many=True).data,
            },
            'graph': None,
        })
