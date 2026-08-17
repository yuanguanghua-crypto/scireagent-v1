"""只读探针 v3：领域实体/方法匹配版。

问题背景：v2 用 docx 用途↔协议文本的 token 重叠打分，因"自然语言长句 vs 专有实验名"
用词空间不相交，2501 对分数全压在 0~0.1，无任何区分度。

v3 改用"领域词"匹配：
  - docx 用途 → 抽取领域词集合 P（transcription/labeling/click chemistry/sequencing/
    crispr/epigenetic/protein-rna/nucleotide/oligonucleotide/rna/dna/...）
  - 每个 Protocol → 用 method.name+method.objective+protocol.name+protocol.objective
    抽同一套领域词集合 Q
  - 相关性 = F-score(P,Q) = 0.5*coverage + 0.5*precision
      coverage  = |P∩Q| / max(1,|P|)     # 产品用途意图被协议覆盖多少
      precision = |P∩Q| / max(1,|Q|)     # 协议主题有多紧贴产品
  - 辅助：Bioz 缓存计数（best-effort，只读不抓）

输出：分数直方图 + 多组候选阈值(H,M)下的可见/折叠分布 + 高相关示例(含命中的领域词)。

用法（本地 sqlite，只读）：
  cd backend && DB_ENGINE=sqlite PYTHONDONTWRITEBYTECODE=1 \
      venv/Scripts/python.exe -B manage.py probe_protocol_relevance_v3 --cap 12 --min 5
"""
import os
import re
import json
import sys
from collections import Counter

from django.core.management.base import BaseCommand
from django.conf import settings

from apps.commerce.models import Product
from apps.bridges.models import ProductMethod, MethodProtocol
from apps.knowledge.models import Protocol
from apps.commerce.services.jena_matcher import match_jena, _looks_like_cas

# ───────── 领域词表（canonical -> 变体别名）─────────
# 集中在生物试剂/核酸技术域；v3 只是探针。
# D2（2026-08-04）：词表外部化为数据文件 apps/bridges/data/domain_vocab.json，
# 便于沉淀/扩充而不动探针逻辑；文件缺失/损坏时回退内联副本（行为不变）。
import functools


@functools.lru_cache(maxsize=1)
def _load_vocab():
    data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "..", "data", "domain_vocab.json")
    try:
        with open(data_path, encoding="utf-8") as fh:
            voc = json.load(fh)
        if isinstance(voc, dict) and voc:
            return voc
    except Exception:
        pass
    # 内联回退（须与 domain_vocab.json 保持一致）
    return {
        "transcription": ["transcription", "transcribe", "ivt", "in vitro transcription",
                           "rna synthesis", "synthesize rna", "run-off transcription"],
        "reverse transcription": ["reverse transcription", "reverse transcriptase", "rt-pcr", "cdna synthesis"],
        "pcr": ["pcr", "polymerase chain reaction", "amplification", "amplify"],
        "qpcr": ["qpcr", "q-pcr", "quantitative pcr", "real-time pcr", "rt-qpcr"],
        "rnaseq": ["rna-seq", "rnaseq", "rna sequencing", "transcriptome", "mrna seq", "bulk rna"],
        "sequencing": ["sequencing", "sequenced", "ngs", "nanopore", "pacbio", "illumina", "minion",
                       "oxford nanopore", "third-generation sequencing"],
        "labeling": ["labeling", "labelling", "label", "fluorescent labeling", "fluorophore",
                     "fluorescein", "biotin", "digoxigenin", "dig-", "alkaline phosphatase", "tagging"],
        "fluorescent": ["fluorescent", "fluorescence", "fam", "tamra", "cy3", "cy5", "texas red",
                        "alexa", "quencher", "dyes", "dye"],
        "click chemistry": ["click chemistry", "cuac", "azide", "alkyne", "cycloaddition",
                            "bioorthogonal", "strain-promoted"],
        "nucleotide": ["nucleotide", "nucleoside", "ntp", "utp", "atp", "gtp", "ctp", "ntps",
                       "modified nucleotide", "phosphorothioate", "ptp", "thio", "aminoallyl",
                       "biotinylated nucleotide", "ribonucleotide", "deoxynucleotide"],
        "oligonucleotide": ["oligonucleotide", "oligo", "primer", "probe", "aptamer", "pcr primer"],
        "rna": ["rna", "mrna", "rrna", "snrna", "mirna", "sirna", "shrna", "lncrna", "trna", "rnai"],
        "dna": ["dna", "cdna", "genomic dna", "plasmid", "dsdna", "ssdna", "genomic"],
        "crispr": ["crispr", "cas9", "cas12", "cas13", "sgrna", "gene editing", "knockout",
                   "knock-in", "knockin", "genome editing"],
        "epigenetic": ["epigenetic", "methylation", "methylated", "bisulfite", "5-mc", "5-hmc",
                       "chip", "cut&run", "cut run", "atac", "histone"],
        "protein-rna": ["rna binding", "rna-binding", "rbp", "protein-rna", "protein rna interaction",
                        "crosslink", "clip", "eclip", "iclip", "par-clip", "rip"],
        "purification": ["purification", "purify", "extraction", "isolation", "cleanup", "clean-up",
                         "enrichment"],
        "detection": ["detection", "detect", "imaging", "microscopy", "in situ", "western", "blot",
                      "fluorescence microscopy"],
        "modification": ["modification", "modified", "2-ome", "pseudouridine", "psi", "m5c", "m6a",
                         "base modification", "chemical modification", "ribose"],
        "in vitro": ["in vitro", "cell-free", "cell free"],
        "library prep": ["library prep", "library preparation", "library construction", "rna library",
                         "cdna library"],
        "splicing": ["splicing", "splice", "alternative splicing"],
        "translation": ["translation", "protein expression", "in vitro translation", "ivtt",
                        "protein synthesis"],
        "probe design": ["probe design", "probe synthesis", "hybridization", "hybridisation"],
        "fluorescent in situ": ["fish", "fluorescence in situ", "smfish", "rna fish", "rna-fish"],
    }


