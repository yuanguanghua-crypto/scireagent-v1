"""
Serializers for the Basket (shopping cart) API.

Supports both authenticated users (identified by user FK) and
anonymous users (identified by X-Session-Key header).
"""
from decimal import Decimal
from rest_framework import serializers
from apps.transactions.models import Basket
from apps.commerce.models import SKU
from apps.commerce.services.pricing import resolve_unit_price


class BasketItemSerializer(serializers.ModelSerializer):
    """Read-only serializer for a single basket line item.

    Flattens product and SKU fields so the frontend can render
    a basket row without extra lookups.
    """
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_slug = serializers.CharField(source='product.slug', read_only=True)
    product_cas = serializers.CharField(source='product.cas', read_only=True)
    sku_code = serializers.CharField(source='sku.sku_code', read_only=True)
    pack_size = serializers.CharField(source='sku.pack_size', read_only=True)
    # ★ 2026-10-29：改走唯一取价入口（阶梯价 → 目录价兜底）。
    #   不能再用 `source='sku.price'` —— 那会让购物车永远显示 1 件价。
    unit_price = serializers.SerializerMethodField()
    currency = serializers.CharField(source='sku.currency', read_only=True)
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = Basket
        fields = [
            'id', 'product', 'product_name', 'product_slug', 'product_cas',
            'sku', 'sku_code', 'pack_size', 'unit_price', 'currency',
            'quantity', 'subtotal', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_unit_price(self, obj: Basket) -> Decimal:
        """该行在当前数量下的单价（阶梯价按**本行数量**取，不跨行合计）。"""
        return resolve_unit_price(obj.sku, obj.quantity)

    def get_subtotal(self, obj: Basket) -> Decimal:
        """小计必须与 `get_unit_price` 用同一个数，否则会出现
        「单价 × 数量 ≠ 小计」这种一眼可见的错。"""
        return resolve_unit_price(obj.sku, obj.quantity) * obj.quantity


class AddToBasketSerializer(serializers.Serializer):
    """Validate input for adding an item to the basket."""
    sku_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, max_value=999, default=1)

    def validate_sku_id(self, value: int) -> int:
        if not SKU.objects.filter(id=value).exists():
            raise serializers.ValidationError("SKU not found")
        return value


class UpdateBasketItemSerializer(serializers.Serializer):
    """Validate input for updating the quantity of a basket item."""
    quantity = serializers.IntegerField(min_value=1, max_value=999)


class MergeBasketItemSerializer(serializers.Serializer):
    """Validate one line of a guest basket submitted by the merge endpoint.

    约束与 `AddToBasketSerializer`(:49) / `UpdateBasketItemSerializer`(:59)
    完全对齐 —— merge 同样是写入 `Basket.quantity` 的入口，历史上用了裸
    `DictField()`（无 child 约束）导致任意 key-value 都能进来（实测可打成 500
    或写入负数/超大数），属疏漏而非设计。

    ⚠️ 字段集刻意只含 `sku_id` / `quantity`：前端 `stores/basket.js` 的
    `mergeLocalBasket` 在 :179-184 重新 map 后提交的也只有这两个键
    （`auth.js:58-60` 传入的三键 guestItems 是函数入参，不进 HTTP body）。
    """
    sku_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=999)


class MergeBasketSerializer(serializers.Serializer):
    """Validate input for merging localStorage basket after login."""
    items = serializers.ListField(
        child=MergeBasketItemSerializer(), allow_empty=False
    )
