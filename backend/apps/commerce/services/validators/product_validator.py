"""Product Validator Service
Validates product structural data against external sources.
- PubChem: checks CAS, SMILES, molecular weight consistency
- BioProCorpus: cross-references product names in known protocols
"""
import logging
import re
from dataclasses import dataclass, field
from typing import Optional
import requests

logger = logging.getLogger(__name__)

PUBCHEM_BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"


def _normalize_smiles(smiles: str) -> str:
    """正则化 SMILES：去掉立体化学/电荷/氢标记，统一比较"""
    s = smiles.strip()
    # 去掉同位素标记 [nC]
    s = re.sub(r'\[\d+', '[', s)
    # 去掉立体化学标记 @ @+ @- @@ @@+ @@-
    s = re.sub(r'@[+\-]?@?', '', s)
    # 去掉氢标记 H
    s = re.sub(r'H\d?', '', s)
    # 去掉电荷标记 [n+] [n-] → 保留原子
    s = re.sub(r'\[(\w+)\][+\-]', r'\1', s)
    # 去掉显式正电荷 +
    s = s.replace('+', '').replace('-', '')
    # 统一大小写
    s = s.upper()
    return s


@dataclass
class ValidationReport:
    """聚合所有校验维度结果"""
    status: str = "pending"  # pending / running / completed
    pubchem_result: Optional[dict] = None
    pubchem_match: bool = False
    pubchem_cid: Optional[int] = None
    mismatches: list = field(default_factory=list)
    matched_protocols: list = field(default_factory=list)
    bioprocorpus_result: Optional[dict] = None
    overall_match: bool = False
    timestamp: Optional[str] = None


class PubChemClient:
    """PubChem REST API 客户端"""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    def lookup_by_cas(self, cas: str) -> Optional[dict]:
        """通过 CAS 号查询 PubChem，返回化合物信息"""
        url = f"{PUBCHEM_BASE_URL}/compound/name/{cas}/JSON"
        try:
            resp = requests.get(url, timeout=self.timeout)
            if resp.status_code != 200:
                return None
            data = resp.json()
            compounds = data.get("PC_Compounds", [])
            if not compounds:
                return None
            cid = compounds[0]["id"]["id"]["cid"]
            return {"cid": cid}
        except Exception as e:
            logger.warning(f"PubChem lookup failed for CAS {cas}: {e}")
            return None

    def compare_smiles(self, product_smiles: str, cas: str) -> dict:
        """比对产品 SMILES 与 PubChem 标准 SMILES 是否一致（正则化后比较）"""
        result = self.lookup_by_cas(cas)
        if result is None:
            return {"match": False, "cid": None, "mismatch_fields": ["cas"]}

        url = f"{PUBCHEM_BASE_URL}/compound/cid/{result['cid']}/property/CanonicalSMILES/JSON"
        try:
            resp = requests.get(url, timeout=self.timeout)
            if resp.status_code != 200:
                return {"match": False, "cid": result["cid"], "mismatch_fields": ["pubchem_api"]}
            data = resp.json()
            pubchem_smiles = next(
                (data["PropertyTable"]["Properties"][0].get(f)
                 for f in ["CanonicalSMILES", "ConnectivitySMILES", "IsomericSMILES"]
                 if data["PropertyTable"]["Properties"][0].get(f)),
                None
            )
            if pubchem_smiles is None:
                return {"match": False, "cid": result["cid"], "mismatch_fields": ["pubchem_smiles_field"]}
            # 正则化后再比较（去掉立体化学标记、电荷标注等格式差异）
            norm_product = _normalize_smiles(product_smiles)
            norm_pubchem = _normalize_smiles(pubchem_smiles)
            is_match = norm_product == norm_pubchem
            return {
                "match": is_match,
                "cid": result["cid"],
                "pubchem_smiles": pubchem_smiles,
                "product_smiles": product_smiles,
                "mismatch_fields": [] if is_match else ["smiles"],
            }
        except Exception as e:
            logger.warning(f"SMILES comparison failed for CID {result['cid']}: {e}")
            return {"match": False, "cid": result["cid"], "mismatch_fields": ["pubchem_api"]}


