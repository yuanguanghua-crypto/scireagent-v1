"""Protocol Recommender Service
Recommends experimental protocols from BioProCorpus based on product information.
- BioProCorpusIndexer: builds search index from JSON protocol files
- ProtocolRetriever: keyword-based search over indexed protocols
- ProtocolRecommender: product-to-protocol recommendation
"""
import json
import logging
import os
import re
import threading
from typing import Optional

logger = logging.getLogger(__name__)

import html as html_lib


BIOPROCORPUS_DIR = os.environ.get(
    "BIOPROCORPUS_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                 "data", "bioprocorpus"),
)


class BioProCorpusIndexer:
    """BioProCorpus 索引器：从 JSON 文件构建内存索引"""

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir or BIOPROCORPUS_DIR
        self._entries = []

    def build(self):
        """从所有 JSON 源文件构建索引"""
        self._entries = []
        source_files = self._find_source_files()
        for fpath in source_files:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    source_name = os.path.basename(fpath).replace(".json", "")
                    for item in data:
                        self._entries.append({
                            "id": item.get("id", ""),
                            "title": html_lib.unescape(item.get("title", "")),
                            "source": source_name,
                            "text": item.get("input", ""),
                            "keywords": item.get("keywords", ""),
                            "abstract": html_lib.unescape(item.get("abstract", "")),
                            "url": item.get("url", ""),
                            "hierarchical_protocol": item.get("hierarchical_protocol", {}),
                            "method": item.get("method", ""),
                        })
            except Exception as e:
                logger.warning(f"Failed to index {fpath}: {e}")

    def size(self) -> int:
        return len(self._entries)

    def list_sources(self) -> list:
        """列出所有可用的协议源名称"""
        return list(set(e["source"] for e in self._entries))

    def _find_source_files(self) -> list:
        if not os.path.exists(self.data_dir):
            return []
        files = os.listdir(self.data_dir)
        return [
            os.path.join(self.data_dir, f)
            for f in files
            if f.endswith(".json") and not f.startswith("PQA") and not f.startswith("ERR")
            and not f.startswith("ORD") and not f.startswith("GEN")
        ]

    def get_entries(self) -> list:
        return self._entries


