"""只读探测配套：对全部 jena 命中产品实抓 Bioz 文献，写入 DataSourceCache。

目的：把"Bioz 辅助信号"铺满，供 probe_protocol_relevance_v3 复跑看到最终分布。
铁律①要求 Bioz 覆盖从"仅 18/106 曾 enrich"扩到"全部 jena 命中产品"。

严格只写 DataSourceCache（bioz 证据缓存，14 天 TTL，幂等），不改任何业务表。
BiozClient.search_by_sku 内部已做 set_cache 持久化 + 2 req/s 限速。

用法（本地 sqlite，需网络）：
  cd backend && DB_ENGINE=sqlite PYTHONDONTWRITEBYTECODE=1 \
      venv/Scripts/python.exe -B manage.py crawl_bioz_jena [--force]
  --force  忽略已缓存(non-stale)结果，强制重新抓取
"""
import sys
from django.core.management.base import BaseCommand

from apps.commerce.models import Product
from apps.knowledge.services.bioz_client import BiozClient
from apps.commerce.services.jena_matcher import match_jena, _looks_like_cas

# jena 索引 vendor(小写) -> Bioz cx 参数
VENDOR_MAP = {
    "jena": "Jena Bioscience",
    "cayman": "Cayman Chemical",
    "trilink": "TriLink BioTechnologies",
    "biotium": "Biotium",
}


def resolve_jena(product):
    """返回 (jena_catalog_no, bioz_vendor) 或 None。

    使用生产级 match_jena 级联（CAS→name→synonyms），与 AUTO MATCH 同源，
    保证覆盖与线上一致（铁律①：扩到全部 jena 命中产品，而非仅精确 catalog 命中的子集）。
    """
    user_cas = (product.get("cas") or "").strip()
    search_name = product.get("name") or ""
    synonyms = product.get("synonyms") or []
    if isinstance(synonyms, str):
        synonyms = [synonyms]
    identifier = user_cas or search_name
    if not identifier and not synonyms:
        return None
    namespace = "cas" if (user_cas and _looks_like_cas(user_cas)) else "name"
    try:
        jena = match_jena(identifier=identifier, namespace=namespace,
                          synonyms=synonyms, request_name=search_name)
    except Exception as e:
        return None
    if not jena.get("matched"):
        return None
    catalog_no = jena.get("catalog_no", "")
    if "sources" in jena and not catalog_no:
        matched_sources = [s for s in jena.get("sources", []) if s.get("matched")]
        s = next((x for x in matched_sources if x.get("vendor") == "jena"), None) \
            or (matched_sources[0] if matched_sources else None)
        if s:
            catalog_no = s.get("catalog_no", "")
    if not catalog_no:
        return None
    vendor = (jena.get("vendor") or "jena").lower()
    return catalog_no, VENDOR_MAP.get(vendor, "Jena Bioscience")


class Command(BaseCommand):
    help = "Crawl Bioz for all jena-matched products, fill DataSourceCache."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true",
                            help="ignore non-stale cache, re-fetch")
        parser.add_argument("--limit", type=int, default=0,
                            help="max products to crawl (0=all)")

    def handle(self, *args, **opt):
        force = opt["force"]
        limit = opt["limit"]
        client = BiozClient()

        products = list(Product.objects.values("id", "catalog_no", "name", "cas", "synonyms"))
        self.stdout.write(f"products in DB: {len(products)}")

        matched = 0
        done = 0
        with_records = 0
        skipped_cached = 0
        failed = 0
        plan = []
        for p in products:
            r = resolve_jena(p)
            if r is None:
                continue
            matched += 1
            plan.append((p, r[0], r[1]))

        self.stdout.write(f"jena-matched products: {matched}")

        for i, (p, jcat, vendor) in enumerate(plan, 1):
            if limit and done >= limit:
                break
            key = f"{vendor}:{jcat}"
            try:
                if not force:
                    from apps.documents.services.datasource_cache import get_cache
                    cached = get_cache("bioz", key, "sku")
                    if cached is not None and not cached.is_stale:
                        skipped_cached += 1
                        done += 1
                        continue
                recs = client.search_by_sku(jcat, vendor)
                done += 1
                if recs:
                    with_records += 1
                if (i % 10) == 0 or i == len(plan):
                    self.stdout.write(
                        f"  [{i}/{len(plan)}] {p['catalog_no'] or p['name']} "
                        f"-> {len(recs)} bioz records")
            except Exception as e:
                failed += 1
                self.stderr.write(f"  [{i}] {p['catalog_no']} FAILED: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"\nDONE: matched={matched} crawled={done} "
            f"with_records={with_records} skipped_cached={skipped_cached} failed={failed}"))
        sys.stdout.flush()