class BioProCorpusLookup:
    """BioProCorpus 本地索引检索 — 复用 ProtocolRetriever（14,675 条协议）

    用类级缓存避免每次 validate 都重建索引。
    """

    _retriever = None

    def __init__(self, data_dir: Optional[str] = None):
        # data_dir 参数保留以兼容旧签名，ProtocolRetriever 自己解析默认路径
        if BioProCorpusLookup._retriever is None:
            from apps.knowledge.services.protocol_recommender import ProtocolRetriever
            BioProCorpusLookup._retriever = ProtocolRetriever()

    def search(self, query: str, top_k: int = 5) -> list:
        """按关键词检索匹配的协议"""
        if not query:
            return []
        results = BioProCorpusLookup._retriever.search(query, top_k=top_k)
        return [
            {
                'id': r.get('id', ''),
                'title': r.get('title', ''),
                'source': r.get('source', ''),
                'score': r.get('score', 0),
            }
            for r in results
        ]


class ProductValidator:
    """校验产品结构数据与外部知识源的一致性"""

    def __init__(self):
        self.pubchem = PubChemClient()
        self.biocorpus = BioProCorpusLookup()
        from apps.commerce.services.validators.pubchem_enhancer import PubChemEnhancer
        self.pubchem_enhancer = PubChemEnhancer()

    def validate(self, product):
        """入口：对单个产品执行全维度校验"""
        pubchem_result = None
        pubchem_match = False
        pubchem_cid = None
        mismatches = []
        matched_protocols = []
        bioprocorpus_result = None
        molecular_properties = None
        lipinski = None
        similar_compounds = []

        # PubChem 校验
        if product.cas:
            try:
                if product.smiles:
                    cmp = self.pubchem.compare_smiles(product.smiles, product.cas)
                    pubchem_result = cmp
                    pubchem_match = cmp["match"]
                    pubchem_cid = cmp["cid"]
                    mismatches = cmp.get("mismatch_fields", [])
                else:
                    lookup = self.pubchem.lookup_by_cas(product.cas)
                    if lookup:
                        pubchem_result = lookup
                        pubchem_cid = lookup["cid"]
            except Exception as e:
                logger.error(f"PubChem validation error for product {product.id}: {e}")

        # ── PubChemEnhancer: 完整分子属性 + Lipinski + 相似度搜索 ──
        if pubchem_cid:
            try:
                molecular_properties = self.pubchem_enhancer.get_full_properties(
                    str(pubchem_cid), 'cid')
                if molecular_properties:
                    lipinski = self.pubchem_enhancer.check_lipinski(molecular_properties)
            except Exception as e:
                logger.warning(f"PubChemEnhancer properties failed for product {product.id}: {e}")
        if product.smiles and product.smiles.strip():
            try:
                similar_compounds = self.pubchem_enhancer.find_similar(
                    product.smiles, threshold=85, max_results=5)
            except Exception as e:
                logger.warning(f"PubChemEnhancer similarity failed for product {product.id}: {e}")

        # BioProCorpus 检索
        if product.name:
            try:
                matched_protocols = self.biocorpus.search(product.name)
                bioprocorpus_result = {"count": len(matched_protocols)}
            except Exception as e:
                logger.error(f"BioProCorpus search error for product {product.id}: {e}")

        overall_match = pubchem_match if product.cas else True

        report = ValidationReport(
            status="completed",
            pubchem_result=pubchem_result,
            pubchem_match=pubchem_match,
            pubchem_cid=pubchem_cid,
            mismatches=mismatches,
            matched_protocols=matched_protocols,
            bioprocorpus_result=bioprocorpus_result,
            overall_match=overall_match,
        )
        # Attach enhanced fields
        report.molecular_properties = molecular_properties
        report.lipinski = lipinski
        report.similar_compounds = similar_compounds
        return report
