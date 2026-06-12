from django.db import transaction
from .models import Product, SKU


class CommerceService:
    """商务层域服务 — 处理跨模型业务逻辑"""

    @staticmethod
    @transaction.atomic
    def create_product(validated_data: dict, skus_data: list = None) -> Product:
        """创建产品及其 SKU"""
        product = Product.objects.create(**validated_data)
        if skus_data:
            SKU.objects.bulk_create([SKU(product=product, **s) for s in skus_data])
        return product

    @staticmethod
    def search_products(query: str, filters: dict = None):
        """搜索产品"""
        from .selectors import filter_products
        return filter_products(query, filters)
