"""诊断：本地 sqlite 能否持久化 Bioz 缓存写（DataSourceCache 表 + set/get_cache）。

只做 1 次真实 Bioz 查询 + 1 次写 + 1 次读，验证 round-trip。不改业务数据。
若打印 'cache round-trip OK' 说明本地可持久化，可安全跑全量 crawl_bioz_jena；
若打印 'cache set skipped' 警告或 round-trip 失败，说明本地 DB 迁移漂移，需另寻路径。
"""
from django.core.management.base import BaseCommand
from apps.knowledge.services.bioz_client import BiozClient
from apps.documents.services.datasource_cache import get_cache, set_cache


class Command(BaseCommand):
    help = "Diagnose Bioz cache persistence on local DB."

    def handle(self, *args, **opt):
        cat = "NU-1138"
        vendor = "Jena Bioscience"
        key = f"{vendor}:{cat}"
        self.stdout.write(f"query bioz {key} ...")
        recs = BiozClient().search_by_sku(cat, vendor)
        self.stdout.write(f"  got {len(recs)} records (cached write attempted inside client)")

        reread = get_cache("bioz", key, "sku")
        if reread is not None and not reread.is_stale:
            data = reread.get_data()
            if data is not None and len(data) == len(recs):
                self.stdout.write(self.style.SUCCESS(
                    f"cache round-trip OK: {len(data)} records persisted"))
                return
        # 显式再 set 一次，看是否抛错/被吞
        try:
            set_cache("bioz", key, "sku", recs)
            reread2 = get_cache("bioz", key, "sku")
            if reread2 is not None and reread2.get_data() is not None:
                self.stdout.write(self.style.SUCCESS(
                    f"explicit set+get OK: {len(reread2.get_data())} records"))
            else:
                self.stdout.write(self.style.ERROR("round-trip FAILED: reread empty after set"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"set_cache raised: {e}"))
