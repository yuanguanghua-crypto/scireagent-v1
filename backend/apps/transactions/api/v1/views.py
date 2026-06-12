from rest_framework import viewsets
from core.mixins import EnvelopeMixin
from apps.transactions.models import Order, Quote, Basket, Wishlist
from apps.transactions.api.v1.serializers import (
    OrderListSerializer, OrderDetailSerializer,
    QuoteListSerializer, QuoteDetailSerializer,
    BasketSerializer, WishlistSerializer,
)


class OrderViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderListSerializer
    filterset_fields = ['status']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return OrderDetailSerializer
        return OrderListSerializer


class QuoteViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    queryset = Quote.objects.prefetch_related('items').all()
    serializer_class = QuoteListSerializer
    filterset_fields = ['status']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return QuoteDetailSerializer
        return QuoteListSerializer


class BasketViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    serializer_class = BasketSerializer

    def get_queryset(self):
        if self.request.user.is_authenticated:
            return Basket.objects.filter(user=self.request.user).select_related('product', 'sku')
        return Basket.objects.none()


class WishlistViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    serializer_class = WishlistSerializer

    def get_queryset(self):
        if self.request.user.is_authenticated:
            return Wishlist.objects.filter(user=self.request.user).prefetch_related('products')
        return Wishlist.objects.none()
