"""
Related Products Service
Finds related products based on shared methods and category.
"""
from django.db.models import Q, Count
from apps.commerce.models import Product
from apps.commerce.selectors import get_descendant_product_class_ids


def get_related_products(product: Product, limit: int = 10) -> list[Product]:
    """
    Find related products for a given product.
    Priority: same method > same category

    ★ A-101（2026-11-18）：三条分支都必须显式排除 `archived=True`。
      原因：生产 141 条产品里 **114 条是「archived=True 且 status='active'」**
      （归档只把行移入回收站，不改 status）。原实现只按 `status='active'` 过滤，
      于是回收站里的产品会出现在**前台产品详情页的「相关产品」**里，
      点进去又是 404（公开详情端点对 archived 返回 404）——「列表有、点进没有」。
      归档不是软删除语义的私事：它对**所有读路径**都意味着"不该被看到"，
      除非调用方明确是回收站/后台管理。
    """
    # Get methods linked to this product
    product_method_ids = set(
        product.product_methods.values_list('method_id', flat=True)
    )

    if product_method_ids:
        # Find products sharing the same methods
        related = (
            Product.objects
            .filter(status='active', archived=False)
            .exclude(id=product.id)
            .filter(product_methods__method_id__in=product_method_ids)
            .annotate(shared_methods=Count('product_methods__method_id', distinct=True))
            .order_by('-shared_methods', 'name')
            .distinct()[:limit]
        )
        if related:
            return list(related)

    # Fallback: same category (recursive L1/L2/L3)
    if product.product_class_id:
        ids = get_descendant_product_class_ids(product.product_class_id)
        if ids:
            related = (
                Product.objects
                .filter(status='active', archived=False)
                .exclude(id=product.id)
                .filter(product_class_id__in=ids)
                .order_by('-display_priority', 'name')
                .distinct()[:limit]
            )
            if related:
                return list(related)

    # Final fallback: any active products
    return list(
        Product.objects
        .filter(status='active', archived=False)
        .exclude(id=product.id)
        .order_by('-display_priority', 'name')
        .distinct()[:limit]
    )
