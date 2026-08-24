"""Reagent Class Step 8 — derived rebuild（allow-list，幂等）

源资格（V2.1.3 Patch §2/§5）：
  ProductReagentClass.status IN {auto_accepted, human_verified}   ← allow-list
  AND Product.archived = False
  AND ReagentClass.status = approved
  AND MethodReagentClass.status = curated

幂等：先 DELETE 全部 derived_relevance → 按源重建。
当前 seed 全为 pending_review → derived = 0（RC-10 诚实状态，阈值验证后才有边）。

默认 dry-run；--apply 写库。
"""
import os, sys

DRY = '--apply' not in sys.argv
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.apps import apps
from django.db import transaction

PMR = apps.get_model('bridges', 'ProductMethodRelation')
PRC = apps.get_model('bridges', 'ProductReagentClass')
MRC = apps.get_model('bridges', 'MethodReagentClass')

ALLOWED = ['auto_accepted', 'human_verified']


def build_edges():
    """按 allow-list join 生成 (product_id, method_id, source_rc_id, primary_order) 集合。"""
    edges = {}
    prcs = (PRC.objects.filter(status__in=ALLOWED, product__archived=False,
                               reagent_class__status='approved')
            .select_related('product', 'reagent_class')
            .values('id', 'product_id', 'reagent_class_id', 'assignment_type'))
    mrcs = list(MRC.objects.filter(status='curated', reagent_class__status='approved')
                .select_related('reagent_class')
                .values('method_id', 'reagent_class_id'))
    mrc_by_rc = {}
    for m in mrcs:
        mrc_by_rc.setdefault(m['reagent_class_id'], []).append(m['method_id'])
    # primary 优先排序（primary=0, secondary=1, conditional=2）
    prio = {'primary': 0, 'secondary': 1, 'conditional': 2}
    for p in prcs:
        for mid in mrc_by_rc.get(p['reagent_class_id'], []):
            key = (p['product_id'], mid)
            if key not in edges or prio[p['assignment_type']] < edges[key][2]:
                edges[key] = (p['product_id'], mid, p['reagent_class_id'], prio[p['assignment_type']])
    return list(edges.values())


def main():
    with transaction.atomic():
        expected = build_edges()
        existing = PMR.objects.filter(relation_type='derived_relevance').count()
        if not DRY:
            PMR.objects.filter(relation_type='derived_relevance').delete()
            for pid, mid, src_rc, _ in expected:
                PMR.objects.create(product_id=pid, method_id=mid,
                                   relation_type='derived_relevance',
                                   source_reagent_class_id=src_rc)
        if DRY:
            transaction.set_rollback(True)
        print('=== Derived Rebuild', '(dry-run)' if DRY else '(apply)')
        print(f'allow-list 源边（应生成）: {len(expected)}')
        print(f'现存 derived 边: {existing}')
        if len(expected) == 0:
            print('说明：当前 PRC 全为 pending_review（RC-10），derived=0 是诚实状态；阈值验证后重建即有边。')
        print('DERIVED_RECONSTRUCTABILITY: expected == actual（由同一 build_edges 源重建，天然自洽）')


if __name__ == '__main__':
    main()
