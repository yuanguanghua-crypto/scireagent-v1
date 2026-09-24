from rest_framework import viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from core.mixins import EnvelopeMixin
from apps.transactions.models import Order, Quote, Basket, Wishlist
from apps.transactions.api.v1.serializers import (
    OrderListSerializer, OrderDetailSerializer,
    QuoteListSerializer, QuoteDetailSerializer,
    BasketSerializer, WishlistSerializer,
)


class OrderViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    serializer_class = OrderListSerializer
    filterset_fields = ['status']
    # ★ 2026-09-24 收紧：此前未声明权限 ⇒ 匿名可写 `POST /orders/`（实测可造 `user=null` 的订单）。
    #   真实下单路径**本就要求登录**（`CheckoutView`/`POSubmitView` 均 `IsAuthenticated`）
    #   ⇒ 本 CRUD 的写口要求登录，与之一致；读维持原契约（匿名 GET → 200 空列表，`get_queryset` 已 `.none()`）。
    permission_classes = [AllowAny]

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Order.objects.none()
        if user.is_staff:
            return Order.objects.all().order_by('-created_at')
        return Order.objects.filter(user=user).order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return OrderDetailSerializer
        return OrderListSerializer


class QuoteViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    serializer_class = QuoteListSerializer
    filterset_fields = ['status']
    # ★ 2026-09-24 同 OrderViewSet：读维持匿名空列表契约，**写要求登录**。
    permission_classes = [AllowAny]

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Quote.objects.none()
        if user.is_staff:
            return Quote.objects.prefetch_related('items').all().order_by('-created_at')
        return Quote.objects.filter(user=user).prefetch_related('items').order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return QuoteDetailSerializer
        return QuoteListSerializer


class BasketViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    # ★ 2026-09-24 显式声明 —— 但**本类是死代码**：全仓 grep 显示它**未被任何 urls 路由**
    #   （真正生效的购物车端点在 `basket_views.py`：`/basket`、`/basket/items` …，且那句已显式 AllowAny）。
    #   保留显式 `AllowAny` 仅用于消除"隐式即公开"这一族隐患；**待删除**（删前确认无外部引用）。
    permission_classes = [AllowAny]
    serializer_class = BasketSerializer

    def get_queryset(self):
        if self.request.user.is_authenticated:
            return Basket.objects.filter(user=self.request.user).select_related('product', 'sku')
        return Basket.objects.none()


class WishlistViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    serializer_class = WishlistSerializer

    # ★ 2026-09-24 修「匿名 POST 必 500」+ 收紧写面：
    #   根因：本类此前**未声明权限**（⇒ AllowAny），而 `Wishlist.user` 是 **NOT NULL**、
    #   `WishlistSerializer` 又**不含 `user`** ⇒ 匿名（乃至任何）`POST /wishlist/` 都会
    #   `IntegrityError: NOT NULL constraint failed: wishlist.user_id` ⇒ **HTTP 500**
    #   （2026-09-24 已实测）。权限口径与模型约束**自相矛盾**。
    #   修法：**读维持原契约**（匿名 GET → 200 空列表，`test_list_unauthenticated_returns_empty` 在案
    #   ⇒ 不能用一刀切 `IsAuthenticated`），**写要求登录**；并在 `perform_create` 强制归属，
    #   使登录用户的创建不再 500、且**无法**为他人创建收藏。
    permission_classes = [AllowAny]   # 兜底；实际按方法分流见 get_permissions()

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [AllowAny()]           # 匿名可读（queryset 已 `.none()` ⇒ 空列表）
        return [IsAuthenticated()]        # create/update/partial_update/destroy 必须登录

    def perform_create(self, serializer):
        # 归属由服务端决定，不接受客户端指定（serializer 本就不含 user 字段）
        serializer.save(user=self.request.user)

    def get_queryset(self):
        if self.request.user.is_authenticated:
            return Wishlist.objects.filter(
                user=self.request.user
            ).prefetch_related('products').order_by('-created_at')
        return Wishlist.objects.none()
