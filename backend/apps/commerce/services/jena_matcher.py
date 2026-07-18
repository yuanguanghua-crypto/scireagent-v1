"""jena 匹配服务（策略 B：本地索引常驻 + L1 缓存）。

按 cas→name→synonyms 优先级查 jena 本地索引，命中经归一化函数映射 Product choices，
DataSourceCache L1 缓存包裹（TTL 30 天，jena 数据静态）。

不直接落库，仅返回草案供研究员确认预填（FIVE_DATASOURCES.md §5.4 铁律）。
"""
import hashlib
import logging
import re

from apps.documents.services.datasource_cache import get_cache, set_cache

logger = logging.getLogger(__name__)

# jena 数据静态，L1 TTL 30 天（同 PubChem）
JENA_MATCH_TTL = 60 * 60 * 24 * 30

# 映射器版本：随 map_category_l1 / classify_concentration 等归一化逻辑变更而递增。
# 缓存命中时校验此版本——缺版本或版本不符的旧缓存（可能带错误 slug，
# 如预修复把 SC8001 映射成不存在的 'probes_epigenetics'）必须被忽略并重查。
# v3（P2-2）：classify_concentration 对齐 canonical 正则（稀释比 1:1000 现保留、
# "5 mg/ml (photometrically)" 现保留），旧缓存的 concentration 归一化值须失效重查。
# v4（A 修复，铁律②）：name/synonym 松匹配加糖型一致性约束（碱基/脱氧-核糖冲突
#   即拒收，杜绝 dTTP→dGTP 类化学错配）。bump 以强制失效旧 L1 缓存（旧缓存曾把
#   SC8068/8069 错配为 PASS，须忽略重查）。
MAPPER_VERSION = "4"


def _looks_like_cas(s: str) -> bool:
    r"""CAS 号形态识别（\d{2,7}-\d{2}-\d）。避免非 CAS 字符串被误 CAS 查询。"""
    return bool(re.match(r"^\s*\d{2,7}-\d{2}-\d\s*$", s))


def _get_index():
    """获取 jena 索引（惰性，进程级单例）。异常返回 None（不阻断主流程）。"""
    from apps.commerce.services.jena_index import get_shared_jena_index
    try:
        return get_shared_jena_index()
    except Exception as e:
        logger.warning(f"jena match index unavailable: {e}")
        return None


def _match_jena_no_cache(identifier: str, synonyms: list, request_name: str = None) -> dict:
    """核心匹配逻辑（无缓存包裹）：cas→name→synonyms 真级联。

    identifier 优先当 CAS 查，miss 后当 name 查，再 miss 走 synonyms 模糊。
    CAS 与 name 的语义从调用方（enrich view）传入的 namespace 推断：
    若 identifier 形如 CAS 号 → 先 CAS 再 name；否则直接 name。

    request_name：研究者原始产品名（权威身份），用于 name/synonym 路径的
    糖型一致性约束（铁律②）。取自 SC 产品名，不取自 synonyms——synonyms
    来自 PubChem 且可能含与候选相同的修饰词，会反向污染请求侧签名。
    """
    index = _get_index()
    if index is None or index.size() == 0:
        return {"matched": False}

    from apps.commerce.services.jena_index import (
        extract_nucleotide_signature,
        signatures_conflict,
    )

    match_key = None
    record = None
    req_sig = extract_nucleotide_signature(request_name or identifier)

    # 优先级 1: CAS 精确匹配（仅当 identifier 看起来像 CAS 号）。CAS 精确命中即同化合物，
    # 糖型必然一致，不经糖型约束。
    if identifier and _looks_like_cas(identifier):
        record = index.lookup_by_cas(identifier)
        if record:
            match_key = "cas"

    # 优先级 2: name 精确/模糊匹配（CAS miss 或 identifier 非 CAS）
    if record is None and identifier:
        cand = index.lookup(identifier, namespace="name")
        if cand and not signatures_conflict(req_sig, extract_nucleotide_signature(cand.product_name)):
            record = cand
            match_key = "name"

    # 优先级 3: synonyms 逐条模糊匹配（糖型约束以 request_name 为准，不与 synonym 自身比较）
    if record is None and synonyms:
        for syn in synonyms[:20]:  # 限制 20 条，避免超长查询
            cand = index.lookup(syn.strip(), namespace="name")
            if cand is not None and not signatures_conflict(
                req_sig, extract_nucleotide_signature(cand.product_name)
            ):
                record = cand
                match_key = f"synonym:{syn}"
                break

    if record is None:
        return {"matched": False}

    # 命中：归一化规格字段
    from apps.commerce.services.jena_index import (
        normalize_purity,
        normalize_storage,
        normalize_shipping,
        normalize_shelf_life,
        classify_concentration,
        map_category_l1,
    )

    return {
        "matched": True,
        "match_key": match_key,
        "catalog_no": record.catalog_no,
        "product_name": record.product_name,
        "systematic_name": record.systematic_name,
        "cas_number": record.cas_number,
        "category_path": record.category_path,
        "mapper_version": MAPPER_VERSION,
        "normalized": {
            "purity": normalize_purity(record.purity),
            "storage_condition": normalize_storage(record.storage_condition),
            "shipping_condition": normalize_shipping(record.shipping_condition),
            "shelf_life": normalize_shelf_life(record.shelf_life),
            "concentration": classify_concentration(record.concentration),
            "category_l1": map_category_l1(record.category_path),
        },
    }