VOCAB = _load_vocab()

# 预编译：每个 canonical 一个 (?<![a-z0-9])(alt)(?![a-z0-9]) 正则
_COMPILED = {}
for _canon, _alts in VOCAB.items():
    _alt = "|".join(re.escape(a) for a in _alts)
    _COMPILED[_canon] = re.compile(r"(?<![a-z0-9])(" + _alt + r")(?![a-z0-9])")


def extract_domains(text):
    """返回文本命中的领域词 canonical 集合。"""
    if not text:
        return set()
    t = str(text).lower()
    out = set()
    for _canon, _rx in _COMPILED.items():
        if _rx.search(t):
            out.add(_canon)
    return out


def f_score(P, Q):
    """F-score on domain sets. 0 if no product domain."""
    if not P:
        return 0.0
    inter = P & Q
    if not inter:
        return 0.0
    coverage = len(inter) / len(P)
    precision = len(inter) / len(Q) if Q else 0.0
    return 0.5 * coverage + 0.5 * precision


def load_docx_usage():
    path = os.path.join(settings.BASE_DIR, "docx_products.json")
    if not os.path.exists(path):
        print(f"[warn] docx_products.json not found at {path}", file=sys.stderr)
        return {}, {}
    with open(path, encoding="utf-8") as f:
        recs = json.load(f)
    by_catalog, by_name = {}, {}
    for r in recs:
        if r.get("catalog"):
            by_catalog[r["catalog"].strip()] = r.get("usage", "")
        if r.get("name"):
            by_name[r["name"].strip().lower()] = r.get("usage", "")
    return by_catalog, by_name


def bioz_cached_count(vendor, catalog_no):
    """Bioz 缓存文献条数（只读）。key = f"{vendor}:{catalog_no}"，与 BiozClient 写入一致。
    注意：catalog_no 必须是 jena 解析出的厂商货号，不是产品内部 SC 编号，否则永远 miss。"""
    if not catalog_no:
        return 0
    try:
        from apps.documents.services.datasource_cache import get_cache
        entry = get_cache("bioz", f"{vendor}:{catalog_no}", "sku")
        if entry is not None and not entry.is_stale:
            data = entry.get_data()
            return len(data) if isinstance(data, list) else 0
    except Exception:
        pass
    return 0


