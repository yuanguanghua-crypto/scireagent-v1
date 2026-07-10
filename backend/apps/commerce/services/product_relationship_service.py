"""
Product Relationship Service — Find related products.
Priority 1: Same product_class → catalog_no sort → neighbors.
Fallback: Same application/method/protocol/category scoring.
"""
from apps.commerce.models import Product
from apps.knowledge.models import Application, Method
from apps.bridges.models import ProductMethod, MethodProtocol


def get_related_products(product, limit=6):
    """
    Find related products.
    1. Match same product_class → sort by catalog_no asc → take neighbors.
    2. If fewer than limit, fall back to scoring (app/method/protocol/category).
    Returns: list of dicts with {id, name, catalog_no, cas, match_reason}
    """
    result = []

    # ── Phase 1: Same product_class neighbors ──
    if product.product_class:
        same_class_qs = Product.objects.filter(
            product_class=product.product_class,
            status__in=['active', 'published'],
        ).exclude(id=product.id).order_by('catalog_no')

        class_ids = list(same_class_qs.values_list('id', flat=True))
        if class_ids:
            # Find current product's position
            all_in_class = list(
                Product.objects.filter(
                    product_class=product.product_class,
                    status__in=['active', 'published'],
                ).order_by('catalog_no').values_list('id', flat=True)
            )
            try:
                pos = all_in_class.index(product.id)
            except ValueError:
                pos = -1

            # Take neighbors: half before, half after
            half = limit // 2
            start = max(0, pos - half)
            # Remove current product from selection
            neighbor_ids = [pid for pid in all_in_class[start:start + limit + 1] if pid != product.id]
            neighbor_ids = neighbor_ids[:limit]

            if neighbor_ids:
                neighbor_products = Product.objects.filter(id__in=neighbor_ids)
                product_map = {p.id: p for p in neighbor_products}
                for pid in neighbor_ids:
                    p = product_map.get(pid)
                    if p:
                        result.append({
                            'id': p.id,
                            'name': p.name,
                            'catalog_no': p.catalog_no,
                            'cas': p.cas,
                            'match_reason': 'Same Category',
                        })

    # ── Phase 2: Fallback scoring if not enough ──
    if len(result) >= limit:
        return result[:limit]

    existing_ids = {r['id'] for r in result}
    fallback_limit = limit - len(result)

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
        if pid not in existing_ids:
            scores[pid] = scores.get(pid, 0) + 100

    # Same Method (+50)
    same_method_ids = set(
        ProductMethod.objects.filter(
            method_id__in=method_ids
        ).exclude(product=product).values_list('product_id', flat=True)
    )
    for pid in same_method_ids:
        if pid not in existing_ids:
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
        if pid not in existing_ids:
            scores[pid] = scores.get(pid, 0) + 20

    # Same Category (+10, only for those not already in Phase 1)
    if product.product_class:
        same_class_ids = set(
            Product.objects.filter(
                product_class=product.product_class, status__in=['active', 'published']
            ).exclude(id=product.id).values_list('id', flat=True)
        )
        for pid in same_class_ids:
            if pid not in existing_ids:
                scores[pid] = scores.get(pid, 0) + 10

    if not scores:
        return result

    # Sort by score descending, take remaining slots
    sorted_ids = sorted(scores.keys(), key=lambda pid: scores[pid], reverse=True)[:fallback_limit]

    fallback_products = Product.objects.filter(id__in=sorted_ids, status__in=['active', 'published'])
    fb_map = {p.id: p for p in fallback_products}

    for pid in sorted_ids:
        p = fb_map.get(pid)
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

    return result[:limit]
