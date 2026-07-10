"""Bioz widget API 客户端（厂商作参数，多厂商可扩展）。

按 供应商名 + SKU 查询 Bioz widget，返回原始解析后的文献记录列表。
此层只做请求 + 解析 + L1 缓存，不做厂商无关化净化、不做化学等同性校验
（职责分离：净化在 bioz_sanitizer，等同性在 bioz_equivalence，编排在 bioz_pipeline）。

vendor 作参数（非硬编码）：本 Phase 默认 "Jena Bioscience"，后续接默克/赛默飞
只需建对应索引 + 换 vendor 参数，本客户端无需改动。

详见 docs/FIVE_DATASOURCES.md §3.6、memory bioz-api-real-behavior。
"""
import logging

from core.datasource_client import request_with_resilience
from apps.documents.services.datasource_cache import get_cache, set_cache

logger = logging.getLogger(__name__)

BIOZ_WIDGET_URL = "https://back-badge-8.bioz.com/get_widget_data_ex_v9/"


class BiozClient:
    """Bioz widget API 客户端。

    限速与重试统一由 request_with_resilience(source='bioz') 处理
    （2 req/s 令牌桶 + 429/503/504 指数退避）。
    L1 DataSourceCache 14 天（SOURCE_TTL 已配）。
    """

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def search_by_sku(self, catalog_no: str, vendor: str = "Jena Bioscience",
                      max_results: int = 10) -> list[dict]:
        """按供应商 SKU 查询 Bioz 文献。

        Args:
            catalog_no: 供应商目录号（如 jena 的 NU-1138）
            vendor: 供应商名（如 "Jena Bioscience"）
            max_results: 返回条数上限

        Returns:
            文献记录 list[dict]（原始解析，未净化）。每条含 article_title/authors/
            journal/impact_factor/pmid/pmcid/doi/pub_date/techniques/filter_data/
            image_urls/long/medium/short/catalog_group（供净化用）。
            查询失败返回 []。
        """
        if not catalog_no or not vendor:
            return []

        cache_key = f"{vendor}:{catalog_no}"
        entry = get_cache("bioz", cache_key, "sku")
        if entry is not None and not entry.is_stale:
            data = entry.get_data()
            if data is not None:
                return data

        try:
            resp = request_with_resilience(
                "POST",
                BIOZ_WIDGET_URL,
                source="bioz",
                timeout=self.timeout,
                data={
                    "qx": catalog_no,
                    "cx": vendor,
                    "tx": "commercial",
                    "sx": str(max_results),
                    "kx": "",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
            )
            if not resp.ok:
                logger.warning(f"Bioz widget non-200 for {vendor}:{catalog_no}: {resp.status_code}")
                return []
            payload = resp.json()
        except Exception as e:
            logger.warning(f"Bioz widget request failed for {vendor}:{catalog_no}: {e}")
            return []

        records = self._parse_records(payload)

        try:
            set_cache("bioz", cache_key, "sku", records)
        except Exception as e:
            logger.debug(f"Bioz cache set skipped for {cache_key}: {e}")

        return records

    @staticmethod
    def _parse_records(payload: dict) -> list[dict]:
        """解析 Bioz widget 响应 → 文献记录列表。

        只抽保留字段（厂商无关化净化需要 catalog_group，故保留）。
        丢弃 score/rating_info/vendor_name/product_url 等厂商/SKU 相关字段
        （净化在 bioz_sanitizer 做，编排层组装最终输出时再丢 catalog_group）。
        """
        if not isinstance(payload, dict):
            return []
        raw_records = payload.get("records") or []
        if not isinstance(raw_records, list):
            return []

        parsed = []
        for rec in raw_records:
            if not isinstance(rec, dict):
                continue
            parsed.append({
                "article_title": rec.get("article_title", "") or "",
                "authors": rec.get("authors", []) or [],
                "journal": rec.get("journal", "") or "",
                "impact_factor": rec.get("impact_factor") or 0.0,
                "pmid": rec.get("pmid", "") or "",
                "pmcid": rec.get("pmcid", "") or "",
                "doi": rec.get("doi", "") or "",
                "pub_date": rec.get("pub_date", "") or "",
                "techniques": rec.get("techniques", []) or [],
                "filter_data": rec.get("filter_data") or [],
                "image_urls": rec.get("image_urls", []) or [],
                # 引用上下文（待净化）
                "long": rec.get("long", "") or "",
                "medium": rec.get("medium", "") or "",
                "short": rec.get("short", "") or "",
                # 供净化器取 SKU 变体
                "catalog_group": rec.get("catalog_group", []) or [],
                "catalog_number": rec.get("catalog_number", "") or "",
            })
        return parsed