class ProtocolRetriever:
    """协议检索器：基于关键词匹配的检索"""

    def __init__(self, indexer: Optional[BioProCorpusIndexer] = None):
        self.indexer = indexer or BioProCorpusIndexer()
        if self.indexer.size() == 0:
            try:
                self.indexer.build()
            except Exception as e:
                logger.warning(f"Auto-build index failed: {e}")

    def search(self, query: str, top_k: int = 5, include_content: bool = False) -> list:
        """按关键词检索匹配的协议，按相关度降序。

        Args:
            include_content: 是否返回试剂/设备/步骤等富内容
        """
        if not query or self.indexer.size() == 0:
            return []

        query_lower = query.lower()
        terms = set(re.findall(r"[a-z0-9-]+", query_lower))

        scored = []
        for entry in self.indexer.get_entries():
            score = self._compute_relevance(entry, query_lower, terms)
            if score > 0:
                result = {
                    "id": entry["id"],
                    "title": entry["title"],
                    "source": entry["source"],
                    "score": score,
                    "text_snippet": entry["text"][:200] if entry["text"] else "",
                }
                if include_content:
                    result["abstract"] = entry.get("abstract", "")
                    result["url"] = entry.get("url", "")
                    # 扩展章节匹配: 试剂/溶液/配方/材料 的各种命名模式
                    result["reagents"] = self._extract_section(entry.get("text", ""), "Reagents")
                    result["equipment"] = self._extract_section(entry.get("text", ""), "Equipment")
                    result["materials"] = self._extract_section(entry.get("text", ""), "Biological materials")
                    # 额外提取 solutions/recipes（很多 Bio-protocol 协议试剂列在这些章节下）
                    if not result["reagents"]:
                        result["reagents"] = self._extract_section(entry.get("text", ""), "Solutions")
                    if not result["reagents"]:
                        result["reagents"] = self._extract_section(entry.get("text", ""), "Recipes")
                    if not result["materials"]:
                        result["materials"] = self._extract_section(entry.get("text", ""), "Materials")
                    if not result["materials"]:
                        result["materials"] = self._extract_section(entry.get("text", ""), "Laboratory supplies")
                    result["steps"] = self._extract_steps(entry.get("hierarchical_protocol", {}))
                    result["method_hint"] = entry.get("method", "")
                scored.append(result)

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    @staticmethod
    def _extract_section(input_text: str, section_name: str) -> str:
        """从 BioProCorpus 的 input Markdown 文本中按章节标题提取内容。

        支持 # Reagents、# Equipment、# Biological materials 等章节。
        """
        if not input_text:
            return ""
        import re as regex
        # Match both "# Reagent" and "# Reagents" (Bio-protocol uses # Reagents plural only)
        # Multiple patterns for different section naming conventions
        patterns = [
            rf'#\s*{regex.escape(section_name)}s?\s*\n(.*?)(?=\n#\s|\Z)',  # "Reagents" or "Reagent"
            rf'#\s*{regex.escape(section_name)}.*?\n(.*?)(?=\n#\s|\Z)',   # looser match
        ]
        for pattern in patterns:
            match = regex.search(pattern, input_text, regex.DOTALL)
            if match:
                content = match.group(1).strip()
                # 清理 LaTeX 残留和换行标记
                content = regex.sub(r'\\begin\{array.*?\\end\{array\}', '', content, flags=regex.DOTALL)
                content = regex.sub(r'eginarrayr?\{[^}]*\}', '', content)
                content = regex.sub(r'endarray', '', content)
                return content
        return ""

    @staticmethod
    def _extract_steps(hierarchical: dict) -> list:
        """从 hierarchical_protocol 提取层级步骤列表。

        Input:
            {"1": {"title": "..."}, "1.1": "step body", "1.2": "step body", "2": {"title": "..."}, ...}

        Returns:
            [{"step_no": "1.1", "title": "...", "body": "step body"}, ...]
        """
        if not hierarchical:
            return []

        steps = []
        # 先收集 section titles
        section_titles = {}
        for key, val in hierarchical.items():
            if isinstance(val, dict) and "title" in val:
                section_titles[key] = val["title"]

        for key, val in hierarchical.items():
            if "." not in key:
                continue  # skip section headers, keep only leaf steps
            title = ""
            # 找最近的父级标题
            parts = key.rsplit(".", 1)
            if parts[0] in section_titles:
                title = section_titles[parts[0]]
            if isinstance(val, str):
                steps.append({
                    "step_no": key,
                    "title": title,
                    "body": val.strip(),
                })

        return steps

    def _compute_relevance(self, entry: dict, query_lower: str, terms: set) -> float:
        """计算协议与查询的相关度分数"""
        score = 0.0
        text = (entry["title"] + " " + (entry.get("keywords") or "") + " " + (entry.get("text") or "")[:1000]).lower()

        # 精确匹配标题
        if query_lower in entry["title"].lower():
            score += 5.0

        # 关键词命中
        for term in terms:
            if len(term) < 2:
                continue
            count = text.count(term)
            if count > 0:
                score += count * 1.0

        return score


