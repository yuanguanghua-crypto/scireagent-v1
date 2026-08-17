"""只读探针：按设计稿的协议相关性算法，对当前全部产品跑一遍，输出真实状态报告。

不做任何 DB 写入（不持久化 relevance_score 等），仅读取并计算、打印聚合报告。
用法：
    DB_ENGINE=sqlite python manage.py probe_protocol_relevance
    DB_ENGINE=sqlite python manage.py probe_protocol_relevance --topn 10 --min-overlap 2

文献信号来源：Bioz 缓存（DataSourceCache，allow_stale=True 取 14 天 TTL 已过的快照，
代表 2026-07-30 左右的真实文献池，离线、可复现、不依赖网络）。
jena 匹配：match_jena 走本地索引 + jena_match 缓存（离线）。
"""
import logging
import re
from collections import Counter, defaultdict

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

# ── 算法默认参数（与设计稿一致，可调） ──
MIN_OVERLAP = 2          # 文献与协议语料关键词重叠阈值 → 计为 1 条证据
TOPN = 10                # 每个产品默认展示/筛选上限
W_DIRECT = 4.0           # 直接用法权重
W_EVIDENCE = 0.5         # 每条文献证据权重（evidence_count 截断到 10）
W_BIOPRO = 0.3           # BioProCorpus 代理分（归一化 0-1）权重
W_EVLEVEL = 0.4          # 证据等级权重
W_FEATURED = 0.5         # 编辑推荐权重

STOPWORDS = set("""
the a an and or of to in for with on at by from as is are be this that these those we our
using use used uses employ employed employs employment apply applied applies application
method methods protocol protocols technique techniques sample samples cell cells based
via using into using using can may using using using using using using using using using using
""".split())

USAGE_VERBS = re.compile(r"\b(use|uses|used|using|employ|employs|employed|appl(?:y|ies|ied|ying)|utili[sz]e|utili[sz]es|utili[sz]ed|perform(?:s|ed)?|conduct(?:s|ed)?)\b")


def tokenize(text):
    if not text:
        return set()
    toks = re.findall(r"[a-z0-9][a-z0-9\-]{2,}", text.lower())
    return {t for t in toks if t not in STOPWORDS and not t.isdigit()}


def has_usage_verb(text):
    return bool(USAGE_VERBS.search(text or ""))


def evidence_level_score(level):
    return {"high": 3, "curated": 3, "medium": 2, "low": 1}.get((level or "").lower(), 1)


def get_bioz_refs_for_product(product):
    """返回该产品的 Bioz 文献记录列表（离线：jena 本地匹配 + bioz 过期缓存）。

    product 为 dict（来自 Product.objects.values，避免 SELECT 整行触发缺失的 archived 列）。
    返回 (refs, jena_matched, vendor, catalog_no)。
    """
    try:
        from apps.commerce.services.jena_matcher import match_jena, _looks_like_cas
    except Exception as e:
        logger.warning(f"jena_matcher import failed: {e}")
        return [], False, "", ""

    user_cas = (product.get("cas") or "").strip()
    search_name = (product.get("name") or "").strip()
    synonyms = product.get("synonyms") or []
    identifier = user_cas or search_name
    namespace = "cas" if (user_cas and _looks_like_cas(user_cas)) else "name"

    jena = {"matched": False, "sources": []}
    try:
        if identifier:
            jena = match_jena(identifier=identifier, namespace=namespace,
                              synonyms=synonyms, request_name=search_name)
        if not jena.get("matched") and search_name and namespace == "cas":
            jena = match_jena(identifier=search_name, namespace="name",
                              synonyms=synonyms, request_name=search_name)
    except Exception as e:
        logger.warning(f"match_jena failed for {product.get('catalog_no')}: {e}")
        return [], False, "", ""

    if not jena.get("matched"):
        return [], False, "", ""

    # 解析 vendor + catalog_no（兼容新旧结构）
    vendor_for_bioz = "Jena Bioscience"
    catalog_no = jena.get("catalog_no", "")
    if "sources" in jena and not catalog_no:
        matched_sources = [s for s in jena.get("sources", []) if s.get("matched")]
        s = next((x for x in matched_sources if x.get("vendor") == "jena"), None) or (matched_sources[0] if matched_sources else None)
        if s:
            v = (s.get("vendor") or "").lower()
            vendor_for_bioz = {"jena": "Jena Bioscience", "cayman": "Cayman Chemical",
                               "trilink": "TriLink BioTechnologies", "biotium": "Biotium"}.get(v, s.get("vendor", "Jena Bioscience"))
            catalog_no = s.get("catalog_no", "")
    else:
        v = (jena.get("vendor") or "jena").lower()
        vendor_for_bioz = {"jena": "Jena Bioscience", "cayman": "Cayman Chemical",
                           "trilink": "TriLink BioTechnologies", "biotium": "Biotium"}.get(v, "Jena Bioscience")

    if not catalog_no:
        return [], True, vendor_for_bioz, ""

    # 离线取 bioz 过期缓存（allow_stale=True）
    try:
        from apps.documents.services.datasource_cache import get_cache
        entry = get_cache("bioz", f"{vendor_for_bioz}:{catalog_no}", "sku", allow_stale=True)
        refs = entry.get_data() if entry is not None else []
    except Exception as e:
        logger.warning(f"bioz cache read failed for {catalog_no}: {e}")
        refs = []
    return (refs or []), True, vendor_for_bioz, catalog_no


