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
    # ★ 2026-10-21 只读化（F4，P2 孤儿写口）：此前是完整 ModelViewSet，且**无
    #   `perform_create`** ⇒ 登录用户 `POST /orders/` 可造出 `user=NULL` 的**孤儿订单**
    #   （谁都不拥有、审核台永远查不到）；`order_no` 又没标 read_only 且 `unique=True`
    #   无默认值 ⇒ 不传就 IntegrityError → 500；还能顺手写 payment_method / po_number。
    #   前端对 `/orders/` **只有 GET**（api/orders.js、api/poPortal.js、api/adminPo.js
    #   全是 http.get，全仓无 `post('/orders/'`）⇒ 写口是**孤儿**，只读化零功能损失。
    #   真实下单入口：`CheckoutView`（结账）与 `POSubmitView`（/orders/po/），均自带
    #   服务层校验（收件人、SKU、价格覆盖、订单号生成）。
    #   ⇒ 写方法一律 405。注意 DRF 语义：dispatch() 先 check_permissions() 再查方法
    #      ⇒ 匿名写仍是 401（非 405），见同文件 QuoteViewSet:50-54 的同一做法。
    http_method_names = ['get', 'head', 'options']
    serializer_class = OrderListSerializer
    # ★ 2026-10-21 修 D1（P0，全站测试发现）：此前只有 `['status']`，而
    #   `/ops/po/organizations` 的「订单查看」传的是 `organization_id`（`api/adminPo.js:94`）
    #   ⇒ 该参数被 **DjangoFilterBackend 静默丢弃**，右侧表格显示**全库订单**（实测 937/983 单），
    #   与所选机构无关 ⇒ 跨机构订单可见。
    #   两种写法都收：`organization_id`（前端现用、也是本仓库既有惯例，同
    #   `commerce/api/v1/views.py:59` 的 `product_class_id`）+ `organization`（FK 字段规范名）。
    #   ⚠️ 不会造成提权：`get_queryset()` 先按用户收窄（客户只看自己的），过滤只在其**之上**再收窄。
    #   回归测试：`apps/transactions/tests/test_cross_org_visibility.py::OrderOrganizationFilterTest`
    filterset_fields = ['status', 'organization', 'organization_id']
    # ★ 2026-09-24 收紧：此前未声明权限 ⇒ 匿名可写 `POST /orders/`（实测可造 `user=null` 的订单）。
    #   2026-10-21 F4 起写口**整体关闭**（`http_method_names` 只读），此条仅描述读契约。
    #   读维持原契约（匿名 GET → 200 空列表，`get_queryset` 已 `.none()`）。
    permission_classes = [AllowAny]

    def get_permissions(self):
        # 读（list/retrieve）维持匿名空列表契约（`get_queryset` 已 `.none()`）。
        # ★ 2026-10-21 F4：写方法已被 `http_method_names` 拦成 405，下面这个
        #   `IsAuthenticated()` 分支对 create/update/destroy **已不可达**；
        #   保留它是纵深防御 —— DRF 的 `dispatch()` 先 `check_permissions()` 再查方法，
        #   所以匿名 POST 仍是 401（不暴露写口），而非 405。
        if self.action in ('list', 'retrieve'):
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Order.objects.none()
        # ★ 2026-10-22：列表序列化器新增 `invoice` / `attachments` 字段（修下载中心空态），
        #   这里必须一并 select_related/prefetch，否则每行多 2 次查询（客户 100 单 = 200 次）。
        base = (Order.objects
                .select_related('invoice')
                .prefetch_related('attachments', 'items', 'invoice__payments'))
        # ★ 2026-10-14 修：内部人员（is_staff 或 procurement/admin）跨机构可见所有订单（审核台），
        #   客户仍只看自己的。此前仅 is_staff 可见全量 ⇒ procurement（非 staff）审核台空列表。
        if user.is_staff or user.role in ('procurement', 'admin'):
            return base.order_by('-created_at')
        return base.filter(user=user).order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return OrderDetailSerializer
        return OrderListSerializer


class QuoteViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    # ★ 2026-10-15 只读化：create 会落到 QuoteListSerializer（fields 不含 items/联系字段）
    #   ⇒ **已登录** POST /quotes/ 会建出「quote_no=null、grand_total=0.00、无 items」的**空壳单**（实测 201）。
    #   客户侧真实询价入口是 /quote-requests/（apps/quotes）；前端对 /quotes/ 只做 GET（api/poPortal.js:15）。
    #   ⇒ 写方法一律 405。注意 DRF 语义：dispatch() 先 check_permissions() 再查方法 ⇒ 匿名写仍 401（非 405）。
    http_method_names = ['get', 'head', 'options']
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
        if user.is_staff or user.role in ('procurement', 'admin'):
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
