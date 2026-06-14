from rest_framework import serializers
from apps.quotes.models import QuoteRequest, QuoteRequestItem


class QuoteRequestItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', default='', read_only=True)
    sku_code = serializers.CharField(source='sku.sku_code', default='', read_only=True)

    class Meta:
        model = QuoteRequestItem
        fields = ['id', 'product_id', 'sku', 'quantity', 'note', 'product_name', 'sku_code']
        read_only_fields = ['id', 'product_name', 'sku_code']


class QuoteRequestCreateSerializer(serializers.ModelSerializer):
    items = QuoteRequestItemSerializer(many=True, write_only=True)

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
