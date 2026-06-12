from django.db.models import QuerySet, Q
from .models import Product


def filter_products(query: str = '', filters: dict = None) -> QuerySet:
    """筛选/搜索产品"""
    qs = Product.objects.select_related('product_class').all()
    if query:
        qs = qs.filter(
            Q(name__icontains=query) |
            Q(cas__icontains=query) |
            Q(smiles__icontains=query) |
            Q(inchi__icontains=query)
        )
    if filters:
        if 'product_class_id' in filters:
            qs = qs.filter(product_class_id=filters['product_class_id'])
        if 'application_id' in filters:
            qs = qs.filter(
                product_methods__method__application_id=filters['application_id']
            ).distinct()
        if 'method_id' in filters:
            qs = qs.filter(
                product_methods__method_id=filters['method_id']
            ).distinct()
    return qs


def get_product_detail(product_id: int):
    """获取产品详情（含 SKU）"""
    return Product.objects.select_related(
        'product_class', 'catalog_group'
    ).prefetch_related('skus').get(pk=product_id)
