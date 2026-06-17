from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.quotes.models import QuoteRequest
from apps.quotes.api.v1.serializers import (
    QuoteRequestCreateSerializer,
    QuoteRequestDetailSerializer,
)


class QuoteRequestCreateView(generics.CreateAPIView):
    """POST /api/v1/quote-requests/ — 创建报价请求（无需登录）"""
    serializer_class = QuoteRequestCreateSerializer
    permission_classes = []  # AllowAny — anonymous users can submit RFQ
    authentication_classes = []

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        quote_request = serializer.save()
        # Use detail serializer for response (includes items)
        detail = QuoteRequestDetailSerializer(quote_request)
        return Response(detail.data, status=status.HTTP_201_CREATED)


class QuoteRequestDetailView(generics.RetrieveAPIView):
    """GET /api/v1/quote-requests/:id/ — 获取报价请求详情（需登录）"""
    serializer_class = QuoteRequestDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Users can only see their own quote requests
        return QuoteRequest.objects.filter(
            contact_email=self.request.user.email
        ).prefetch_related('items__product', 'items__sku')
