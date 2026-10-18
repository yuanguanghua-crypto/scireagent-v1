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
    """Return the basket QuerySet scoped to the current user or session.

    S5.3：**读取侧过滤**掉指向已归档（回收站）产品的行 —— 产品软删不级联清理 `basket`
    （FK 是 CASCADE，但软删不触发），故购物车会残留"已下架"行（实测生产 5 条）。
    这里只过滤、**不删数据**（不做级联删除）；失效行仍留在库中。
    """
    if request.user.is_authenticated:
        return Basket.objects.filter(
            user=request.user, product__archived=False
        ).select_related('product', 'sku')

    session_key = _get_session_key(request)
    if not session_key:
        return Basket.objects.none()
    return Basket.objects.filter(
        session_key=session_key, user__isnull=True, product__archived=False
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

    #: 与 `MergeBasketItemSerializer.quantity` 的 max_value 对齐 —— 叠加后的
    #: 单行总量同样不得突破它（实测修复前 900 + 900 = 1800 可落库）。
    max_line_quantity = 999

    def post(self, request):
        serializer = MergeBasketSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        merged_count = 0
        skipped_count = 0
        #⚠️ 光有 `skipped_count` 前端无法做到「只清已成功合并的行」——
        #   它只知道"少了几条"，不知道"少的是哪几条"。而 localStorage 的
        #   清理是整键 removeItem，一旦部分跳过就会把没合并的行一并抹掉
        #   （实测后果：那些商品既没进账户、也没留在本地，彻底丢失）。
        #   故这里额外回传**被跳过的行的标识**，让前端能精确保留它们。
        skipped_items = []
        # ⚠️ `reason` 是本次新增的可诊断字段（只加字段，**不改**既有
        #   `merged` / `skipped` / `skipped_items` 的字段名与语义）。
        #   前端 `pruneMergedLocalItems` 只按 `sku_id` 匹配，多出 `reason`
        #   对它无影响；但 toast 可以据此区分「超上限（调小数量即可重试）」
        #   与「非法输入（重试无用）」。
        for item_data in serializer.validated_data['items']:
            sku_id = item_data.get('sku_id')
            quantity = item_data.get('quantity', 1)
            if not sku_id:
                skipped_count += 1
                skipped_items.append({
                    'sku_id': sku_id, 'quantity': quantity,
                    'reason': '缺少 sku_id',
                })
                continue

            # ⚠️ 第二道防线：`MergeBasketItemSerializer` 已把输入约束成
            # (int>=1, 1<=quantity<=999)，但**不能只依赖它**。实测四类 500 的
            # 真实炸点分散在三层，光包 `int()` 挡不住：
            #   A/C sku_id 非法 → `SKU.get()` 在 Django `IntegerField
            #       .get_prep_value` 里 `int()` 抛 ValueError（:224）
            #   B     quantity 非法 → 裸 `int()` 抛 ValueError（:233）
            #   D     quantity 超大整数 → `int()` **不抛**，炸在
            #       `get_or_create` 的 DB 写入（sqlite3: Python int too large）
            # 故这里必须把 SKU 查询与整个写库过程一并兜住，跳过并计数，
            # 语义与既有的 `SKU.DoesNotExist → continue` 保持一致。
            try:
                sku = SKU.objects.select_related('product').get(id=sku_id)
            except SKU.DoesNotExist:
                skipped_count += 1
                skipped_items.append({
                    'sku_id': sku_id, 'quantity': quantity,
                    'reason': 'SKU 不存在或已下架',
                })
                continue
            except (TypeError, ValueError):
                skipped_count += 1
                skipped_items.append({
                    'sku_id': sku_id, 'quantity': quantity,
                    'reason': 'sku_id 非法',
                })
                continue

            try:
                quantity = int(quantity)
            except (TypeError, ValueError):
                skipped_count += 1
                skipped_items.append({
                    'sku_id': sku_id, 'quantity': quantity,
                    'reason': 'quantity 非法',
                })
                continue

            try:
                basket_item, created = Basket.objects.get_or_create(
                    user=request.user,
                    sku=sku,
                    defaults={
                        'product': sku.product,
                        'quantity': quantity,
                    },
                )
                if not created:
                    if basket_item.quantity + quantity > self.max_line_quantity:
                        # ⚠️ 叠加会突破上限 ⇒ **跳过该行**而非整条400。
                        #
                        # 设计决策（本次变更）：这里曾`raise ValidationError`
                        # 让整条请求 400。但 `mergeLocalBasket` 提交的是
                        # **整个购物车列表**（前端 stores/basket.js:185），于是
                        # 「5 件里1 件超限」的实际后果是：
                        #   - 整条 400 ⇒ 前端进 catch 分支 ⇒ 5 件一件都
                        #     合并不进去，全部留在 localStorage 等重试；
                        #   - 重试仍是同样 payload ⇒ 同样 400 ⇒ **死循环，
                        #     永久合并不了**（实测复现：两次提交均 400，
                        #     落库只有预置的那1 件）。
                        # 用「1/5 会出问题的场景」换「全部失败且不可逆」代价太大。
                        #
                        # 选「跳过」而非「静默截断」：截断会让用户拿到一个
                        # 既非其请求值、也非原值的数量（提示不足）；整条拒绝的
                        # 缺陷是损害不可逆。两者瑕疵方向不同，此处取损害可逆
                        # 的一档 —— 被跳过的行会留在 localStorage（前端
                        # `pruneMergedLocalItems` 只剔除已确认合并成功的行），
                        # 用户自行调整数量后可重试，天然无累积问题。
                        skipped_count += 1
                        skipped_items.append({
                            'sku_id': sku_id,
                            'quantity': quantity,
                            # 带上下文以便前端区分「超上限」与「非法输入」
                            'reason': (
                                f'合并后数量将超过上限 {self.max_line_quantity}'
                                f'（已有 {basket_item.quantity} + 本次 {quantity}）'
                            ),
                        })
                        continue
                    basket_item.quantity += quantity
                    basket_item.save(update_fields=['quantity', 'updated_at'])
            except (TypeError, ValueError, OverflowError):
                skipped_count += 1
                skipped_items.append({
                    'sku_id': sku_id, 'quantity': quantity,
                    'reason': '写入购物车失败',
                })
                continue
            merged_count += 1

        # Return the fully updated basket
        items = Basket.objects.filter(
            user=request.user
        ).select_related('product', 'sku')
        serialized = BasketItemSerializer(items, many=True)
        total = _compute_total(serialized.data)
        return Response({
            'merged': merged_count,
            # 让前端能感知"部分合并失败"，而不是看到 merged 就以为全部成功。
            'skipped': skipped_count,
            # ⚠️ 与 `skipped` 配对使用：只有计数时前端无法判断**哪些**行没合并，
            #   也就无法"只清成功行、保留失败行"（见循环内 skipped_items 注释）。
            'skipped_items': skipped_items,
            'items': serialized.data,
            'total': total,
            'count': items.count(),
        })
