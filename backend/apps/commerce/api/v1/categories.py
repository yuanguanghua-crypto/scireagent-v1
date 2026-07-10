"""Product categories endpoint — DB-driven category tree with product counts.

v1 重构：从 ProductClass 自引用树动态构建，删除硬编码 CATEGORIES dict。
响应结构保持与旧版兼容，供前端 ProductLayout.vue 直接消费。
"""
from rest_framework.views import APIView
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from apps.commerce.models import Product, ProductClass as PC


class CategoryTreeView(APIView):
    """GET /api/v1/categories — 从 ProductClass 表动态构建分类树 + 产品计数。

    响应结构（与旧硬编码版逐键兼容）：
    {
        <l1_slug>: {
            'label': <l1_name>,
            'children': [<l2_name>, ...],          # 该 L1 下所有 L2 名称
            'count': <int>,                         # L1 及其后代的产品总数
            'l2_counts': {                          # 仅含 count>0 的 L2
                <l2_name>: {'count': <int>, 'id': <l2_id>, 'children': [<l3_name>, ...]}
            }
        },
        ...
    }
    注意：响应不走信封（用原生 JSONRenderer，保持与旧版兼容）。
    """
    # 绕开全局 EnvelopeRenderer，保持响应顶层为分类 dict
    renderer_classes = [JSONRenderer]

    def get(self, request):
        # 一次性加载三层树，避免 N+1
        l1s = (
            PC.objects
            .filter(parent__isnull=True)
            .order_by('sort_order', 'id')
            .prefetch_related('children__children')
        )

        result = {}
        for l1 in l1s:
            l2_children = list(l1.children.order_by('sort_order', 'id'))
            # L1 及所有后代 id
            descendant_ids = [l1.id]
            for l2 in l2_children:
                descendant_ids.append(l2.id)
                descendant_ids.extend(l2.children.values_list('id', flat=True))

            l1_count = Product.objects.filter(product_class_id__in=descendant_ids).count()

            # L2 计数（仅 count>0 进 l2_counts）
            l2_counts = {}
            for l2 in l2_children:
                cnt = Product.objects.filter(product_class=l2).count()
                if cnt > 0:
                    l3_names = list(l2.children.order_by('sort_order', 'id').values_list('name', flat=True))
                    l2_counts[l2.name] = {
                        'count': cnt,
                        'id': l2.id,
                        'children': l3_names,
                    }

            result[l1.slug] = {
                'label': l1.name,
                'children': [l2.name for l2 in l2_children],
                'count': l1_count,
                'l2_counts': l2_counts,
            }

        return Response(result)
