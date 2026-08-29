"""Evidence Miner v0（生产版，由 datasource_eval/miner_v0 移植）。

职责（两维度分离——用户 2026-08-29 黄金集裁定）：
- 本模块只负责 **relevance 维度**：产品实体 ↔ PubMed 文献的相关性筛选，
  产出候选（product_id + PMID + 信号/强度 + 标题级 Method 匹配）。
- **不裁决 applicability**：evidence_strength 保持保守信号映射（单信号=medium、
  双信号=high），不因黄金集自动升级；applicability 由研究员 approve 时裁决
  （VerifiedService.approve_verified + status 状态机）。

纯逻辑层：不 import django，可独立单测。ORM 落库在 verified_drafts_generator.py。

实测坑（已在 pilot 验证并留测试）：
  1. DB 产品名含 U+2011 非断行连字符 → _norm_text 归一化为 ASCII '-'
  2. PubMed 带引号短语 + [Title]/[Title/Abstract] 对连字符化合物返回 0
     → 检索式一律不用字段限定符（All Fields 候选池），精度由 title 信号闸门兜底
  3. 泛词淹没精词（biotin-11-dutp 命中 78 条且 retmax 截断挤掉精确命中）
     → 逐项 esearch(retmax=5) 取并集去重
"""
import json
import re
import time
import urllib.parse
import urllib.request

EUTILS = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'
REQUEST_INTERVAL = 0.4   # 秒（NCBI 无 key 限 3 req/s）
ESEARCH_RETMAX = 5       # 每检索项上限（防泛词淹没）
MAX_CANDIDATES = 3       # 护栏 5：每产品最多候选数
COVERAGE_THRESHOLD = 0.8  # 词元覆盖率阈值（宁缺毋滥）

MINER_VERSION = 'miner_v0.1'
ORIGIN_TAG = f'origin:ai_extracted|{MINER_VERSION}|PubMed'


class PubMedClient:
    """极简 E-utilities 客户端（urllib，零第三方依赖；可被测试替换）。"""

    def __init__(self, interval=REQUEST_INTERVAL):
        self._last = 0.0
        self.interval = interval

    def _get(self, endpoint, params):
        wait = self._last + self.interval - time.time()
        if wait > 0:
            time.sleep(wait)
        url = EUTILS + endpoint + '?' + urllib.parse.urlencode(params)
        self._last = time.time()
        with urllib.request.urlopen(url, timeout=20) as resp:
            return json.loads(resp.read().decode('utf-8'))

    def esearch(self, term, retmax=ESEARCH_RETMAX):
        data = self._get('esearch.fcgi', {
            'db': 'pubmed', 'term': term, 'retmax': retmax, 'retmode': 'json',
        })
        return data.get('esearchresult', {})

    def esummary(self, ids):
        if not ids:
            return {}
        data = self._get('esummary.fcgi', {
            'db': 'pubmed', 'id': ','.join(str(i) for i in ids), 'retmode': 'json',
        })
        return data.get('result', {})


def _norm_text(s):
    """归一化：小写 + 连字符/撇号变体 → ASCII（覆盖 U+2011 等实测坑）。"""
    s = (s or '').lower()
    for src, dst in (('\u2010', '-'), ('\u2011', '-'), ('\u2012', '-'),
                     ('\u2013', '-'), ('\u2212', '-'), ('\u2032', "'"),
                     ('\u2019', "'"), ('\u2018', "'"), ('`', "'")):
        s = s.replace(src, dst)
    return s


def _tokens(s):
    """词元集：字母/数字连续串（长度 ≥2，滤单字母虚词）。"""
    return {t for t in re.findall(r'[a-z0-9]+', _norm_text(s)) if len(t) >= 2}


def build_terms(name, synonyms, cas):
    """逐项检索式（每项独立 esearch，避免泛词淹没精词）。"""
    terms = []
    for t in [name, *synonyms]:
        t = (t or '').strip()
        if t:
            terms.append(f'"{_norm_text(t)}"')
    if cas:
        terms.append(f'"{cas}"')
    return terms


def build_query(name, synonyms, cas):
    """全部 OR 连接（审计/兼容用；实际检索走 build_terms 逐项）。"""
    return ' OR '.join(build_terms(name, synonyms, cas))


def count_signals(title, name, synonyms, cas):
    """title 信号计数 → (signal_names, signal_cas)。

    规则（宁缺毋滥）：产品名或任一 synonym 词元集 ≥0.8 覆盖 title 词元集 → 名信号；
    CAS 归一化子串在 title → CAS 信号。覆盖「5-iodo-2'-deoxyuridine 5'-triphosphate」
    类空格/撇号变体全名写法。
    """
    title_tokens = _tokens(title)
    name_hits = []
    for s in [name, *synonyms]:
        s = (s or '').strip()
        term_tokens = _tokens(s)
        if term_tokens and len(term_tokens & title_tokens) / len(term_tokens) >= COVERAGE_THRESHOLD:
            name_hits.append(s)
    cas_hit = bool(cas and _norm_text(cas) in _norm_text(title))
    return name_hits, cas_hit


def match_methods_in_title(title, methods):
    """标题级 Method 匹配（词元覆盖率 ≥0.8，按覆盖率降序）。

    methods: [{'id','name','slug'}]。返回匹配列表（空 = 无方法命中，不落库）。
    语义边界：论文标题提到方法 ≠ 论文证明产品适用于该方法（relevance 级证据）。
    """
    title_tokens = _tokens(title)
    hits = []
    for m in methods:
        m_tokens = _tokens(m.get('name'))
        if not m_tokens:
            continue
        coverage = len(m_tokens & title_tokens) / len(m_tokens)
        if coverage >= COVERAGE_THRESHOLD:
            hits.append({'id': m['id'], 'name': m['name'], 'slug': m.get('slug', ''),
                         'coverage': round(coverage, 2)})
    return sorted(hits, key=lambda h: h['coverage'], reverse=True)


def _dedupe(seq):
    seen, out = set(), []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def mine_product(client, product):
    """单个产品 → 候选。product: {id,name,cas,synonyms}。纯函数（无 ORM）。"""
    name = product['name']
    synonyms = product.get('synonyms') or []
    cas = product.get('cas') or ''
    terms = build_terms(name, synonyms, cas)
    if not terms:
        return {'product_id': product['id'], 'query': '', 'candidates': [],
                'excluded': [], 'esearch_count': 0, 'per_term_count': {}}

    idlist, per_term_count = [], {}
    for term in terms:
        result = client.esearch(term)
        per_term_count[term] = int(result.get('count', 0))
        idlist.extend(result.get('idlist', []))
    idlist = _dedupe(idlist)

    summaries = client.esummary(idlist) or {}
    candidates, excluded = [], []
    for pmid in idlist:
        doc = summaries.get(pmid) or {}
        title = doc.get('title', '')
        name_hits, cas_hit = count_signals(title, name, synonyms, cas)
        entry = {
            'pmid': pmid,
            'title': title,
            'source': doc.get('source', ''),
            'pubdate': doc.get('pubdate', ''),
            'signal_name': bool(name_hits),
            'signal_cas': cas_hit,
        }
        if name_hits or cas_hit:
            entry['strength'] = 'high' if (name_hits and cas_hit) else 'medium'
            candidates.append(entry)
        else:
            excluded.append(entry)

    return {
        'product_id': product['id'],
        'query': ' OR '.join(terms),
        'per_term_count': per_term_count,
        'esearch_count': len(idlist),
        'candidates': candidates[:MAX_CANDIDATES],
        'excluded': excluded,
    }