def match_jena(identifier: str, namespace: str = "name", synonyms: list | None = None,
                request_name: str = None) -> dict:
    """jena 匹配入口（L1 缓存包裹，TTL 30 天）。

    内部真级联：identifier 先按 CAS 查，miss 后按 name 查，再 miss 走 synonyms。
    namespace 仅影响缓存分桶（cas/name），不影响查询优先级——
    因为「CAS miss 时 name 兜底」是正确语义（产品 CAS 可能填错或 jena 未索引该 CAS）。

    Args:
        identifier: 主标识符（CAS 或 name）
        namespace: 缓存分桶标识（cas / name）
        synonyms: PubChem 提供的同义词列表（增量命中关键）
        request_name: 研究者原始产品名（权威身份），供 name/synonym 路径做糖型一致性
            约束（铁律②）。务必传 SC 产品名，勿传 synonyms（会反带偏请求侧签名）。

    Returns:
        {matched: bool, ...}。异常时降级 {matched: False, error: str}。
    """
    if not identifier and not synonyms:
        return {"matched": False}

    synonyms = list(synonyms or [])

    # L1 缓存：namespace 区分 cas / name 桶，query_key 取 identifier 或 synonyms hash
    cache_ns = namespace if namespace in ("cas", "name") else "name"
    cache_key = identifier or ""

    if not cache_key:
        # 仅有 synonyms 时，用排序后 hash 建 key
        synonyms_sorted = tuple(sorted(s.lower() for s in synonyms if s.strip()))
        cache_key = hashlib.md5(str(synonyms_sorted).encode(), usedforsecurity=False).hexdigest()[:12]
        cache_ns = "synonym_hash"

    # 命中缓存
    try:
        entry = get_cache("jena_match", cache_key, cache_ns)
        if entry is not None and not entry.is_stale:
            data = entry.get_data()
            # 预修复缓存（缺 mapper_version 或版本不符）可能带错误 slug，
            # 视为失效强制重查，避免陈旧错误结果长期驻留 30 天。
            if data.get("mapper_version") == MAPPER_VERSION:
                return data
    except Exception:
        pass

    # 实际查询
    try:
        result = _match_jena_no_cache(identifier, synonyms, request_name)
    except Exception as e:
        logger.warning(f"jena match failed for {cache_key}: {e}")
        return {"matched": False, "error": str(e)}

    # 写 L1（仅 matched=True 写，减少缓存膨胀）
    if result.get("matched"):
        try:
            set_cache("jena_match", cache_key, cache_ns, result, ttl_seconds=JENA_MATCH_TTL)
        except Exception:
            pass

    return result