class ProtocolRecommender:
    """产品协议推荐器"""

    def __init__(self, retriever: Optional[ProtocolRetriever] = None):
        # 不传 retriever 时 new 一个独立的（ProtocolRetriever.__init__ 已 auto-build）。
        # 生产路径应改用 get_shared_recommender() 复用进程级单例，避免每次请求 rebuild 175MB 索引。
        # 测试可直接 new 后手动注入 retriever.indexer._entries。
        self.retriever = retriever or ProtocolRetriever()

    def recommend(self, product_name: str, top_k: int = 5) -> list:
        """为给定产品名推荐相关协议"""
        results = self.retriever.search(product_name, top_k=top_k)
        recommendations = []
        for r in results:
            recommendations.append({
                "protocol": {"id": r["id"], "title": r["title"]},
                "relevance_score": r["score"],
                "match_reason": f"Product name/keyword found in {r['source']} protocol",
            })
        return recommendations

    def recommend_expanded(self, product_name: str, category_path: Optional[str] = None,
                           synonyms: Optional[list] = None, top_k: int = 5,
                           include_content: bool = False,
                           enforce_core_tokens: bool = True) -> list:
        """扩展查询后推荐：产品名 → 多检索串 → 分别检索 → 合并去重。

        解决冷门精确名（如 5-Propargylamino-CTP）原 search 整体匹配返回 0 的问题：
        碎片化产品名（CTP / Propargyl）+ jena 分类路径领域关键词
        （nucleotide / labeling / click chemistry）+ 同义词，扩大命中面。
        返回结构与 retriever.search 一致（含 matched_query 标记来源）。

        ★ N-1 加固（2026-11-18）：
          1. 碎片必须过化学词根门（见 _chemical_root_of），不再拿任意 ≥3 字母串当检索词；
          2. **核心 token 回验**：来自产品名（整体名/词根）的命中，其标题或正文片段
             必须含产品名任一核心 token，否则判为错配丢弃。分类/同义词来源豁免
             —— 它们来自产品自身的 jena 分类与权威同义词，不是对名字的猜测。
          3. 每条结果写 match_reason / match_confidence（旧实现只有 matched_query，
             用户看到推荐却看不出为什么被推荐）。
          enforce_core_tokens=False 仅供排障对比使用，生产路径必须保持 True。
        """
        tagged = expand_protocol_query_tagged(
            product_name, category_path=category_path, synonyms=synonyms)
        if not tagged:
            return []

        core = core_name_tokens(product_name)
        lists = []
        dropped = 0
        for item in tagged:
            q, kind = item["query"], item["kind"]
            res = self.retriever.search(q, top_k=top_k, include_content=include_content)
            kept = []
            for r in res:
                r["matched_query"] = q
                r["match_kind"] = kind
                r["match_reason"] = _MATCH_REASON_BY_KIND[kind].format(q=q)
                r["match_confidence"] = _MATCH_CONFIDENCE_BY_KIND[kind]
                if enforce_core_tokens and core and kind in ("name", "fragment"):
                    hay = f"{r.get('title') or ''} {r.get('text_snippet') or ''}".lower()
                    if not any(tok in hay for tok in core):
                        dropped += 1
                        continue
                kept.append(r)
            lists.append(kept)

        if dropped:
            logger.info(
                "recommend_expanded: core-token gate dropped %d result(s) for %r (core=%s)",
                dropped, product_name, core,
            )
        return _merge_results(lists, top_k)


# ── 查询扩展（TDD #4）：把产品名扩成多个检索串，提升 BioProCorpus 命中率 ──
# 领域关键词：按 jena 分类路径段抽取；覆盖核苷酸/标记/点击化学等核心场景。
_CATEGORY_KEYWORDS = ("nucleotide", "click chemistry", "rna", "labeling",
                      "cuac", "epigenetics", "probe", "modified nucleotide")

# ── 化学词根白名单（N-1，2026-11-18 立）───────────────────────────────────
# 背景：旧实现把产品名里**任意长度 ≥3 的字母串**都当独立检索词。
#   DS 复测 `DS-A203-probe` ⇒ `A203`、`probe` 各自成为查询 ⇒ 召回 5 条含
#   "Probe" 的无关协议（score 恒 0.7，match_reason 为空，用户无从判断为何推荐）。
# 纪律：**宁 miss 不错配** ⇒ 碎片必须落在「化学身份」词根上才允许检索。
#
# ★ 本表只收能**标识试剂身份**的词根；刻意不收 pbs / tris / probe / kit /
#   buffer 这类"几乎每个协议正文都出现"的通用词 —— 收进来等于把噪声源装回去。
# ★ 维护约定：新产品线（如新增染料/交联剂）需在此补词根；未补则碎片检索会
#   主动 miss，这是**预期行为**，不要为了让召回变多而放宽匹配。
_REAGENT_ROOTS = (
    # 核苷酸 / 脱氧核苷酸 / 双脱氧 / 环核苷酸
    "atp", "adp", "amp", "ctp", "cdp", "cmp", "gtp", "gdp", "gmp",
    "ttp", "tdp", "tmp", "utp", "udp", "ump", "itp", "idp", "imp",
    "datp", "dctp", "dgtp", "dttp", "dutp", "ddntp", "dntp", "ntp", "ndp", "nmp",
    "nad", "fad", "fmn", "coa", "sam", "sah", "camp", "cgmp",
    # 核酸形态
    "dna", "rna", "cdna", "crna", "mrna", "trna", "rrna",
    "sirna", "shrna", "mirna", "lncrna", "ncrna", "grna", "sgrna", "aso",
    # 碱基 / 核苷 / 糖
    "adenine", "adenosine", "cytidine", "cytosine", "guanine", "guanosine",
    "thymidine", "thymine", "uridine", "uracil", "inosine", "xanthine",
    "hypoxanthine", "ribose", "deoxyribose", "nucleotide", "nucleoside",
    "nucleobase",
    # 修饰基团 / 连接臂（本项目产品名最常见的化学前缀）
    "propargyl", "propargylamino", "ethynyl", "vinyl", "allyl", "benzyl",
    "azide", "azido", "diazo", "hydrazide", "hydroxylamine", "alkoxyamine",
    "maleimide", "succinimidyl", "nhs", "thiol", "dithiol", "disulfide",
    "phosphorothioate", "phosphoramidite", "cpg", "spacer", "linker",
    "crosslinker", "peg", "peg4", "peg8",
    # 点击化学
    "dbco", "bcn", "tco", "tetrazine", "cyclooctyne", "norbornene", "alkyne",
    # 荧光 / 淬灭 / 标记
    "fluorescein", "fitc", "tritc", "rhodamine", "cyanine", "cy3", "cy5", "cy7",
    "bodipy", "coumarin", "pyrene", "alexa", "atto", "quasar",
    "fam", "hex", "joe", "rox", "tamra", "dabcyl", "bhq", "mgb",
    "biotin", "biotinyl", "desthiobiotin", "digoxigenin", "dig",
)

