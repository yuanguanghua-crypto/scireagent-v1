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
from rest_framework.exceptions import ValidationError
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
    key = request.headers.get('X-Session-Key', '')
    # 超长 key 在 Postgres 上会撞 varchar(100) 抛异常 → 500。
    # 不能截断：不同超长 key 若前 N 字符相同会被截成同一个值 ⇒ 串号风险；
    # 正常前端值是 ``guest_`` + uuid ≈ 42 字符，超长只可能是异常或攻击。
    # 上限从模型字段读取，避免将来字段改长后不同步。
    if len(key) > Basket._meta.get_field('session_key').max_length:
        raise ValidationError('Invalid X-Session-Key')
    return key


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
        # ⚠️ 光有 `skipped_count` 前端只知道"少了几条"，不知道"少的是哪几条"。
        #   故这里回传**被跳过的行的明细**，让前端能：
        #     - 用 `sku_id` 精确剔除「已合并成功」的本地行（若本地有副本）；
        #     - 用 `product_name` 在 toast 里点名是哪件没合并。
        # ⚠️ 实测修正（诚实记录）：真实链路上 localStorage 通常**没有副本**
        #   （`loadBasket()` 成功路径不写 localStorage，只有 API 失败降级才写），
        #   所以 `pruneMergedLocalItems` 的「保留被跳过行」实际从未生效。
        #   ⇒ 前端 toast 不得再暗示"已保留待重试"，只能请用户手动重新加购。
        skipped_items = []
        # ⚠️ `reason` / `product_name` 是新增的可诊断字段（只加字段，**不改**
        #   既有 `merged` / `skipped` / `skipped_items` 的字段名与语义）。
        #   前端 `pruneMergedLocalItems` 只按 `sku_id` 匹配，多出的字段对它无影响；
        #   toast 用 `reason` 区分「超上限（调小数量后可重新加购）」与
        #   「非法输入（重加也无用）」，用 `product_name` 点名具体商品。
        # ⚠️ `product_name` 在拿不到 SKU 的分支为 `None`，但**键始终存在**——
        #   前端不必判断键有无，只需对值兜底。
        for item_data in serializer.validated_data['items']:
            sku_id = item_data.get('sku_id')
            quantity = item_data.get('quantity', 1)
            if not sku_id:
                skipped_count += 1
                skipped_items.append({
                    'sku_id': sku_id, 'quantity': quantity,
                    # 拿不到 SKU ⇒ 没有名字可给；键仍保留，前端按值兜底
                    'product_name': None,
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
                    # 查不到 SKU ⇒ 没有名字可给；键仍保留，前端按值兜底
                    'product_name': None,
                    'reason': 'SKU 不存在或已下架',
                })
                continue
            except (TypeError, ValueError):
                skipped_count += 1
                skipped_items.append({
                    'sku_id': sku_id, 'quantity': quantity,
                    # SKU 查询本身失败 ⇒ 没有 sku 对象，名字无从取
                    'product_name': None,
                    'reason': 'sku_id 非法',
                })
                continue

            try:
                quantity = int(quantity)
            except (TypeError, ValueError):
                skipped_count += 1
                skipped_items.append({
                    'sku_id': sku_id, 'quantity': quantity,
                    # `sku` 已在上面查到（且 select_related 了 product）⇒ 零额外查询
                    'product_name': sku.product.name,
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
                        # 设计决策：这里曾`raise ValidationError` 让整条请求 400。
                        # 但 `mergeLocalBasket` 提交的是**整个购物车列表**
                        # （前端 stores/basket.js），于是「5 件里1 件超限」的
                        # 实际后果是：整条 400 ⇒ 前端进 catch 分支 ⇒ 5 件一件都
                        # 合并不进去；重试仍是同样 payload ⇒ 同样 400 ⇒
                        # **死循环，永久合并不了**（实测复现：两次提交均 400，
                        # 落库只有预置的那1 件）。
                        # 用「1/5 会出问题的场景」换「全部失败且不可逆」代价太大。
                        #
                        # 选「跳过」而非「静默截断」：截断会让用户拿到一个
                        # 既非其请求值、也非原值的数量（且无提示）。
                        #
                        # ⚠️ 实测更正（勿再假设"已留在本地可重试"）：真实链路上
                        # `loadBasket()` 成功路径**不写** localStorage，只有 API
                        # 失败降级才写 ⇒ 被跳过的行通常**不在** localStorage，
                        # 老 session key 又会在 merge 成功后被轮换 ⇒ 该行对用户
                        # 不可达。故前端提示必须明确要求「手动重新加购」，
                        # 不得再写 "kept for retry"（那是假话，已实测）。
                        # 本次最小修复只保证「告诉用户是哪件商品」。
                        skipped_count += 1
                        skipped_items.append({
                            'sku_id': sku_id,
                            'quantity': quantity,
                            # `sku` 在作用域内（第 255 行取的，已 select_related）
                            'product_name': sku.product.name,
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
                    # `sku` 在作用域内 ⇒ 与超限分支一致，带上商品名
                    'product_name': sku.product.name,
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
