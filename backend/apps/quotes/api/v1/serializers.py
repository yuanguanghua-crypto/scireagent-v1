from django.db import transaction
from rest_framework import serializers
from apps.quotes.models import QuoteRequest, QuoteRequestItem


# RFQ 明细条数上限。依据：实测单游客 session 最多 4 行、单登录用户最多 6 行，
# 本地 65 个 RFQ 全部只有 1 条明细；50 ≈ 峰值 6 的 8 倍，足够覆盖正常业务，
# 同时挡住 ``items=[{}] * 50000`` 这类匿名滥用（item 四个字段均可缺省，``{}`` 合法）。
MAX_QUOTE_REQUEST_ITEMS = 50


class QuoteRequestItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', default='', read_only=True)
    sku_code = serializers.CharField(source='sku.sku_code', default='', read_only=True)

    class Meta:
        model = QuoteRequestItem
        fields = ['id', 'product_id', 'sku', 'quantity', 'note', 'product_name', 'sku_code']
        read_only_fields = ['id', 'product_name', 'sku_code']


class QuoteRequestCreateSerializer(serializers.ModelSerializer):
    items = QuoteRequestItemSerializer(
        many=True, write_only=True, max_length=MAX_QUOTE_REQUEST_ITEMS
    )

    class Meta:
        model = QuoteRequest
        fields = [
            'id', 'contact_name', 'contact_email', 'contact_phone',
            'company_name', 'country', 'notes', 'items',
        ]
        read_only_fields = ['id']

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError('At least one item is required.')
        return value

    def create(self, validated_data):
        # 整体原子：明细中途失败/超时被杀时，不能留下"半个询价单"。
        with transaction.atomic():
            items_data = validated_data.pop('items')
            request = self.context.get('request')
            user = request.user if request and request.user.is_authenticated else None
            quote_request = QuoteRequest.objects.create(user=user, **validated_data)
            for item_data in items_data:
                QuoteRequestItem.objects.create(quote_request=quote_request, **item_data)
        return quote_request


class QuoteRequestDetailSerializer(serializers.ModelSerializer):
    items = QuoteRequestItemSerializer(many=True, read_only=True)

    class Meta:
        model = QuoteRequest
        fields = [
            'id', 'contact_name', 'contact_email', 'contact_phone',
            'company_name', 'country', 'status', 'notes',
            'created_at', 'items',
        ]
        read_only_fields = fields
