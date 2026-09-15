"""Europe PMC 全文检索 → 写 DataSourceCache（复用 source='pubmed' 槽位）。

背景（2026-09-15 生产实测，见 memory `2026-09-15.md` §11）：
  47 个零证据产品在 Bioz 上**有效命中 0/45**（24 TriLink + 21 Jena 货号逐个实查，
  仅 2 条记录且均为错配）；PubMed 商品名检索仅 **2/47**；
  而 **Europe PMC 全文检索 29/47（62%）有命中**（Biotin-11-ATP 44、5-Methoxy-UTP 25、
  O6-Methyl-GTP 8 …）。负对照（假词 `Biotin-77-QQQX` / 不存在的类似物
  `5-Propargylamino-GTP`）均为 0；真阳性已全文核验（PMID 40741402 的 OA 全文
  含 `Biotin-11-ATP` ×3）——命中来自**方法学段落全文**，故 PubMed 的题录/摘要检索抓不到。

为何复用 source='pubmed' 而非新增 'europepmc'：
  `DataSourceCache.Source` 是 TextChoices，新增取值需改模型 + migration，与项目
  铁律"不改模型"冲突。EPMC 命中的每条记录都带 PMID，落库后创建的 Reference 就是
  真实 PubMed 记录，故沿用 pubmed 槽位语义成立；**真实索引来源记在记录的 `_index`
  字段**（='europepmc'）以便审计与日后迁移。

为何必须在本机跑：
  生产容器到 Europe PMC 的网络被挡（`SSLEOFError`，实测）；本机可达。
  故流程为：本机 crawl 写缓存 → 导出 → 注入生产 DataSourceCache → 生产跑
  `adopt_cached_evidence --source pubmed --apply`。

用法（本机 sqlite，需外网）：
  cd backend && DB_ENGINE=sqlite PYTHONDONTWRITEBYTECODE=1 \
      venv/Scripts/python.exe -B manage.py crawl_europepmc_evidence \
      [--apply] [--limit N] [--only-products SC8001,SC8002] \
      [--force] [--max-per-product 25] [--out plan.jsonl]
默认 dry-run：只打印计划，绝不写库。
"""
import json
import re

from django.core.management.base import BaseCommand, CommandError

from apps.commerce.models import Product
from apps.documents.models import DataSourceCache
from apps.documents.services.datasource_cache import get_cache, set_cache
from core.datasource_client import request_with_resilience

EPMC_SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

# 与 PubMed 槽位一致的记录形状（adopt_cached_evidence._normalize 的 pubmed 分支按此读取：
#   title / authors / source(=journal!) / pubdate / doi / pmid）
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# 非 ASCII 破折号（U+2011 等）会让 EPMC 短语检索失配 → 0 命中时用 ASCII 名重试一次
_DASH_RE = re.compile("[\u2010\u2011\u2012\u2013\u2014\u2015]")


def ascii_dashes(name: str) -> str:
    return _DASH_RE.sub("-", name or "")


def _authors_list(author_string) -> list:
    """EPMC authorString 'A, B, C.' → ['A', 'B', 'C']。"""
    if not author_string:
        return []
    parts = [p.strip().rstrip(".").strip()
             for p in str(author_string).split(",")]
    return [p for p in parts if p]


def parse_epmc_results(payload) -> list:
    """Europe PMC search 响应 → adopt 可用的记录列表（pubmed 槽位形状）。

    只保留 title 非空且 (pmid 或 doi) 存在的记录；其余丢弃（宁 miss 不错配）。
    """
    if not isinstance(payload, dict):
        return []
    results = (payload.get("resultList") or {}).get("result")
    if not isinstance(results, list):
        return []
    out = []
    for r in results:
        if not isinstance(r, dict):
            continue
        title = (r.get("title") or "").strip()
        if not title:
            continue
        pmid = str(r.get("pmid") or r.get("id") or "").strip()
        doi = (r.get("doi") or "").strip()
        if not pmid and not doi:
            continue
        out.append({
            "pmid": pmid,
            "title": title,
            "source": (r.get("journalTitle") or "").strip(),   # = journal（命名沿用 pubmed 槽位）
            "doi": doi,
            "pubdate": str(r.get("pubYear") or "").strip(),
            "authors": _authors_list(r.get("authorString")),
            "_index": "europepmc",
        })
    return out