def resolve_jena_cat(prod):
    """返回 (bioz_vendor, jena_catalog_no)，与生产 match_jena 级联同源；无则 (None,None)。"""
    VENDOR_MAP = {"jena": "Jena Bioscience", "cayman": "Cayman Chemical",
                  "trilink": "TriLink BioTechnologies", "biotium": "Biotium"}
    user_cas = (prod.get("cas") or "").strip()
    search_name = prod.get("name") or ""
    synonyms = prod.get("synonyms") or []
    if isinstance(synonyms, str):
        synonyms = [synonyms]
    identifier = user_cas or search_name
    if not identifier and not synonyms:
        return None, None
    namespace = "cas" if (user_cas and _looks_like_cas(user_cas)) else "name"
    try:
        jena = match_jena(identifier=identifier, namespace=namespace,
                          synonyms=synonyms, request_name=search_name)
    except Exception:
        return None, None
    if not jena.get("matched"):
        return None, None
    catalog_no = jena.get("catalog_no", "")
    if "sources" in jena and not catalog_no:
        ms = [s for s in jena.get("sources", []) if s.get("matched")]
        s = next((x for x in ms if x.get("vendor") == "jena"), None) or (ms[0] if ms else None)
        if s:
            catalog_no = s.get("catalog_no", "")
    if not catalog_no:
        return None, None
    vendor = (jena.get("vendor") or "jena").lower()
    return VENDOR_MAP.get(vendor, "Jena Bioscience"), catalog_no


