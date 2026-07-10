from django.db.models import QuerySet, Q
from .models import Product, ProductClass


def get_descendant_product_class_ids(root) -> list:
    """返回含 root 自身及其所有后代 ProductClass 的 id 列表（递归三层）。

    root 可以是 ProductClass 实例、id 或 L1 slug 字符串。
    用于按 L1/L2 过滤产品时纳入所有子节点产品。
    """
    if root is None:
        return []
    if isinstance(root, ProductClass):
        l1 = root
    elif isinstance(root, str):
        l1 = ProductClass.objects.filter(slug=root, parent__isnull=True).first()
        if not l1:
            return []
    else:
        l1 = ProductClass.objects.filter(pk=root, parent__isnull=True).first()
        if not l1:
            # root 可能是 L2/L3 id — 取其所在子树根
            node = ProductClass.objects.filter(pk=root).first()
            if not node:
                return []
            # 找到根
            while node.parent_id is not None:
                node = node.parent
            l1 = node
    ids = [l1.id]
    children = list(ProductClass.objects.filter(parent=l1))
    for child in children:
        ids.append(child.id)
        ids.extend(ProductClass.objects.filter(parent=child).values_list('id', flat=True))
    return ids


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
            pcid = filters['product_class_id']
            include_desc = filters.get('include_descendants', True)
            if include_desc:
                ids = get_descendant_product_class_ids(pcid)
                qs = qs.filter(product_class_id__in=ids) if ids else qs.filter(product_class_id=pcid)
            else:
                qs = qs.filter(product_class_id=pcid)
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
