"""bioz 缓存按 SC catalog_no 重键: 为可经 resolve_jena 解析到厂商货号、且已有对应
厂商键 bioz 缓存的产品, 写入 SC 键别名 (query_key=product.catalog_no)。

目的: 接通 S_B(literature 轴)。load_product_bioz 按 [catalog_no, *sku_codes](SC 内部码)
查 bioz 缓存, 而历史 bioz 缓存按厂商货号键入(如 Jena Bioscience:36544), 二者无法对齐
→ S_B 全库恒 0。本命令补 SC 键别名, 使 loader 命中。

性质:
- 只读 jena 索引(离线, 经 resolve_jena 级联 CAS→name→synonyms), 不重新抓取 Bioz;
- 仅写 DataSourceCache(幂等, 不改任何业务表);
- 依赖 crawl_bioz_jena 已跑过(厂商键 bioz 缓存已存在), 本命令只做键对齐。

用法(本地 sqlite):
  cd backend && DB_ENGINE=sqlite PYTHONDONTWRITEBYTECODE=1 \
      venv/Scripts/python.exe -B manage.py rekey_bioz_by_sc
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.commerce.models import Product
from apps.documents.models import DataSourceCache
from apps.bridges.management.commands.crawl_bioz_jena import resolve_jena

BIOZ_TTL_DAYS = 14  # 与 crawl_bioz_jena 一致


def rekey_bioz_by_sc():
    """为可解析且有厂商键 bioz 缓存的产品写 SC 键别名。返回新写入条数(幂等)。"""
    written = 0
    for p in Product.objects.values("id", "catalog_no", "name", "cas", "synonyms"):
        cat = p.get("catalog_no")
        if not cat:
            continue
        r = resolve_jena(p)
        if r is None:
            continue
        jcat, vendor = r
        src = DataSourceCache.objects.filter(
            source="bioz", query_key=f"{vendor}:{jcat}").first()
        if src is None:
            continue
        _, created = DataSourceCache.objects.update_or_create(
            source="bioz", query_key=cat, query_namespace="sku",
            defaults={
                "data_json": src.data_json,
                "expires_at": timezone.now() + timedelta(days=BIOZ_TTL_DAYS),
            },
        )
        if created:
            written += 1
    return written


class Command(BaseCommand):
    help = "Re-key bioz cache by SC catalog_no (write aliases for resolvable products)."

    def handle(self, *args, **options):
        n = rekey_bioz_by_sc()
        self.stdout.write(self.style.SUCCESS(f"bioz re-keyed for {n} products"))