class Command(BaseCommand):
    help = "ReadOnly v3: domain-entity relevance preview for existing products."

    def add_arguments(self, parser):
        parser.add_argument("--cap", type=int, default=12, help="HARD_CAP (UI guard)")
        parser.add_argument("--min", type=int, default=5, help="MIN_VISIBLE fallback")
        parser.add_argument("--w-dom", type=float, default=0.85, help="domain F-score weight")
        parser.add_argument("--w-bioz", type=float, default=0.15, help="bioz cache weight")
        parser.add_argument("--examples", type=int, default=12)

    def handle(self, *args, **opt):
        CAP = opt["cap"]; MINV = opt["min"]; WD = opt["w_dom"]; WB = opt["w_bioz"]

        by_catalog, by_name = load_docx_usage()

        # 方法词典（用于丰富 protocol 的领域抽取）
        methods = {}
        try:
            for m in __import__("apps.knowledge.models", fromlist=["Method"]).Method.objects.values(
                    "id", "name", "summary", "purpose"):
                methods[m["id"]] = m
        except Exception as e:
            print(f"[warn] method load failed: {e}", file=sys.stderr)

        # 协议预载：标题+objective+method.name+method.summary+method.purpose
        # （Method 无 objective 字段，真实可用字段为 summary/purpose）
        protos = {}
        for p in Protocol.objects.values("id", "name", "objective", "method_id"):
            m = methods.get(p.get("method_id")) or {}
            text = " ".join([p.get("name") or "", p.get("objective") or "",
                             m.get("name") or "", m.get("summary") or "", m.get("purpose") or ""])
            protos[p["id"]] = {"title": p.get("name") or "", "dom": extract_domains(text)}

        products = list(Product.objects.values("id", "catalog_no", "name", "cas", "synonyms"))
        print(f"Products in DB: {len(products)}")

        all_scores = []
        per_product = []
        no_usage = 0

        for prod in products:
            pid = prod["id"]
            method_ids = list(ProductMethod.objects.filter(product_id=pid).values_list("method_id", flat=True))
            if not method_ids:
                continue
            mp_rows = MethodProtocol.objects.filter(method_id__in=method_ids).values_list("protocol_id", "featured")
            proto_ids = []
            feat = {}
            for prid, f in mp_rows:
                if prid not in feat:
                    proto_ids.append(prid)
                if f:
                    feat[prid] = True
            if not proto_ids:
                continue

            usage = ""
            cat = (prod.get("catalog_no") or "").strip()
            if cat and cat in by_catalog:
                usage = by_catalog[cat]
            elif prod.get("name") and prod["name"].strip().lower() in by_name:
                usage = by_name[prod["name"].strip().lower()]
            if not usage:
                no_usage += 1
            P = extract_domains(usage)
            bioz_vendor, jcat = resolve_jena_cat(prod)
            bioz = bioz_cached_count(bioz_vendor, jcat) if jcat else 0
            bioz_boost = min(1.0, bioz / 5.0)  # 5+ 条封顶

            scored = []
            for prid in proto_ids:
                pr = protos.get(prid)
                if not pr:
                    continue
                dom = f_score(P, pr["dom"])
                edit = 1.0 if feat.get(prid) else 0.0
                # 编辑 featured 作兜底：domain=0 但被编辑精选时给一个基础分
                if dom == 0.0 and edit:
                    dom = 0.25
                score = WD * dom + WB * bioz_boost
                score = max(0.0, min(1.0, score))
                all_scores.append(score)
                scored.append((prid, pr["title"], round(score, 3),
                               sorted(P & pr["dom"]), dom, len(P)))

            scored.sort(key=lambda x: x[2], reverse=True)
            per_product.append({
                "pid": pid, "name": prod.get("name"), "catalog": cat,
                "total": len(scored), "has_usage": bool(usage), "bioz": bioz,
                "np_dom": len(P), "top": scored[:8],
            })

        print(f"\n=== INPUT ===  products-with-bridges={len(per_product)}  no_docx_usage={no_usage}")
        print(f"Total (product,protocol) pairs scored: {len(all_scores)}")
        print(f"Weights: domain={WD} bioz={WB} (bioz_boost=min(1,bioz/5))")

        # ── 直方图 ──
        bins = [(0.0, 0.1), (0.1, 0.2), (0.2, 0.3), (0.3, 0.4), (0.4, 0.6),
                (0.6, 0.8), (0.8, 1.01)]
        hist = Counter()
        for s in all_scores:
            for lo, hi in bins:
                if lo <= s < hi:
                    hist[(lo, hi)] += 1
                    break
        print("\n=== SCORE HISTOGRAM (all pairs, domain F-score) ===")
        maxc = max((hist[b] for b in bins), default=1)
        for lo, hi in bins:
            c = hist[(lo, hi)]
            bar = "#" * int(c / max(1, maxc) * 50)
            print(f"  [{lo:.1f},{hi:.1f}) {c:5d} {bar}")

        # ── 多组候选阈值的可见分布 ──
        print("\n=== ADAPTIVE VISIBLE DISTRIBUTION (grid of H/M) ===")
        for H, M in [(0.6, 0.3), (0.5, 0.25), (0.4, 0.2), (0.3, 0.15)]:
            vis_bins = Counter()
            n_fb = n_cap = 0
            for r in per_product:
                high = [s for s in r["top"] if s[2] >= H]
                if len(high) > CAP:
                    v = CAP; n_cap += 1
                elif len(high) == 0:
                    v = min(MINV, r["total"]); n_fb += 1
                else:
                    v = len(high)
                if v == 0: vis_bins["0"] += 1
                elif v <= 3: vis_bins["1-3"] += 1
                elif v <= 6: vis_bins["4-6"] += 1
                elif v <= 9: vis_bins["7-9"] += 1
                elif v <= 12: vis_bins["10-12"] += 1
                else: vis_bins["13+"] += 1
            line = "  ".join(f"{k}:{vis_bins[k]:3d}" for k in ["0", "1-3", "4-6", "7-9", "10-12", "13+"])
            print(f"  H={H:.2f} M={M:.2f}  show[ {line} ]  fb={n_fb} cap={n_cap}")

        # ── 高相关示例（展示命中领域词，便于人工判断算法对错）──
        print(f"\n=== HIGH-RELEVANCE EXAMPLES (top {opt['examples']} by best score) ===")
        ranked = sorted(per_product, key=lambda r: (r["top"][0][2] if r["top"] else 0), reverse=True)
        for r in ranked[:opt["examples"]]:
            best = r["top"][0] if r["top"] else None
            print(f"\n  {r['catalog'] or r['name']}  total={r['total']} np_dom={r['np_dom']} bioz={r['bioz']} usage={r['has_usage']}")
            for prid, title, sc, doms, domraw, nP in r["top"][:5]:
                dstr = ",".join(doms) if doms else "-"
                print(f"     score={sc:.3f} (dom={domraw:.2f} P={nP}) [{dstr}]  {title[:58]}")
