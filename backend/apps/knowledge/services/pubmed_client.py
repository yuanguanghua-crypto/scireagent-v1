"""PubMed API 客户端
通过 NCBI E-utilities API 搜索文献。
- ESearch: 关键词搜索
- ESummary: 获取文献元数据
- EFetch: 获取摘要正文
"""
import html
import logging
import re
from typing import Optional

from core.datasource_client import request_with_resilience
from apps.knowledge.services.external_objective import _method_tokens

logger = logging.getLogger(__name__)

PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def _method_token_query(name: str) -> str:
    """从协议名提取最具区分度的方法 token 作为检索词（如 BARseq / HCR / Tn5）。

    偏好含数字 / 连字符 / 全大写的 token（更像方法缩写）。无则返回 ''。
    """
    mts = _method_tokens(name)
    if not mts:
        return ''
    # 排序：含数字 > 含连字符 > 全大写 > 其他
    mts.sort(key=lambda t: (
        any(ch.isdigit() for ch in t), '-' in t, t.isupper()
    ), reverse=True)
    return mts[0]


def _parse_pubmed_xml_abstract(xml_text: str) -> str:
    """从 efetch retmode=xml 响应解析纯摘要正文。

    NCBI XML 把摘要拆成多个 <AbstractText Label="..." NlmCategory="..."> 段；
    保留 Label 作为小節标题（如 'BACKGROUND: ...'），使下游 extract_objective
    的结构化切分仍生效。返回拼接后的纯文本；无 <AbstractText> 返回空串。

    实体转义：NCBI 用数值实体表达希腊字母/符号（&#x3b2; = β、&#x3b1; = α），
    必须 html.unescape 还原，否则写进 Protocol.objective 的正文会是
    'pancreatic &#x3b2; cell' 这类脏文本。顺序必须是「先去标签 → 再反转义」，
    否则 &lt;b&gt; 会先被还原成 <b> 再被当真标签剥掉，丢失字面内容。
    """
    segments = re.findall(r'<AbstractText\b([^>]*)>(.*?)</AbstractText>', xml_text, re.S)
    if not segments:
        return ''
    parts = []
    for attrs, body in segments:
        body = re.sub(r'<[^>]+>', '', body)  # 去内层标签（<b>/<i> 等）
        body = html.unescape(body)           # 再反转义（顺序不可颠倒）
        body = re.sub(r'\s+', ' ', body).strip()
        if not body:
            continue
        m = re.search(r'Label="([^"]*)"', attrs)
        if m:
            label = m.group(1).strip().upper()
            parts.append(f"{label}: {body}")
        else:
            parts.append(body)
    return ' '.join(parts).strip()


class PubMedClient:
    """PubMed REST API 客户端

    限速与重试统一由 core/datasource_client.request_with_resilience 处理
    （PubMed 3 req/s 令牌桶 + 429/503/504 指数退避），本客户端不再手写 sleep。
    详见 docs/DATASOURCE_RELIABILITY.md §4。
    """

    def __init__(self, timeout: int = 15, api_key: Optional[str] = None):
        self.timeout = timeout
        self.api_key = api_key

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
            r = request_with_resilience(
                "GET", f"{PUBMED_BASE}/esearch.fcgi",
                source="pubmed", timeout=self.timeout,
                params=params,
            )
            r.raise_for_status()
            data = r.json()
            id_list = data.get("esearchresult", {}).get("idlist", [])
            if not id_list:
                return []
            return self._fetch_details(id_list)
        except Exception as e:
            logger.warning(f"PubMed search failed for query {query[:50]}: {e}")
            return []

    def search_by_protocol_name(self, name: str, max_results: int = 5) -> list:
        """按协议名多策略搜索（短语精确 → 全文兜底 → 方法 token 检索）。

        与 search_by_product 不同：协议名不含 CAS/产品别名，故只做
        标题/摘要短语搜索 + 全文兜底 + 方法缩写检索（如 BARseq/HCR/Tn5），
        避免污染。返回结构同 search_by_product。
        """
        if not name:
            return []
        name_clean = name.replace("'", "").replace('"', '').replace("`", "")
        queries = [
            f'"{name_clean}"[Title/Abstract]',  # 策略1: 短语精确命中标题/摘要
            name_clean,                           # 策略2: 全文兜底
        ]
        mt = _method_token_query(name)
        if mt:
            queries.append(f'"{mt}"[Title/Abstract]')  # 策略3: 方法缩写短语
            queries.append(mt)                     # 策略4: 方法缩写全文
        seen = set()
        results = []
        for query in queries:
            for article in self._search_single(query, max_results):
                pmid = article.get("pmid")
                if pmid and pmid not in seen:
                    seen.add(pmid)
                    results.append(article)
            if len(results) >= max_results:
                break
        return results[:max_results]

    def fetch_abstract(self, pmid: str, max_chars: int = 4000) -> str:
        """按 PMID 取论文摘要正文。

        优先 retmode=xml 解析 <AbstractText>（干净、无引文头噪声）；
        XML 失败/为空时回退 retmode=text（去 'PMID:' 前缀）。
        失败/无摘要均返回空串（调用方据此跳过，严守宁 miss 不错配）。
        """
        if not pmid:
            return ""
        # 优先 XML：干净摘要，避免 text 模式「引文头+作者+机构+Erratum+正文」整块
        # 导致 extract_objective 把 "1. Biotechniques." 当摘要判 junk 返回空。
        xml_params = {
            "db": "pubmed",
            "id": pmid,
            "rettype": "abstract",
            "retmode": "xml",
        }
        if self.api_key:
            xml_params["api_key"] = self.api_key
        try:
            r = request_with_resilience(
                "GET", f"{PUBMED_BASE}/efetch.fcgi",
                source="pubmed", timeout=self.timeout,
                params=xml_params,
            )
            r.raise_for_status()
            text = _parse_pubmed_xml_abstract(r.text)
            if text:
                return text[:max_chars]
        except Exception as e:
            logger.warning(f"PubMed XML abstract fetch failed for {pmid}: {e}")
        # 回退 text 模式
        text_params = {
            "db": "pubmed",
            "id": pmid,
            "rettype": "abstract",
            "retmode": "text",
        }
        if self.api_key:
            text_params["api_key"] = self.api_key
        try:
            r = request_with_resilience(
                "GET", f"{PUBMED_BASE}/efetch.fcgi",
                source="pubmed", timeout=self.timeout,
                params=text_params,
            )
            r.raise_for_status()
            text = (r.text or "").strip()
            # 去掉 efetch 常见的 "PMID: 123" 前缀行
            text = re.sub(r'^\s*PMID:\s*\d+\s*', '', text, flags=re.I).strip()
            return text[:max_chars]
        except Exception as e:
            logger.warning(f"PubMed abstract fetch failed for {pmid}: {e}")
            return ""

    def _fetch_details(self, pmid_list: list) -> list:
        """获取文献详情"""
        if not pmid_list:
            return []
        summary_url = f"{PUBMED_BASE}/esummary.fcgi"
        params = {
            "db": "pubmed",
            "id": ",".join(pmid_list),
            "retmode": "json",
        }
        if self.api_key:
            params["api_key"] = self.api_key

        try:
            r = request_with_resilience(
                "GET", summary_url,
                source="pubmed", timeout=self.timeout,
                params=params,
            )
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