# 长度 ≤4 的词根只做精确匹配，避免 amp→amplification、dig→digital 这类误扩。
_ROOT_PREFIX_MIN_LEN = 5
# 词根 + 修饰后缀的允许长度：propargyl(9) + amino(5) = propargylamino
_ROOT_PREFIX_MAX_TAIL = 8


def _chemical_root_of(fragment: Optional[str]) -> Optional[str]:
    """判断碎片是否具备化学身份；是则返回应使用的检索词，否则 None。

    规则：
      1. 整体命中 _REAGENT_ROOTS（忽略大小写）→ 返回碎片**原样**，
         保留 CTP / dUTP / Cy5 这类大小写形态。
      2. 长度 ≥5 的词根作为前缀、尾部 ≤8 字符且全为字母 → 返回该词根。
         例：Propargylamino → propargyl；Biotinylated → biotin。
      3. 其余一律 None。**宁 miss 不错配** —— 拿不准就当没有。
    """
    if not fragment:
        return None
    low = fragment.lower()
    if not low.isalnum():
        return None
    if low in _REAGENT_ROOTS:
        return fragment
    for root in _REAGENT_ROOTS:
        if len(root) < _ROOT_PREFIX_MIN_LEN:
            continue
        if low.startswith(root):
            tail = low[len(root):]
            if tail.isalpha() and len(tail) <= _ROOT_PREFIX_MAX_TAIL:
                return root
    return None


def core_name_tokens(product_name: Optional[str]) -> list:
    """产品名的「核心 token」—— 化学词根 + 编号片段（如 A203 / SC8101）。

    用途：**检索结果回验**。协议标题/正文里不含任一核心 token ⇒ 判为错配丢弃。
    这正是 `DS-A203-probe` 案例的闸门：核心 token 只有 `a203`，
    那 5 条只因含 "Probe" 而被召回、标题里没有 A203 的协议会被清掉。
    """
    out: list = []
    seen = set()
    for frag in re.findall(r"[A-Za-z][A-Za-z0-9]*", product_name or ""):
        tok = _chemical_root_of(frag)
        if tok:
            tok = tok.lower()
        elif re.fullmatch(r"[A-Za-z]{1,4}\d{2,}", frag):
            tok = frag.lower()      # 目录号/位次编号，如 A203、SC8101
        else:
            continue
        if tok not in seen:
            seen.add(tok)
            out.append(tok)
    return out


# ── 命中来源 → 理由 / 置信度（N-1：旧实现 recommend_expanded 完全不写 match_reason）──
_MATCH_REASON_BY_KIND = {
    "name": "协议标题/正文命中产品名「{q}」",
    "fragment": "协议标题/正文命中产品名词根「{q}」",
    "category": "按产品分类路径关键词「{q}」扩展命中",
    "synonym": "按产品同义词「{q}」扩展命中",
}
_MATCH_CONFIDENCE_BY_KIND = {
    "name": "high",
    "fragment": "low",      # 词根猜测，置信度最低
    "category": "medium",
    "synonym": "medium",
}


