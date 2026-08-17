"""Europe PMC API 客户端 —— Protocol.objective 补全的第二外部源。

为什么引入这个源（2026-08-08 对 70 条空 objective 的只读探针实测结论）：

1. **一次请求即拿到摘要**：`resultType=core` 把 `abstractText` 直接内嵌在检索
   结果里，无需 PubMed 那样 esearch + efetch 两步，请求数减半；沙箱实测 1.9s/请求，
   且未出现 NCBI 那种间歇 502（会让 --apply 结果不可复现）。
2. **覆盖 PubMed 不索引的预印本平台**：`source=PPR` 对应 protocols.exchange /
   Research Square / bioRxiv —— 而我们补的正是「协议」，源头天然对口。
   实测 3 条真增量里 2 条（Hi-C mosquito embryos / bioRxiv）只有 EPMC 能找到。
3. **换源能纠正错配**：id=149（Agrobacterium→asparagus）上一批被 PubMed 判为
   错配，Europe PMC 命中了真正的源论文。

同时必须记住探针的负面结论：EPMC 自动门放行的候选里错配率 **57%**（高于 PubMed
批的 33%），因为 preprint 覆盖面广也意味着噪声大。故落库路径不变，仍是
「dry-run --report → 人工复核 → --from-report 重放 + --allowlist 白名单」。

限速/重试：统一走 core/datasource_client（'europepmc' 令牌桶），本模块不手写 sleep。
"""
import html
import logging
import re

from core.datasource_client import request_with_resilience

logger = logging.getLogger(__name__)

EPMC_SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

# Europe PMC 的预印本源标识（protocols.exchange / Research Square / bioRxiv 等）
PREPRINT_SOURCE = "PPR"


def strip_markup(text: str) -> str:
    """去标记 + 反转义 + 压缩空白。

    顺序铁律「先去标签 → 再反转义」（与 PubMed XML 路径同口径）：否则 `&lt;b&gt;`
    会先被还原成 `<b>` 再被当真标签剥掉，丢失字面内容。

    EPMC 的 title 字段也会内嵌裸标签（实测 bioRxiv 条目标题含 `<i>Saccharomyces
    cerevisiae</i>`），故标题与摘要共用本函数。
    """
    if not text:
        return ''
    text = re.sub(r'<[^>]+>', ' ', text)   # 去标签
    text = html.unescape(text)             # 再反转义（顺序不可颠倒）
    return re.sub(r'\s+', ' ', text).strip()


def clean_abstract(text: str) -> str:
    """清洗 Europe PMC 的 abstractText 为纯文本。

    在 strip_markup 基础上多一步：EPMC 对 PPR（预印本）源的摘要固定包装一个前导
    `Abstract` 字样，不剥掉的话写进 Protocol.objective 会变成
    'Abstract The step-by-step...'。剥离要求 'abstract' 后紧跟冒号或空白，
    故 'Abstracts were screened' 这类正常句首不受影响。
    """
    text = strip_markup(text)
    if not text:
        return ''
    return re.sub(r'^abstract[:\s]+', '', text, flags=re.I).strip()


def build_queries(name: str) -> list:
    """按精确度递减构造三级检索式。

    1) `TITLE:"<name>"`                          —— 标题短语精确，最可信
    2) `(TITLE:"<name>" OR ABSTRACT:"<name>")`   —— 放宽到摘要短语
    3) `<name>`                                  —— 全文兜底

    协议名里的引号会破坏 EPMC 的短语语法，先清掉。空名返回 []。
    """
    clean = re.sub(r'["\']', ' ', name or '')
    clean = re.sub(r'\s+', ' ', clean).strip()
    if not clean:
        return []
    return [
        f'TITLE:"{clean}"',
        f'(TITLE:"{clean}" OR ABSTRACT:"{clean}")',
        clean,
    ]


def _parse_result(entry: dict) -> dict:
    """把 EPMC 一条 result 规整成统一候选结构。"""
    src = (entry.get('source') or '').strip()
    return {
        'title': strip_markup(entry.get('title') or ''),
        'abstract': clean_abstract(entry.get('abstractText') or ''),
        'pmid': (entry.get('pmid') or '').strip(),
        'pmcid': (entry.get('pmcid') or '').strip(),
        'doi': (entry.get('doi') or '').strip(),
        'source': src,
        'is_preprint': src == PREPRINT_SOURCE,
    }


def _dedup_key(item: dict) -> str:
    return (item.get('doi') or item.get('pmid')
            or item.get('pmcid') or item.get('title') or '').lower()


class EuropePMCClient:
    """Europe PMC REST 客户端（只做协议名检索这一件事）。

    与 PubMedClient 的关键差异：摘要内嵌在检索响应里，没有独立的
    fetch_abstract 步骤 —— 这正是选它作为第二源的主要原因之一。
    """

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    def _search_single(self, query: str, page_size: int) -> list:
        params = {
            'query': query,
            'format': 'json',
            'pageSize': max(1, min(page_size, 25)),
            'resultType': 'core',   # 内嵌 abstractText
        }
        try:
            r = request_with_resilience(
                'GET', EPMC_SEARCH_URL,
                source='europepmc', timeout=self.timeout,
                params=params,
            )
            r.raise_for_status()
            data = r.json() or {}
        except Exception as e:  # noqa: BLE001 —— 外部源异常一律降级为「无结果」
            logger.warning(f"Europe PMC search failed for {query[:60]!r}: {e}")
            return []
        results = ((data.get('resultList') or {}).get('result')) or []
        return [_parse_result(x) for x in results if isinstance(x, dict)]

    def search_by_protocol_name(self, name: str, max_results: int = 8) -> list:
        """按协议名三级检索，返回去重后的候选列表（含摘要）。

        任一级凑够 max_results 即停；跨级按 DOI/PMID/PMCID/标题去重。
        任何网络/解析异常都降级为空列表（宁 miss 不错配）。
        """
        queries = build_queries(name)
        if not queries:
            return []
        seen = set()
        out = []
        for q in queries:
            for item in self._search_single(q, max_results):
                key = _dedup_key(item)
                if not key or key in seen:
                    continue
                seen.add(key)
                out.append(item)
            if len(out) >= max_results:
                break
        return out[:max_results]
