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
#   2026-07-29 bump 4→5：Biotium 接入给 _match_jena_no_cache 的 matched source 追加了
#   ex_em/cas_source/product_type/match_quality 字段（见 line 190-197 字段块）。
#   该 schema 变更必须升版本，否则 Redis 中旧 v4 缺字段缓存会因版本号不变被继续命中返回。
MAPPER_VERSION = "5"


_MODIFIER_STOPWORDS = {
    'atp', 'gtp', 'ctp', 'ttp', 'utp', 'datp', 'dgtp', 'dctp', 'dttp', 'dutp',
    'atpps', 'atpγs', 'datpαs', 'datps', 'atp', 'gtp', 'ctp', 'utp', 'ttp',
    'amp', 'gmp', 'cmp', 'ump', 'tmp', 'damp', 'dgmp', 'dcmp', 'dump',
    'adp', 'gdp', 'cdp', 'udp', 'tdp', 'dadp', 'dgdp', 'dcdp', 'dudp',
    'na', 'mg', 'k', 'li', 'nh4', 'cl', 'br', 'i', 'f',
    'salt', 'sodium', 'potassium', 'lithium', 'ammonium', 'acid', 'free',
    'solution', 'water', 'buffer', 'solid', 'liquid', 'crystalline',
    'mm', 'um', 'nm', 'pm', 'mm', 'ml', 'ul', 'mg', 'ug', 'g',
}


def _modifiers_conflict(request_name: str, candidate_name: str) -> bool:
    """修饰词一致性约束：请求与候选均含非标准修饰词且无交集 → 冲突。

    防止 synonym 松匹配错配不同修饰的产品（如 Fluorescein-12-dCTP 误
    配 5-Propargylamino-dCTP-Cy5）。只对 synonym 匹配路径生效，
    name 精确匹配不受影响（精确匹配无歧义，不冲突）。

    Returns:
        True 如果两者都有修饰词且完全互斥（无交集）。
        False 如果任一无修饰词，或修饰词有重叠。
    """
    if not request_name or not candidate_name:
        return False
    req_tokens = set(re.split(r'[\s\-_/()]+', request_name.lower()))
    cand_tokens = set(re.split(r'[\s\-_/()]+', candidate_name.lower()))
    req_mods = req_tokens - _MODIFIER_STOPWORDS
    cand_mods = cand_tokens - _MODIFIER_STOPWORDS
    # 去掉纯数字（版本号、CAS 段等）
    req_mods = {t for t in req_mods if not t.isdigit()}
    cand_mods = {t for t in cand_mods if not t.isdigit()}
    if req_mods and cand_mods and req_mods.isdisjoint(cand_mods):
        return True
    return False


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


