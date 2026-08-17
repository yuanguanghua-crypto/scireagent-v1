"""S3 平价校验（只读）：新命令 recompute_auto_links 的 Top-N 选择
是否与游离脚本 _land_recompute_auto.py 已落库的 AUTO 行一致。

严格只读：全程 dry_run=True，不写任何一行。

用法：
    cd backend && DB_ENGINE=sqlite PYTHONDONTWRITEBYTECODE=1 \
        venv/Scripts/python.exe -B scripts/verify_auto_links_parity.py [产品数]
"""
import json
import os
import sys

sys.path.insert(0, os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
os.environ.setdefault('DB_ENGINE', 'sqlite')

import django  # noqa: E402

django.setup()

from apps.bridges.models import ProductProtocol as PP  # noqa: E402
from apps.bridges.services.auto_links import (  # noqa: E402
    DEFAULT_CANDIDATES_PATH, recompute_auto_links,
)
from apps.commerce.models import Product  # noqa: E402

N_PRODUCTS = int(sys.argv[1]) if len(sys.argv) > 1 else 3


def main():
    auto_qs = PP.objects.filter(link_source=PP.LinkSource.AUTO)
    total_auto = auto_qs.count()
    print(f"DB AUTO rows total = {total_auto}")
    if not total_auto:
        print("SKIP: dev 库无 AUTO 行，无法做平价校验")
        return 0

    catalogs = []
    seen = set()
    for pid in auto_qs.values_list('product_id', flat=True):
        if pid in seen:
            continue
        seen.add(pid)
        prod = Product.objects.filter(id=pid).only('catalog_no').first()
        if prod and prod.catalog_no:
            catalogs.append(prod.catalog_no)
        if len(catalogs) >= N_PRODUCTS:
            break
    print(f"selected catalogs = {catalogs}")

    print(f"loading {DEFAULT_CANDIDATES_PATH} ...")
    with open(DEFAULT_CANDIDATES_PATH, encoding='utf-8') as f:
        full = json.load(f)
    sliced = {c: full.get(c, []) for c in catalogs}
    for c in catalogs:
        print(f"  {c}: {len(sliced[c])} candidate titles")

    # 每产品旧 AUTO 行数即当时的有效 topn（可能 < 20，因跳过继承链）
    stats = recompute_auto_links(
        sliced, topn=20, model=None, dry_run=True, log=print,
    )

    print("\n=== PARITY ===")
    all_ok = True
    for cat in catalogs:
        prod = Product.objects.get(catalog_no=cat)
        old = list(
            PP.objects.filter(product=prod, link_source=PP.LinkSource.AUTO)
            .order_by('-relevance_score').values_list('protocol_id', flat=True)
        )
        new = stats['selection'].get(cat, [])
        same_set = set(old) == set(new)
        same_order = old == new
        all_ok = all_ok and same_set
        print(f"{cat}: old={len(old)} new={len(new)} "
              f"set_match={same_set} order_match={same_order}")
        if not same_set:
            print(f"  only_in_old = {sorted(set(old) - set(new))[:10]}")
            print(f"  only_in_new = {sorted(set(new) - set(old))[:10]}")

    print(f"\nAUTO rows after dry-run = "
          f"{PP.objects.filter(link_source=PP.LinkSource.AUTO).count()} "
          f"(须等于 {total_auto})")
    print("RESULT:", "PARITY OK" if all_ok else "PARITY MISMATCH")
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