def expand_protocol_query_tagged(product_name: Optional[str],
                                 category_path: Optional[str] = None,
                                 synonyms: Optional[list] = None) -> list:
    """同 expand_protocol_query，但每个检索串带上**来源类型**。

    返回 ``[{'query': str, 'kind': 'name'|'fragment'|'category'|'synonym'}, ...]``
    ``recommend_expanded`` 用它区分「产品名字面猜测」与「产品自身分类/同义词」，
    因为后者不该被核心 token 闸门误杀。
    """
    tagged: list = []
    if product_name and product_name.strip():
        tagged.append({"query": product_name.strip(), "kind": "name"})
    # 碎片化：只保留过化学词根门的片段（见 _chemical_root_of）
    for frag in re.findall(r"[A-Za-z][A-Za-z0-9]*", product_name or ""):
        root = _chemical_root_of(frag)
        if root:
            tagged.append({"query": root, "kind": "fragment"})
    # 分类路径关键词
    if category_path:
        for seg in category_path.split("|"):
            seg_l = seg.lower()
            for kw in _CATEGORY_KEYWORDS:
                if kw in seg_l:
                    tagged.append({"query": kw, "kind": "category"})
    # 同义词
    if synonyms:
        for s in synonyms[:10]:
            if s and str(s).strip():
                tagged.append({"query": str(s).strip(), "kind": "synonym"})
    # 去重保序（同串只保留首次出现的 kind）
    seen = set()
    out = []
    for item in tagged:
        q = (item["query"] or "").strip()
        if not q or q.lower() in seen:
            continue
        seen.add(q.lower())
        out.append({"query": q, "kind": item["kind"]})
    return out


def expand_protocol_query(product_name: Optional[str], category_path: Optional[str] = None,
                          synonyms: Optional[list] = None) -> list:
    """把产品名扩展成多个检索串（去重保序）。

    策略：
      1. 原始产品名（精确）
      2. 产品名碎片化：**仅保留过化学词根门的片段**（如 'CTP'、'Propargyl'）
      3. jena 分类路径段中的领域关键词（nucleotide / labeling / click chemistry …）
      4. 传入的同义词/系统名

    实现见 expand_protocol_query_tagged；本函数保持旧签名与返回类型（list[str]）。
    """
    return [item["query"] for item in expand_protocol_query_tagged(
        product_name, category_path=category_path, synonyms=synonyms)]


def _merge_results(result_lists: list, top_k: int) -> list:
    """合并多次检索结果：同 id 取最高分，按分降序，截断 top_k。"""
    best: dict = {}
    for results in result_lists:
        for r in results:
            rid = r.get("id")
            if rid not in best or r["score"] > best[rid]["score"]:
                best[rid] = r
    merged = sorted(best.values(), key=lambda x: x["score"], reverse=True)
    return merged[:top_k]


# ── 进程级共享单例（惰性构建，线程安全）──────────────────────────────────────
# 解决「每次 HTTP 请求 new ProtocolRecommender() → rebuild 175MB 索引」的性能问题。
# 索引在首次调用时构建一次，之后全进程复用。生产调用点应使用 get_shared_recommender()。
# 测试请直接 new ProtocolRecommender()/ProtocolRetriever() 注入独立实例，不要用单例。
# 详见 docs/DATASOURCE_RELIABILITY.md §7
_shared_retriever: Optional[ProtocolRetriever] = None
_shared_retriever_lock = threading.Lock()

_shared_recommender: Optional[ProtocolRecommender] = None
_shared_recommender_lock = threading.Lock()


def get_shared_retriever() -> ProtocolRetriever:
    """获取进程级共享 ProtocolRetriever 单例（惰性、线程安全、双检锁）。

    首次调用时构建索引（读取并解析全部 BioProCorpus JSON），之后全进程复用。
    BioProCorpusLookup 与 ProtocolRecommender 共享同一份索引。
    """
    global _shared_retriever
    if _shared_retriever is None:
        with _shared_retriever_lock:
            if _shared_retriever is None:
                logger.info("Building BioProCorpus shared index (one-time, process-level)...")
                retriever = ProtocolRetriever()
                logger.info(f"BioProCorpus shared index ready: {retriever.indexer.size()} entries")
                _shared_retriever = retriever
    return _shared_retriever


def get_shared_recommender() -> ProtocolRecommender:
    """获取进程级共享 ProtocolRecommender 单例（复用 get_shared_retriever 的索引）。

    生产 AI AUTO MATCH 调用点应使用此函数，而非直接 new ProtocolRecommender()。
    """
    global _shared_recommender
    if _shared_recommender is None:
        with _shared_recommender_lock:
            if _shared_recommender is None:
                _shared_recommender = ProtocolRecommender(get_shared_retriever())
    return _shared_recommender