def build_protocol_corpus(protocol):
    method_name = ""
    try:
        if protocol.method_id and protocol.method:
            method_name = protocol.method.name or ""
    except Exception:
        method_name = ""
    parts = [protocol.name or "", method_name, protocol.objective or "",
             protocol.reagents or "", protocol.materials or ""]
    return " ".join(p for p in parts if p)


def score_pair(product, protocol, method_protocol, product_method, bioz_refs, jena_catalog_no=""):
    """返回 dict: score, evidence_count, direct_usage, tier, basis"""
    corpus = build_protocol_corpus(protocol)
    corpus_tokens = tokenize(corpus)
    product_tokens = tokenize(product.get("name") or "")

    # 严格直接用法：文献正文须出现产品全名或 jena 目录号（强身份串）+ 用法动词，
    # 避免产品名里的常见生化词（atp/amino 等）在文献中泛现导致的假阳性。
    name_l = (product.get("name") or "").lower()
    cat_l = (jena_catalog_no or "").lower()
    strong_ids = [s for s in [name_l, cat_l] if s and len(s) >= 4]

    evidence_count = 0
    direct_usage = False
    for ref in bioz_refs:
        ref_text = " ".join([
            ref.get("article_title", "") or "",
            " ".join(ref.get("techniques", []) or []),
            ref.get("long", "") or "",
            ref.get("medium", "") or "",
        ])
        ref_lower = ref_text.lower()
        ref_tokens = tokenize(ref_lower)
        if len(corpus_tokens & ref_tokens) >= MIN_OVERLAP:
            evidence_count += 1
        if strong_ids and any(sid in ref_lower for sid in strong_ids) and has_usage_verb(ref_lower):
            direct_usage = True

    # BioProCorpus 代理分：产品名 vs 协议语料 的 token 重叠比（归一化 0-1）
    union = (corpus_tokens | product_tokens)
    biop = (len(corpus_tokens & product_tokens) / len(union)) if union else 0.0

    evlevel = evidence_level_score(product_method.evidence_level if product_method else "low")
    featured = bool(method_protocol.featured) if method_protocol else False

    score = (W_DIRECT * (1 if direct_usage else 0)
             + W_EVIDENCE * min(evidence_count, 10)
             + W_BIOPRO * biop
             + W_EVLEVEL * evlevel
             + W_FEATURED * (1 if featured else 0))

    if direct_usage:
        tier = "direct"
    elif evidence_count >= 1:
        tier = "literature"
    elif featured:
        tier = "featured"
    else:
        tier = "none"

    basis = []
    if direct_usage:
        basis.append("direct_usage")
    if evidence_count:
        basis.append(f"evidence×{evidence_count}")
    if biop > 0:
        basis.append(f"biopro={biop:.2f}")
    basis.append(f"ev={product_method.evidence_level if product_method else 'low'}")
    if featured:
        basis.append("featured")

    return {
        "score": round(score, 3),
        "evidence_count": evidence_count,
        "direct_usage": direct_usage,
        "tier": tier,
        "basis": ",".join(basis),
    }


