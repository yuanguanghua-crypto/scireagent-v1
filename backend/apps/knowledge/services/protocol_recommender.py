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

    def search(self, query: str, top_k: int = 5) -> list:
        """按关键词检索匹配的协议，按相关度降序"""
        if not query or self.indexer.size() == 0:
            return []

        query_lower = query.lower()
        terms = set(re.findall(r"[a-z0-9-]+", query_lower))

        scored = []
        for entry in self.indexer.get_entries():
            score = self._compute_relevance(entry, query_lower, terms)
            if score > 0:
                scored.append({
                    "id": entry["id"],
                    "title": entry["title"],
                    "source": entry["source"],
                    "score": score,
                    "text_snippet": entry["text"][:200] if entry["text"] else "",
                })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

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
        self.retriever = retriever or ProtocolRetriever()
        try:
            self.retriever.indexer.build()
        except Exception:
            pass

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
