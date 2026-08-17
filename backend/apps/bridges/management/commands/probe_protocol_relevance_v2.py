"""只读探针：模拟"ProductProtocol 相关性 + 自适应 TopN"在现有产品上的显示结果。

不改任何库、不建表、不写桥。仅读取：
  - Product / ProductMethod / MethodProtocol / Protocol（DB，窄字段避免陈旧列）
  - docx_products.json（用途，主信号）
  - Bioz 缓存（best-effort，只读不抓）
按 docx 用途↔协议文本重叠(主) + 产品名↔协议标题(辅) + 编辑 featured(兜底) 算分，
再按自适应规则（档位 H/M + HARD_CAP + MIN_VISIBLE）给出每产品"可见/折叠"预览。

用法（本地 sqlite）：
  cd backend && DB_ENGINE=sqlite PYTHONDONTWRITEBYTECODE=1 \
      venv/Scripts/python.exe -B manage.py probe_protocol_relevance_v2 \
      --h 0.6 --m 0.3 --cap 12 --min 5

目的：在敲定阈值前，先看 125+ 产品的真实分布，再决定 H/M/HARD_CAP。
"""
import os
import json
import re
import sys
from collections import Counter

from django.core.management.base import BaseCommand
from django.conf import settings

from apps.commerce.models import Product
from apps.bridges.models import ProductMethod, MethodProtocol
from apps.knowledge.models import Protocol

STOP = set("""the a an and or of for in to with by via using from into on at is are be
used use using application applications method methods protocol protocols this that these those
can may also as its their our we it they he she which what when where who how will would should
sample samples cell cells reaction reactions assay assays acid acids base bases rna dna protein
""".split())


def tokenize(text):
    if not text:
        return set()
    toks = re.findall(r"[A-Za-z][A-Za-z0-9\-]*", str(text).lower())
    return {t for t in toks if len(t) >= 3 and t not in STOP}


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


def bioz_cached_count(catalog_no):
    """best-effort 只读 Bioz 缓存，不触发网络抓取。"""
    try:
        from apps.documents.services.datasource_cache import get_cache
        entry = get_cache("bioz", f"Jena Bioscience:{catalog_no}", "sku")
        if entry is not None and not entry.is_stale:
            data = entry.get_data()
            return len(data) if isinstance(data, list) else 0
    except Exception:
        pass
    return 0