def _fetch(query: str, page_size: int) -> list:
    """按 query 检索 EPMC，返回解析后的记录列表；失败返回 []。"""
    resp = request_with_resilience(
        "GET", EPMC_SEARCH_URL, source="europepmc", timeout=30,
        params={"query": query, "format": "json",
                "pageSize": str(page_size), "resultType": "lite"},
        headers={"User-Agent": _UA, "Accept": "application/json"},
    )
    if not resp.ok:
        return []
    return parse_epmc_results(resp.json())


class Command(BaseCommand):
    help = ("Crawl Europe PMC full-text search per product name into DataSourceCache "
            "(source='pubmed' slot). Dry-run by default; --apply to write.")

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true",
                            help="Write to DataSourceCache (default: dry-run only).")
        parser.add_argument("--limit", type=int, default=None,
                            help="Only process the first N products (by id).")
        parser.add_argument("--only-products", default=None,
                            help="Comma-separated catalog_no whitelist.")
        parser.add_argument("--force", action="store_true",
                            help="Also overwrite rows that already hold non-empty evidence.")
        parser.add_argument("--max-per-product", type=int, default=25,
                            help="Cap records stored per product (default 25).")
        parser.add_argument("--page-size", type=int, default=25,
                            help="EPMC pageSize per request (default 25).")
        parser.add_argument("--out", default=None,
                            help="Write one JSONL line per product (plan/detail).")

    def handle(self, *args, **options):
        apply = options["apply"]
        limit = options["limit"]
        max_per = options["max_per_product"]
        page_size = options["page_size"]
        force = options["force"]
        out_path = options["out"]
        only = ([s.strip() for s in options["only_products"].split(",") if s.strip()]
                if options["only_products"] else None)
        if max_per <= 0:
            raise CommandError("--max-per-product 必须 > 0")

        products = Product.objects.order_by("id")
        if only:
            products = products.filter(catalog_no__in=only)
        if limit is not None:
            products = products[:limit]
        product_list = list(products)

        fetched = written = skipped_existing = no_hit = failed = 0
        total_records = 0
        lines = []

        for p in product_list:
            key = p.catalog_no
            if not key:
                continue
            existing = get_cache("pubmed", key, "sku")
            if existing is not None and not force:
                data = existing.get_data()
                if isinstance(data, list) and data:
                    skipped_existing += 1
                    continue
            name = (p.name or "").strip()
            if not name:
                continue
            try:
                recs = _fetch('"%s"' % name, page_size)
                if not recs:
                    alt = ascii_dashes(name)
                    if alt != name:
                        recs = _fetch('"%s"' % alt, page_size)
            except Exception as e:  # 网络/解析异常不中断整批
                failed += 1
                self.stderr.write(f"  [{key}] FAILED: {e}")
                continue
            fetched += 1
            if not recs:
                no_hit += 1
                lines.append({"catalog_no": key, "name": name, "records": 0,
                              "written": False})
                continue
            recs = recs[:max_per]
            total_records += len(recs)
            if apply:
                set_cache("pubmed", key, "sku", recs)
                written += 1
            lines.append({"catalog_no": key, "name": name, "records": len(recs),
                          "written": bool(apply),
                          "sample": [r["pmid"] or r["doi"] for r in recs[:5]]})

        if out_path:
            with open(out_path, "w", encoding="utf-8") as f:
                for ln in lines:
                    f.write(json.dumps(ln, ensure_ascii=False) + "\n")

        mode = "APPLY" if apply else "DRY-RUN"
        self.stdout.write(self.style.SUCCESS(
            f"\n[{mode}] products={len(product_list)} queried={fetched} "
            f"with_records={fetched - no_hit} no_hit={no_hit} "
            f"written={written} skipped_existing={skipped_existing} failed={failed} "
            f"records={total_records}"))
        self.stdout.write(
            "下一步：本机导出这些行 → 注入生产 DataSourceCache → "
            "生产跑 adopt_cached_evidence --source pubmed --apply")
