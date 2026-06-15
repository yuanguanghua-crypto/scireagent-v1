"""
Product Relationship Service — Find related products.
Priority: same_application(+100) > same_method(+50) > same_protocol(+20) > same_product_class(+10)
"""
from apps.commerce.models import Product
from apps.knowledge.models import Application, Method
from apps.bridges.models import ProductMethod, MethodProtocol


def get_related_products(product, limit=4):
    """
    Find related products based on shared Application/Method/Protocol/Category.
    Returns: list of dicts with {id, name, catalog_no, cas, match_reason}
    """
    # Get this product's method IDs
    method_ids = list(
        ProductMethod.objects.filter(product=product).values_list('method_id', flat=True)
    )

    # Get this product's application IDs
    app_ids = list(
        Application.objects.filter(
            methods__id__in=method_ids, status__in=['active', 'published']
        ).values_list('id', flat=True).distinct()
    )

    # Get protocol IDs via MethodProtocol
    protocol_ids = list(
        MethodProtocol.objects.filter(method_id__in=method_ids).values_list('protocol_id', flat=True).distinct()
    )

    # Find candidate product IDs and scores
    scores = {}

    # Same Application (+100)
    same_app_ids = set(
        ProductMethod.objects.filter(
            method__application__id__in=app_ids
        ).exclude(product=product).values_list('product_id', flat=True)
    )
    for pid in same_app_ids:
        scores[pid] = scores.get(pid, 0) + 100

    # Same Method (+50)
    same_method_ids = set(
        ProductMethod.objects.filter(
            method_id__in=method_ids
        ).exclude(product=product).values_list('product_id', flat=True)
    )
    for pid in same_method_ids:
        scores[pid] = scores.get(pid, 0) + 50

    # Same Protocol (+20)
    same_proto_method_ids = set(
        MethodProtocol.objects.filter(protocol_id__in=protocol_ids).values_list('method_id', flat=True)
    )
    same_proto_product_ids = set(
        ProductMethod.objects.filter(
            method_id__in=same_proto_method_ids
        ).exclude(product=product).values_list('product_id', flat=True)
    )
    for pid in same_proto_product_ids:
        scores[pid] = scores.get(pid, 0) + 20

    # Same Category (+10)
    if product.product_class:
        same_class_ids = set(
            Product.objects.filter(
                product_class=product.product_class, status__in=['active', 'published']
            ).exclude(id=product.id).values_list('id', flat=True)
        )
        for pid in same_class_ids:
            scores[pid] = scores.get(pid, 0) + 10

    if not scores:
        return []

    # Sort by score descending, take top N
    sorted_ids = sorted(scores.keys(), key=lambda pid: scores[pid], reverse=True)[:limit]

    # Build result with match_reason
    products = Product.objects.filter(id__in=sorted_ids, status__in=['active', 'published'])
    product_map = {p.id: p for p in products}

    result = []
    for pid in sorted_ids:
        p = product_map.get(pid)
        if not p:
            continue
        score = scores[pid]
        if score >= 100:
            reason = 'Same Application'
        elif score >= 50:
            reason = 'Same Method'
        elif score >= 20:
            reason = 'Same Protocol'
        else:
            reason = 'Same Category'
        result.append({
            'id': p.id,
            'name': p.name,
            'catalog_no': p.catalog_no,
            'cas': p.cas,
            'match_reason': reason,
        })

    return result
