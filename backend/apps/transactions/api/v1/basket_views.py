"""
Basket (shopping cart) API views.

Endpoints:
  GET    /api/v1/basket              — current basket (auth or session)
  POST   /api/v1/basket/items        — add item
  PATCH  /api/v1/basket/items/<pk>   — update quantity
  DELETE /api/v1/basket/items/<pk>/delete — remove item
  POST   /api/v1/basket/merge        — merge localStorage basket after login

All endpoints accept AllowAny so anonymous visitors can use the cart.
Anonymous users are identified by the ``X-Session-Key`` request header.
"""
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status as http_status
from apps.transactions.models import Basket
from apps.commerce.models import SKU
from .basket_serializers import (
    BasketItemSerializer,
    AddToBasketSerializer,
    UpdateBasketItemSerializer,
    MergeBasketSerializer,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_session_key(request) -> str:
    """Extract X-Session-Key header; returns empty string if missing."""
    return request.headers.get('X-Session-Key', '')


def _get_basket_queryset(request):
    """Return the basket QuerySet scoped to the current user or session."""
    if request.user.is_authenticated:
        return Basket.objects.filter(
            user=request.user
        ).select_related('product', 'sku')

    session_key = _get_session_key(request)
    if not session_key:
        return Basket.objects.none()
    return Basket.objects.filter(
        session_key=session_key, user__isnull=True
    ).select_related('product', 'sku')


def _compute_total(serializer_data) -> str:
    """Sum subtotal fields from serialized basket items."""
    from decimal import Decimal
    total = Decimal('0')
    for item in serializer_data:
        subtotal = item.get('subtotal', 0)
        total += subtotal if subtotal else Decimal('0')
    return str(total)


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

class BasketView(APIView):
    """GET — Retrieve the current basket with totals."""
    permission_classes = [AllowAny]

    def get(self, request):
        items = _get_basket_queryset(request)
        serializer = BasketItemSerializer(items, many=True)
        total = _compute_total(serializer.data)
        return Response({
            'items': serializer.data,
            'total': total,
            'count': items.count(),
        })


class AddToBasketView(APIView):
    """POST — Add a SKU to the basket (or increment if already present)."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AddToBasketSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sku_id = serializer.validated_data['sku_id']
        quantity = serializer.validated_data['quantity']
        sku = SKU.objects.select_related('product').get(id=sku_id)

        if request.user.is_authenticated:
            basket_item, created = Basket.objects.get_or_create(
                user=request.user,
                sku=sku,
                defaults={'product': sku.product, 'quantity': quantity},
            )
            if not created:
                basket_item.quantity += quantity
                basket_item.save(update_fields=['quantity', 'updated_at'])
        else:
            session_key = _get_session_key(request)
            if not session_key:
                return Response(
                    {'error': 'Session key required'},
                    status=http_status.HTTP_400_BAD_REQUEST,
                )
            basket_item, created = Basket.objects.get_or_create(
                session_key=session_key,
                sku=sku,
                user__isnull=True,
                defaults={
                    'product': sku.product,
                    'quantity': quantity,
                    'session_key': session_key,
                },
            )
            if not created:
                basket_item.quantity += quantity
                basket_item.save(update_fields=['quantity', 'updated_at'])

        return Response(
            BasketItemSerializer(basket_item).data,
            status=http_status.HTTP_201_CREATED,
        )


class UpdateBasketItemView(APIView):
    """PATCH — Update the quantity of a specific basket line item."""
    permission_classes = [AllowAny]

    def patch(self, request, pk: int):
        try:
            item = Basket.objects.select_related('product', 'sku').get(pk=pk)
        except Basket.DoesNotExist:
            return Response(
                {'error': 'Item not found'},
                status=http_status.HTTP_404_NOT_FOUND,
            )

        # Ownership check — only the basket owner can update
        if request.user.is_authenticated:
            if item.user_id != request.user.id:
                return Response(
                    {'error': 'Item not found'},
                    status=http_status.HTTP_404_NOT_FOUND,
                )
        else:
            session_key = _get_session_key(request)
            if not session_key or item.session_key != session_key:
                return Response(
                    {'error': 'Item not found'},
                    status=http_status.HTTP_404_NOT_FOUND,
                )

        serializer = UpdateBasketItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item.quantity = serializer.validated_data['quantity']
        item.save(update_fields=['quantity', 'updated_at'])
        return Response(BasketItemSerializer(item).data)


class DeleteBasketItemView(APIView):
    """DELETE — Remove a specific basket line item."""
    permission_classes = [AllowAny]

    def delete(self, request, pk: int):
        try:
            item = Basket.objects.get(pk=pk)
        except Basket.DoesNotExist:
            return Response(
                {'error': 'Item not found'},
                status=http_status.HTTP_404_NOT_FOUND,
            )

        # Ownership check
        if request.user.is_authenticated:
            if item.user_id != request.user.id:
                return Response(
                    {'error': 'Item not found'},
                    status=http_status.HTTP_404_NOT_FOUND,
                )
        else:
            session_key = _get_session_key(request)
            if not session_key or item.session_key != session_key:
                return Response(
                    {'error': 'Item not found'},
                    status=http_status.HTTP_404_NOT_FOUND,
                )

        item.delete()
        return Response(
            {'message': 'Item removed'},
            status=http_status.HTTP_200_OK,
        )


class MergeBasketView(APIView):
    """POST — Merge localStorage basket items into the DB basket after login.

    For each incoming item (sku_id + quantity), either creates a new basket
    line or increments the quantity of an existing one.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = MergeBasketSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        merged_count = 0
        for item_data in serializer.validated_data['items']:
            sku_id = item_data.get('sku_id')
            quantity = item_data.get('quantity', 1)
            if not sku_id:
                continue

            try:
                sku = SKU.objects.select_related('product').get(id=sku_id)
            except SKU.DoesNotExist:
                continue

            basket_item, created = Basket.objects.get_or_create(
                user=request.user,
                sku=sku,
                defaults={
                    'product': sku.product,
                    'quantity': int(quantity),
                },
            )
            if not created:
                basket_item.quantity += int(quantity)
                basket_item.save(update_fields=['quantity', 'updated_at'])
            merged_count += 1

        # Return the fully updated basket
        items = Basket.objects.filter(
            user=request.user
        ).select_related('product', 'sku')
        serialized = BasketItemSerializer(items, many=True)
        total = _compute_total(serialized.data)
        return Response({
            'merged': merged_count,
            'items': serialized.data,
            'total': total,
            'count': items.count(),
        })
