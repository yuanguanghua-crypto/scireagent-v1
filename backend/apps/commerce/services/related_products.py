"""
Related Products Service
Finds related products based on shared methods and category.
"""
from django.db.models import Q, Count
from apps.commerce.models import Product


def get_related_products(product: Product, limit: int = 4) -> list[Product]:
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

    # Fallback: same category
    if product.category_l1:
        related = (
            Product.objects
            .filter(status='active')
            .exclude(id=product.id)
            .filter(category_l1=product.category_l1)
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