class Command(BaseCommand):
    help = "只读探针：按设计稿算法对全部产品计算协议相关性，输出真实状态报告（不改库）。"

    def add_arguments(self, parser):
        parser.add_argument("--topn", type=int, default=TOPN)
        parser.add_argument("--min-overlap", type=int, default=MIN_OVERLAP)

    def handle(self, *args, **opts):
        global MIN_OVERLAP, TOPN
        MIN_OVERLAP = opts["min_overlap"]
        TOPN = opts["topn"]

        from apps.commerce.models import Product
        from apps.bridges.models import ProductMethod, MethodProtocol
        from apps.knowledge.models import Protocol

        # 用 .values() 只取必要字段，避免 SELECT 整行触发本地 DB 缺失的 archived 列
        products = list(Product.objects.values("id", "name", "cas", "catalog_no", "synonyms"))
        self.stdout.write(f"总产品数(values, 绕过 archived 列): {len(products)}")

        tier_counter = Counter()
        score_sum = 0.0
        score_min = None
        score_max = None
        pairs_total = 0
        products_with_protocols = 0
        products_with_jena = 0
        products_with_bioz = 0
        pairs_with_evidence = 0
        pairs_with_direct = 0
        pairs_hidden_beyond_topn = 0
        per_product_examples = []

        for product in products:
            product_id = product["id"]
            # 链路: Product -> ProductMethod -> Method -> MethodProtocol -> Protocol
            pms = list(ProductMethod.objects.filter(product_id=product_id).select_related("method"))
            if not pms:
                continue
            # 收集 (protocol, method_protocol, product_method) 去重
            seen = set()
            chain = []
            for pm in pms:
                method = pm.method
                if not method:
                    continue
                mps = list(MethodProtocol.objects.filter(method=method).select_related("protocol"))
                for mp in mps:
                    proto = mp.protocol
                    if not proto or proto.id in seen:
                        continue
                    seen.add(proto.id)
                    chain.append((proto, mp, pm))

            if not chain:
                continue
            products_with_protocols += 1

            bioz_refs, jena_matched, vendor, catalog_no = get_bioz_refs_for_product(product)
            if jena_matched:
                products_with_jena += 1
            if bioz_refs:
                products_with_bioz += 1

            scored = []
            for proto, mp, pm in chain:
                r = score_pair(product, proto, mp, pm, bioz_refs, catalog_no)
                scored.append((proto, r))
                pairs_total += 1
                tier_counter[r["tier"]] += 1
                if r["evidence_count"] > 0:
                    pairs_with_evidence += 1
                if r["direct_usage"]:
                    pairs_with_direct += 1
                score_sum += r["score"]
                score_min = r["score"] if score_min is None else min(score_min, r["score"])
                score_max = r["score"] if score_max is None else max(score_max, r["score"])

            scored.sort(key=lambda x: x[1]["score"], reverse=True)
            top = scored[:TOPN]
            hidden = len(scored) - len(top)
            pairs_hidden_beyond_topn += hidden
            if hidden > 0 or len(scored) >= 5 or bool(bioz_refs):
                per_product_examples.append((product, scored, hidden, vendor, catalog_no, bool(bioz_refs)))

        # ── 报告 ──
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("协议相关性探针报告（只读，不改库）")
        self.stdout.write("=" * 70)
        self.stdout.write(f"有协议关联的产品数: {products_with_protocols} / {len(products)}")
        self.stdout.write(f"  ├─ 其中 jena 命中（可查 Bioz）: {products_with_jena}")
        self.stdout.write(f"  └─ 其中 Bioz 文献可用（过期缓存快照）: {products_with_bioz}")
        self.stdout.write(f"参与评分的 (产品×协议) 桥接对: {pairs_total}")
        self.stdout.write(f"  ├─ 有文献证据(evidence>0): {pairs_with_evidence}")
        self.stdout.write(f"  └─ 判定直接用法(direct): {pairs_with_direct}")
        if pairs_total:
            mean = score_sum / pairs_total
            self.stdout.write(f"相关性分: min={score_min} max={score_max} mean={mean:.2f}")
        self.stdout.write("\n档位分布 (tier):")
        for t in ["direct", "literature", "featured", "none"]:
            c = tier_counter.get(t, 0)
            pct = (100.0 * c / pairs_total) if pairs_total else 0
            self.stdout.write(f"  {t:12s}: {c:4d}  ({pct:5.1f}%)")
        self.stdout.write(f"\n被 Top{TOPN} 折叠隐藏的桥接对: {pairs_hidden_beyond_topn}（即 UI 需折叠的数量）")

        self.stdout.write("\n" + "-" * 70)
        self.stdout.write(f"样例产品（前 12 个含折叠或 ≥5 协议）:")
        self.stdout.write("-" * 70)
        shown = 0
        per_product_examples.sort(key=lambda x: (x[5], len(x[1])), reverse=True)
        for product, scored, hidden, vendor, catalog_no, has_bioz in per_product_examples:
            if shown >= 20:
                break
            shown += 1
            bioz_tag = f"bioz={len([1])}?" if False else ("[BIOZ✓]" if has_bioz else "[BIOZ✗]")
            jtag = f"jena={catalog_no}" if catalog_no else "jena=—"
            self.stdout.write(f"\n■ {product.get('catalog_no')} {(product.get('name') or '')[:50]}  ({len(scored)} 协议, {jtag}, {bioz_tag})")
            for proto, r in scored[:TOPN]:
                self.stdout.write(f"   {r['score']:6.2f} [{r['tier']:9s}] {proto.name[:60]}  ({r['basis']})")
            if hidden:
                self.stdout.write(f"   … 折叠 {hidden} 条（Top{TOPN} 之外）")
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("注: 文献来自 Bioz 过期缓存快照(2026-07-30 左右)，离线可复现；")
        self.stdout.write("direct_usage 为正则启发式(best-effort)，非精确。")
        self.stdout.write("=" * 70)
