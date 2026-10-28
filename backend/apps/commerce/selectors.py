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


def build_product_class_tree():
    """一次查询把整棵 ProductClass 读进内存，返回 `(descendant_map, l1_slug_to_id)`。

    ## 为什么需要
    `get_descendant_product_class_ids` 每次调用要 **1 + 1 + len(children)** 次查询，
    放在循环里就退化成 N+1。实测 `/api/v1/site/home` 有 **21 次**
    `SELECT id FROM product_class WHERE parent_id = N`，占该端点 51 次查询的 4 成。

    ## 语义与 `get_descendant_product_class_ids` 严格对齐
    - `descendant_map[节点 id]` = 「自身 + 全部后代」的 id 列表（与原函数同序不影响求和）
    - `l1_slug_to_id` **只收 `parent_id IS NULL` 的节点** —— 原函数对
      `slug=..., parent__isnull=True` 找不到时直接返回 `[]`，这里保持一致，
      避免"slug 命中了 L2 节点"时算出一批本不该算的后代。

    ## 防环
    数据里万一出现 `parent_id` 环（历史脏数据），朴素递归会**死循环**。
    这里用 visited 集合兜住，环上节点只收一次。
    """
    rows = list(ProductClass.objects.values_list('id', 'parent_id', 'slug'))
    children = {}
    for pk, parent, _slug in rows:
        children.setdefault(parent, []).append(pk)

    desc_map = {}
    for pk, _parent, _slug in rows:
        stack, seen = [pk], set()
        while stack:
            cur = stack.pop()
            if cur in seen:          # 防环
                continue
            seen.add(cur)
            stack.extend(children.get(cur, ()))
        desc_map[pk] = list(seen)

    l1_slug_to_id = {slug: pk for pk, parent, slug in rows if parent is None}
    return desc_map, l1_slug_to_id


# 产品搜索覆盖的字段。★ 必须与 `ProductViewSet.search_fields` 保持一致 ——
#   后者是给 DRF `SearchFilter` 看的，但 `ProductViewSet.get_queryset()` 实际走本函数，
#   所以**真正生效的是这份清单**。两处曾经不一致：
#     · 2026-10-28 修：`catalog_no` 与 `formula` 只写在 search_fields 里、这里漏了
#       ⇒ 按货号搜不到产品（实测 `search=SC8023` 返回 0 条，而该产品确实存在）。
#       货号恰恰是采购/报价/对账时最常用的检索方式，影响 `/po/submit` 明细行搜索、
#       前台搜索框等所有 `GET /products/?search=` 的调用方。
PRODUCT_SEARCH_FIELDS = ['name', 'cas', 'smiles', 'inchi', 'catalog_no', 'formula']


def filter_products(query: str = '', filters: dict = None, base_qs: QuerySet = None) -> QuerySet:
    """筛选/搜索产品

    base_qs：可选的基础 QuerySet。传入时在其之上叠加搜索/过滤，避免覆盖调用方
    已施加的可见性约束（例如视图 queryset 里的 exclude(archived=True)）。
    不传时保持原行为（从全表起）。

    搜索字段见 `PRODUCT_SEARCH_FIELDS`（全部 `icontains` 模糊匹配）。
    """
    qs = base_qs if base_qs is not None else Product.objects.select_related('product_class').all()
    if query:
        cond = Q()
        for f in PRODUCT_SEARCH_FIELDS:
            cond |= Q(**{f'{f}__icontains': query})
        qs = qs.filter(cond)
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
