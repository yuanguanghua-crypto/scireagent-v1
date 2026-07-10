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
                            "title": item.get("title", ""),
                            "source": source_name,
                            "text": item.get("input", ""),
                            "keywords": item.get("keywords", ""),
                            "abstract": item.get("abstract", ""),
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
