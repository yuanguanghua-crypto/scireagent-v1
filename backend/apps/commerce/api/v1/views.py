import os
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from core.mixins import EnvelopeMixin
from core.permissions import IsAdminOrReadOnly
from core.jsonld import build_product_jsonld
from apps.commerce.models import Product, SKU, ProductClass, CatalogGroup, ProductDocument
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
    ordering_fields = ['name', 'created_at', 'catalog_no']
    filterset_fields = ['product_class_id', 'status', 'category_l1', 'research_use_only']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProductDetailSerializer
        if self.action in ('create', 'update', 'partial_update'):
            return ProductCreateUpdateSerializer
        return ProductListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        query = self.request.query_params.get('search', '')
        if query:
            qs = selectors.filter_products(query)
        # Filter by category_l1
        cat1 = self.request.query_params.get('category_l1', '')
        if cat1:
            qs = qs.filter(category_l1=cat1)
        # Filter by category_l2
        cat2 = self.request.query_params.get('category_l2', '')
        if cat2:
            qs = qs.filter(category_l2__icontains=cat2)
        return qs

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
        related = get_related_products(product, limit=4)

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