class Command(BaseCommand):
    help = "ReadOnly preview of adaptive TopN relevance for existing products."

    def add_arguments(self, parser):
        parser.add_argument("--h", type=float, default=0.6, help="high tier threshold")
        parser.add_argument("--m", type=float, default=0.3, help="medium tier threshold")
        parser.add_argument("--cap", type=int, default=12, help="HARD_CAP (UI guard)")
        parser.add_argument("--min", type=int, default=5, help="MIN_VISIBLE fallback")
        parser.add_argument("--w-docx", type=float, default=0.6)
        parser.add_argument("--w-name", type=float, default=0.25)
        parser.add_argument("--w-edit", type=float, default=0.15)
        parser.add_argument("--examples", type=int, default=10)

    def handle(self, *args, **opt):
        H = opt["h"]; M = opt["m"]; CAP = opt["cap"]; MINV = opt["min"]
        WD, WN, WE = opt["w_docx"], opt["w_name"], opt["w_edit"]

        by_catalog, by_name = load_docx_usage()

        # 预载所有 protocol 文本 + token 集（一次）
        protos = {}
        for p in Protocol.objects.values("id", "name", "objective", "materials", "reagents"):
            text = " ".join([p.get("name") or "", p.get("objective") or "",
                             p.get("materials") or "", p.get("reagents") or ""])
            protos[p["id"]] = {"title": p.get("name") or "", "tokens": tokenize(text)}

        # 读产品（窄字段，避免陈旧 archived 列）
        products = list(Product.objects.values("id", "catalog_no", "name", "cas"))
        print(f"Products in DB: {len(products)}")

        all_pairs = []          # (score,) 收集做直方图
        per_product = []        # 每产品结果
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

            # 用途
            usage = ""
            cat = (prod.get("catalog_no") or "").strip()
            if cat and cat in by_catalog:
                usage = by_catalog[cat]
            elif prod.get("name") and prod["name"].strip().lower() in by_name:
                usage = by_name[prod["name"].strip().lower()]
            if not usage:
                no_usage += 1
            utoks = tokenize(usage)
            ntoks = tokenize(prod.get("name") or "")

            scored = []
            for prid in proto_ids:
                pr = protos.get(prid)
                if not pr:
                    continue
                docx_overlap = (len(utoks & pr["tokens"]) / len(utoks)) if utoks else 0.0
                name_match = (len(ntoks & pr["tokens"]) / len(ntoks)) if ntoks else 0.0
                edit = 1.0 if feat.get(prid) else 0.0
                score = WD * docx_overlap + WN * name_match + WE * edit
                score = max(0.0, min(1.0, score))
                all_pairs.append(score)
                scored.append((prid, pr["title"], round(score, 3), round(docx_overlap, 3)))

            scored.sort(key=lambda x: x[2], reverse=True)
            high = [s for s in scored if s[2] >= H]
            if len(high) > CAP:
                visible = high[:CAP]
            elif len(high) == 0:
                visible = scored[:MINV]
            else:
                visible = high
            folded = len(scored) - len(visible)
            per_product.append({
                "pid": pid, "name": prod.get("name"), "catalog": cat,
                "total": len(scored), "visible": len(visible), "folded": folded,
                "has_usage": bool(usage), "bioz": bioz_cached_count(cat) if cat else 0,
                "top": scored[:8], "visible_n": len(high),
            })

        # ── 输出 ──
        print(f"\n=== CONFIG ===  H={H} M={M} CAP={CAP} MINV={MINV}  weights docx={WD} name={WN} edit={WE}")
        print(f"Products with protocol bridges: {len(per_product)}  (no docx usage: {no_usage})")
        print(f"Total (product,protocol) pairs scored: {len(all_pairs)}")

        # 直方图
        bins = [(0.0, 0.1), (0.1, 0.2), (0.2, 0.3), (0.3, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)]
        hist = Counter()
        for s in all_pairs:
            for lo, hi in bins:
                if lo <= s < hi:
                    hist[(lo, hi)] += 1
                    break
        print("\n=== SCORE HISTOGRAM (all pairs) ===")
        for lo, hi in bins:
            c = hist[(lo, hi)]
            bar = "#" * int(c / max(1, len(all_pairs)) * 50)
            print(f"  [{lo:.1f},{hi:.1f}) {c:5d} {bar}")

        # 可见数分布
        vis_bins = Counter()
        for r in per_product:
            v = r["visible"]
            if v == 0: vis_bins["0"] += 1
            elif v <= 3: vis_bins["1-3"] += 1
            elif v <= 6: vis_bins["4-6"] += 1
            elif v <= 9: vis_bins["7-9"] += 1
            elif v <= 12: vis_bins["10-12"] += 1
            else: vis_bins["13+"] += 1
        print("\n=== VISIBLE-COUNT DISTRIBUTION (per product, adaptive) ===")
        for k in ["0", "1-3", "4-6", "7-9", "10-12", "13+"]:
            c = vis_bins[k]
            bar = "#" * int(c / max(1, len(per_product)) * 50)
            print(f"  show {k:5s} : {c:4d} products  {bar}")
        n_fallback = sum(1 for r in per_product if r["visible_n"] == 0)
        print(f"  products hitting MIN_VISIBLE fallback (0 high): {n_fallback}")
        n_cap = sum(1 for r in per_product if r["visible_n"] > CAP)
        print(f"  products hitting HARD_CAP (high>{CAP}): {n_cap}")

        # 当前平铺 vs 自适应：折叠量最大的案例（即"太多"被修掉的）
        print("\n=== TOP 'TOO MANY FIXED' (largest fold reduction) ===")
        fixed = sorted(per_product, key=lambda r: r["folded"], reverse=True)[:8]
        for r in fixed:
            print(f"  [{r['catalog'] or r['name']}] total={r['total']} -> visible={r['visible']} (fold {r['folded']}) bioz={r['bioz']} usage={r['has_usage']}")

        # 示例：带 docx 用途、且有高相关的产品
        print(f"\n=== EXAMPLES (with docx usage, top {opt['examples']}) ===")
        ex = [r for r in per_product if r["has_usage"]]
        ex.sort(key=lambda r: (r["visible_n"] > 0, r["total"]), reverse=True)
        for r in ex[:opt["examples"]]:
            print(f"\n  {r['catalog'] or r['name']}  total={r['total']} visible={r['visible']} bioz={r['bioz']}")
            for prid, title, sc, dov in r["top"][:6]:
                print(f"     {sc:.3f} (docx {dov:.2f})  {title[:60]}")