def _match_jena_no_cache(identifier: str, synonyms: list, request_name: str = None,
                         ex_em: str = None) -> dict:
    """核心匹配逻辑（无缓存包裹）：cas→name→synonyms→ex_em 真级联，跨供应商匹配。

    每个供应商独立运行级联，收集全部命中结果。Ex/Em 仅对 biotium 候选触发
    （D2 专属次级键），避免污染 jena/cayman/trilink 等核酸源。
    结果格式：
      {matched: bool, sources: [{vendor, match_key, catalog_no, ...}], summary: {...}}
    """
    index = _get_index()
    if index is None:
        return {"matched": False, "sources": [], "summary": {"scanned": 0, "matched": 0}}
    # 兼容 JenaIndex（单供应商）和 MultiVendorIndex（多供应商）
    total = getattr(index, 'total_size', lambda: 1)() if hasattr(index, 'total_size') else index.size()
    if total == 0:
        return {"matched": False, "sources": [], "summary": {"scanned": 0, "matched": 0}}

    from apps.commerce.services.jena_index import (
        extract_nucleotide_signature,
        signatures_conflict,
    )

    # 兼容单供应商（JenaIndex）和多供应商（MultiVendorIndex）
    if hasattr(index, 'get_vendors') and index.get_vendors():
        vendors = index.get_vendors()
        is_multi = True
    else:
        # 单供应商：包装为 vendor="jena"
        vendors = ["jena"]
        is_multi = False

    matches = []
    req_sig = extract_nucleotide_signature(request_name or identifier)

    for vendor in vendors:
        vendor_matched = False
        match_key = None
        record = None

        # 优先级 1: CAS 精确匹配
        if identifier and _looks_like_cas(identifier):
            if is_multi:
                cas_results = index.lookup_by_cas(identifier)
                if vendor in cas_results:
                    record = cas_results[vendor]
            else:
                record = index.lookup_by_cas(identifier)
            if record:
                match_key = "cas"

        # 优先级 2: name 匹配
        if record is None and identifier:
            if is_multi:
                name_results = index.lookup(identifier, namespace="name")
                if vendor in name_results:
                    cand = name_results[vendor]
                else:
                    cand = None
            else:
                cand = index.lookup(identifier, namespace="name")
            if cand and not signatures_conflict(req_sig, extract_nucleotide_signature(cand.product_name)):
                record = cand
                match_key = "name"

        # 优先级 3: synonyms 匹配（加修饰词一致性约束，防不同修饰产品错配）
        if record is None and synonyms:
            for syn in synonyms[:20]:
                if is_multi:
                    syn_results = index.lookup(syn.strip(), namespace="name")
                    cand = syn_results.get(vendor) if vendor in syn_results else None
                else:
                    cand = index.lookup(syn.strip(), namespace="name")
                if cand is not None and not signatures_conflict(
                    req_sig, extract_nucleotide_signature(cand.product_name)
                ) and not _modifiers_conflict(request_name or identifier, cand.product_name):
                    record = cand
                    match_key = f"synonym:{syn}"
                    break

        # 优先级 4: Ex/Em 光谱近似匹配（Biotium 专属次级键，D2）。
        # 仅对 biotium 候选触发；jena/cayman/trilink 无 ex_em 记录，天然不受影响。
        if record is None and ex_em and vendor == "biotium":
            if is_multi:
                ex_results = index.lookup_by_ex_em(ex_em)
                cand = ex_results.get(vendor)
            else:
                cand = index.lookup_by_ex_em(ex_em)
            if cand:
                record = cand
                match_key = "ex_em"

        if record:
            from apps.commerce.services.jena_index import (
                normalize_purity, normalize_storage, normalize_shipping,
                normalize_shelf_life, classify_concentration, map_category_l1,
            )
            matches.append({
                "vendor": vendor,
                "matched": True,
                "match_key": match_key,
                "catalog_no": record.catalog_no,
                "product_name": record.product_name,
                "systematic_name": record.systematic_name,
                "cas_number": record.cas_number,
                "category_path": record.category_path,
                "description": record.description,
                "source_url": record.source_url,
                # Biotium 接入新增（本方案）：透传三字段 + match_quality
                "ex_em": record.ex_em,
                "cas_source": record.cas_source,
                "product_type": record.product_type,
                "match_quality": (
                    "exact" if match_key == "cas"
                    else ("fuzzy_reference" if record.vendor == "biotium"
                          else "name")
                ),
                "normalized": {
                    "purity": normalize_purity(record.purity),
                    "storage_condition": normalize_storage(record.storage_condition),
                    "shipping_condition": normalize_shipping(record.shipping_condition),
                    "shelf_life": normalize_shelf_life(record.shelf_life),
                    "concentration": classify_concentration(record.concentration),
                    "category_l1": map_category_l1(record.category_path),
                },
            })
        else:
            matches.append({
                "vendor": vendor,
                "matched": False,
            })

    matched_count = sum(1 for m in matches if m.get("matched"))
    return {
        "matched": matched_count > 0,
        "mapper_version": MAPPER_VERSION,
        "sources": matches,
        "summary": {
            "scanned": len(matches),
            "matched": matched_count,
        },
    }


def match_jena(identifier: str, namespace: str = "name", synonyms: list | None = None,
                request_name: str = None, ex_em: str = None) -> dict:
    """jena 匹配入口（L1 缓存包裹，TTL 30 天）。

    内部真级联：identifier 先按 CAS 查，miss 后按 name 查，再 miss 走 synonyms，
    最后（仅 biotium）按 Ex/Em 光谱近似查（D2 专属次级键）。
    namespace 仅影响缓存分桶（cas/name），不影响查询优先级——
    因为「CAS miss 时 name 兜底」是正确语义（产品 CAS 可能填错或 jena 未索引该 CAS）。

    Args:
        identifier: 主标识符（CAS 或 name）
        namespace: 缓存分桶标识（cas / name）
        synonyms: PubChem 提供的同义词列表（增量命中关键）
        request_name: 研究者原始产品名（权威身份），供 name/synonym 路径做糖型一致性
            约束（铁律②）。务必传 SC 产品名，勿传 synonyms（会反带偏请求侧签名）。
        ex_em: 可选 Ex/Em 光谱串（如 "484/504"）。仅对 biotium 候选触发光谱近似匹配，
            不污染 jena/cayman/trilink 等核酸源。命中按 fuzzy_reference 标记。

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

    # Biotium 光谱近似匹配需纳入缓存键，避免与无 ex_em 的同名请求混淆
    if ex_em:
        cache_key = f"{cache_key}|ex_em:{ex_em}"

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
        result = _match_jena_no_cache(identifier, synonyms, request_name, ex_em)
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
