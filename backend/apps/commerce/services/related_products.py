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
    """
    # Get methods linked to this product
    product_method_ids = set(
        product.product_methods.values_list('method_id', flat=True)
    )

    if product_method_ids:
        # Find products sharing the same methods
        related = (
            Product.objects
            .filter(status='active')
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
                .filter(status='active')
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
        .filter(status='active')
        .exclude(id=product.id)
        .order_by('-display_priority', 'name')
        .distinct()[:limit]
    )
