"""PubMed API 客户端
通过 NCBI E-utilities API 搜索文献。
- ESearch: 关键词搜索
- ESummary: 获取文献元数据
"""
import logging
import time
from typing import Optional
import requests

logger = logging.getLogger(__name__)

PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


class PubMedClient:
    """PubMed REST API 客户端"""

    def __init__(self, timeout: int = 15, api_key: Optional[str] = None):
        self.timeout = timeout
        self.api_key = api_key
        self._last_request = 0.0

    def _rate_limit(self):
        """NCBI 限制每秒最多 3 次请求（无 API key）或 10 次（有 API key）"""
        min_interval = 0.1 if self.api_key else 0.35
        elapsed = time.time() - self._last_request
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request = time.time()

    # 常见产品的别名映射
    PRODUCT_SYNONYMS = {
        "5-Ethynyl-dUTP": "EdU",
        "5-Ethynyl-2'-deoxyuridine": "EdU",
        "5-Propargylamino-CTP": "propargylamino CTP",
        "5-Propargylamino-dCTP": "propargylamino dCTP",
    }

    # 产品分类到 PubMed 搜索词的映射
    CATEGORY_KEYWORDS = {
        "nucleotides_nucleosides": "modified nucleotide labeling OR nucleotide analog",
        "fluorescence": "fluorescent probe OR fluorescent labeling",
        "biochemistry": "biochemical assay OR enzymatic labeling",
    }

    def _get_synonyms(self, product_name: str) -> list:
        """获取产品别名"""
        aliases = []
        # 直接匹配别名表
        if product_name in self.PRODUCT_SYNONYMS:
            aliases.append(self.PRODUCT_SYNONYMS[product_name])
        # 提取核心词（去数字前缀和后缀）
        import re
        core = re.sub(r"^[\d'-]+", "", product_name).strip("-").strip("'")
        if core and core != product_name:
            aliases.append(core)
        return aliases

    def _build_query(self, product_name: str, cas: Optional[str] = None) -> list:
        """构建多组搜索查询（按优先级排序）"""
        queries = []

        # 策略 1: 产品名精确搜标题/摘要
        name_clean = product_name.replace("'", "").replace('"', '').replace("`", "")
        queries.append(f'"{name_clean}"[Title/Abstract]')

        # 策略 2: 别名搜索
        syns = self._get_synonyms(product_name)
        for syn in syns:
            queries.append(f'"{syn}"[Title/Abstract]')

        # 策略 3: CAS 号
        if cas and cas != "N/A":
            queries.append(cas)

        # 策略 4: 产品名（全文搜索，兜底）
        queries.append(name_clean)

        return queries

    def search_by_product(self, product_name: str, cas: Optional[str] = None,
                          max_results: int = 10) -> list:
        """按产品信息多策略搜索"""
        if not product_name:
            return []

        queries = self._build_query(product_name, cas)
        seen_pmids = set()
        results = []

        for query in queries:
            batch = self._search_single(query, max_results)
            for article in batch:
                pmid = article.get("pmid")
                if pmid and pmid not in seen_pmids:
                    seen_pmids.add(pmid)
                    results.append(article)
            if len(results) >= max_results:
                break

        return results[:max_results]

    def _search_single(self, query: str, max_results: int = 10) -> list:
        """单次搜索"""
        self._rate_limit()
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "sort": "relevance",
        }
        if self.api_key:
            params["api_key"] = self.api_key

        try:
            r = requests.get(f"{PUBMED_BASE}/esearch.fcgi", params=params, timeout=self.timeout)
            r.raise_for_status()
            data = r.json()
            id_list = data.get("esearchresult", {}).get("idlist", [])
            if not id_list:
                return []
            return self._fetch_details(id_list)
        except Exception as e:
            logger.warning(f"PubMed search failed for query {query[:50]}: {e}")
            return []

    def _fetch_details(self, pmid_list: list) -> list:
        """获取文献详情"""
        if not pmid_list:
            return []
        self._rate_limit()
        summary_url = f"{PUBMED_BASE}/esummary.fcgi"
        params = {
            "db": "pubmed",
            "id": ",".join(pmid_list),
            "retmode": "json",
        }
        if self.api_key:
            params["api_key"] = self.api_key

        try:
            r = requests.get(summary_url, params=params, timeout=self.timeout)
            r.raise_for_status()
            data = r.json()
            results = []
            for uid in pmid_list:
                entry = data.get("result", {}).get(uid, {})
                if not entry:
                    continue
                doi = ""
                eloc = entry.get("elocationid", "")
                if eloc.startswith("doi:"):
                    doi = eloc[4:]
                results.append({
                    "pmid": uid,
                    "title": entry.get("title", ""),
                    "source": entry.get("source", ""),
                    "pubdate": entry.get("pubdate", ""),
                    "authors": [a.get("name", "") for a in entry.get("authors", [])[:5]],
                    "doi": doi,
                    "elocationid": eloc,
                })
            return results
        except Exception as e:
            logger.warning(f"PubMed detail fetch failed: {e}")
            # 降级：返回基础信息
            return [{"pmid": uid, "title": "", "source": "",
                      "pubdate": "", "authors": [], "doi": ""} for uid in pmid_list]
