from django.db import transaction
from apps.commerce.models import Product, SKU


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
        from apps.commerce.selectors import filter_products
        return filter_products(query, filters)

    @staticmethod
    @transaction.atomic
    def activate_product(product_id: int) -> dict:
        """DRAFT→ACTIVE 唯一触发点：编排关联管线（MUST-1）。

        关联逻辑聚合到 Service 层，serializer 不直接触碰 bridges 模型。
        process_product 内部自含 transaction + 行锁（MUST-2），此处再包一层 atomic
        仅作激活边界语义标记，嵌套为 savepoint 安全。
        系统级异常（DB/code error）交由调用方（serializer）捕获记录，不阻断产品
        保持 ACTIVE —— 符合 Q2：ACTIVE 不要求成功产出边，管线故障可恢复。
        """
        from apps.bridges.services.association_service import AssociationService
        return AssociationService.process_product(product_id)
