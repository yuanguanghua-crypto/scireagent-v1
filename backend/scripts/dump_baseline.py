"""
S0 基线快照生成器（只读，可复现）。

产出：baselines/baseline_<YYYYMMDD>.json
作用：
  1. 固化当前 dev SQLite 的全部关键指标，作为 S3–S6 的可比基线。
  2. 显式对齐 ABC 方案 C0 的「22 条」数量口径与现状：
       - C0 的「22」= 顶层 __e2e_* / __curl_* 脏夹具 = 9 RG + 6 AP + 7 ME（全部零跨链接）。
       - C5 验收表的「15」是笔误（应为 22）。
       - 真实脏数据全量口径 = 22 顶层夹具 + 131 Product e2e 残骸 + 5 伪方法(已隔离到 catch-all)。
  3. 不含任何写操作，守铁律①零删除。

运行：DB_ENGINE=sqlite PYTHONDONTWRITEBYTECODE=1 venv/Scripts/python.exe -B scripts/dump_baseline.py
"""
import os
import sys
import json
import statistics
import django
from datetime import date

# 把 backend 根加入 sys.path（manage.py 会自动加，独立运行需手动加）
BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

from django.db.models import Count, Q
from apps.knowledge.models import ResearchGoal, Application, Method, Protocol
from apps.bridges.models import ProductMethod, MethodProtocol, ProductProtocol
from apps.commerce.models import Product

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "baselines")
os.makedirs(OUT_DIR, exist_ok=True)
OUT_PATH = os.path.join(OUT_DIR, f"baseline_{date.today():%Y%m%d}.json")


def q_count(qs):
    return qs.count()


# ─────────────────────────────────────────────────────────────
# 1. 脏数据口径对齐（核心：C0「22 条」与现状）
# ─────────────────────────────────────────────────────────────
rg_total = ResearchGoal.objects.count()
rg_fixture = ResearchGoal.objects.filter(is_test_fixture=True).count()
ap_total = Application.objects.count()
ap_fixture = Application.objects.filter(is_test_fixture=True).count()
me_total = Method.objects.count()
me_fixture = Method.objects.filter(is_test_fixture=True).count()

# Product e2e 残骸：name 前缀 "E2E " 或 catalog_no 前缀 "E2E-"
prod_e2e = Product.objects.filter(Q(name__startswith="E2E ") | Q(catalog_no__startswith="E2E-"))
prod_e2e_total = prod_e2e.count()
prod_e2e_archived = prod_e2e.filter(archived=True).count()
prod_e2e_draft = prod_e2e.filter(status="draft").count()
prod_e2e_with_bridges = (
    prod_e2e.filter(Q(product_methods__isnull=False) | Q(protocol_links__isnull=False)).distinct().count()
)

# 伪方法（整句实验描述）已隔离到 catch-all Application
catch_all = Application.objects.filter(name="Other / Experimental Descriptions").first()
pseudo_total = Method.objects.filter(application=catch_all).count() if catch_all else 0

dirty_caliber = {
    "c0_claim": "ABC 方案 C0 正文（line 135）：18 RG 中 9、14 AP 中 6、22 ME 中 7 个 __e2e_* / __curl_* 残留 = 9+6+7 = 22 顶层脏夹具",
    "c5_claim": "ABC 方案 C5 验收表（line 249）误写「15」，v2 已注明为笔误，正确应为 22",
    "caliber_definition": "「脏实体」严格 = 顶层 __ 前缀 e2e 夹具（零跨链接）。Product e2e 残骸与伪方法属另一口径，单列如下。",
    "top_layer_fixtures": {
        "total": rg_fixture + ap_fixture + me_fixture,
        "research_goal": {"fixture": rg_fixture, "total": rg_total},
        "application": {"fixture": ap_fixture, "total": ap_total},
        "method": {"fixture": me_fixture, "total": me_total},
        "note": "全部 is_test_fixture=True（S1 标记），公开读取面已过滤；零删除。",
    },
    "product_e2e_residue": {
        "total": prod_e2e_total,
        "archived": prod_e2e_archived,
        "draft": prod_e2e_draft,
        "with_bridges": prod_e2e_with_bridges,
        "identification": "按前缀 E2E / E2E- 识别；archived 是 dev 库的广泛状态(255/256 商品均 archived，含 108 active + 16 published + 131 e2e)，故 e2e 不能靠 archived 区分，必须靠前缀。",
        "note": "全部 archived=True、draft、0 桥接行；公开 list 已隐藏，search 已在 S1-A 用 .exclude(archived=True) 对齐。",
    },
    "pseudo_methods": {
        "total": pseudo_total,
        "note": "整句实验描述冒充 Method，F3-A 已整体重挂到 catch-all(Other / Experimental Descriptions, research_goal=None)，零删除，MethodProtocol/ProductMethod 桥保留。",
    },
    "full_dirty_footprint": {
        "top_layer_fixtures": rg_fixture + ap_fixture + me_fixture,
        "product_e2e": prod_e2e_total,
        "pseudo_methods": pseudo_total,
        "note": "C0『22』只覆盖 top_layer_fixtures 一项；完整脏数据足迹远大于 22。",
    },
}

# ─────────────────────────────────────────────────────────────
# 2. 顶部链（路径二：Product→Protocol→Method→Application→RG）
# ─────────────────────────────────────────────────────────────
# 非零 RG（去重，含夹具 / 仅真实）
nonzero_rg_all = (
    ResearchGoal.objects.filter(applications__methods__product_methods__isnull=False).distinct().count()
)
nonzero_rg_real = (
    ResearchGoal.objects.filter(
        is_test_fixture=False, applications__methods__product_methods__isnull=False
    )
    .distinct()
    .count()
)
rg_real_total = ResearchGoal.objects.filter(is_test_fixture=False).count()

# 真实 RG 之下各 Application / Method 分布
real_apps = Application.objects.filter(is_test_fixture=False).count()
real_methods = Method.objects.filter(is_test_fixture=False).count()
# 挂在真实 RG 树下的 Method 数（排除 catch-all 等 research_goal=None）
methods_under_rg_tree = Method.objects.filter(
    application__research_goal__isnull=False, is_test_fixture=False
).count()

# 商品 RG 多重性（经路径二：一个商品归属几个不同 RG）
multi = (
    Product.objects.annotate(
        rg_count=Count("product_methods__method__application__research_goal", distinct=True)
    )
    .filter(rg_count__gt=0)
)
multi_dist = {}
for p in multi.values_list("rg_count"):
    multi_dist[p[0]] = multi_dist.get(p[0], 0) + 1
multi_dist = dict(sorted(multi_dist.items()))

top_chain = {
    "research_goal": {"total": rg_total, "fixture": rg_fixture, "real": rg_real_total},
    "application": {"total": ap_total, "fixture": ap_fixture, "real": real_apps},
    "method": {"total": me_total, "fixture": me_fixture, "real": real_methods},
    "nonzero_rg": {
        "path_two_all": nonzero_rg_all,
        "path_two_real_only": nonzero_rg_real,
        "real_rg_total": rg_real_total,
        "ratio": f"{nonzero_rg_real} / {rg_real_total}",
        "note": "S2 后非零 RG 由 1/9 提升到 6/9（v2 核心指标达成）。",
    },
    "methods_under_rg_tree": methods_under_rg_tree,
    "product_rg_multiplicity": multi_dist,
}

# ─────────────────────────────────────────────────────────────
# 3. Knowledge Links（ProductProtocol 桥）指标
# ─────────────────────────────────────────────────────────────
pp_total = ProductProtocol.objects.count()
tier_dist = {
    row["tier"]: row["c"]
    for row in ProductProtocol.objects.values("tier").annotate(c=Count("id"))
}
link_source_dist = {
    row["link_source"]: row["c"]
    for row in ProductProtocol.objects.values("link_source").annotate(c=Count("id"))
}
scores = list(ProductProtocol.objects.values_list("relevance_score", flat=True))
score_stats = {
    "count": len(scores),
    "median": round(statistics.median(scores), 4) if scores else None,
    "mean": round(statistics.mean(scores), 4) if scores else None,
    "min": round(min(scores), 4) if scores else None,
    "max": round(max(scores), 4) if scores else None,
    "zero_count": sum(1 for s in scores if s == 0),
}
# 单协议最大被链次数
from django.db.models import Max
max_linked = (
    ProductProtocol.objects.values("protocol")
    .annotate(c=Count("id"))
    .aggregate(m=Max("c"))["m"]
)
# 每商品链接数范围 / median
per_prod = list(
    ProductProtocol.objects.values("product").annotate(c=Count("id")).values_list("c", flat=True)
)
per_prod_stats = {
    "count": len(per_prod),
    "min": min(per_prod) if per_prod else None,
    "max": max(per_prod) if per_prod else None,
    "median": round(statistics.median(per_prod), 2) if per_prod else None,
}

knowledge_links = {
    "productprotocol_total": pp_total,
    "tier_distribution": tier_dist,
    "link_source_distribution": link_source_dist,
    "relevance_score": score_stats,
    "single_protocol_max_linked": max_linked,
    "per_product_link_count": per_prod_stats,
    "methodprotocol_total": MethodProtocol.objects.count(),
    "productmethod_total": ProductMethod.objects.count(),
}

# ─────────────────────────────────────────────────────────────
# 4. 其他规模指标
# ─────────────────────────────────────────────────────────────
other = {
    "protocol_total": Protocol.objects.count(),
    "product_total": Product.objects.count(),
    "product_archived": Product.objects.filter(archived=True).count(),
    "product_archived_breakdown": {
        "active_archived": Product.objects.filter(status="active", archived=True).count(),
        "published_archived": Product.objects.filter(status="published", archived=True).count(),
        "draft_archived": Product.objects.filter(status="draft", archived=True).count(),
        "not_archived": Product.objects.filter(archived=False).count(),
        "note": "dev 库几乎全 archived；e2e(131) 是 draft+archived 子集，靠前缀识别。",
    },
}

baseline = {
    "generated_at": date.today().isoformat(),
    "source_db": "db.sqlite3 (dev, post-S1/S1-A / S2 / F3-A)",
    "note": "本 JSON 为 S0 权威基线。v2 方案 S0 表(非零RG=1/9 等)是 S1/S2 之前快照，现已过时，以本文件为准。",
    "dirty_data_caliber": dirty_caliber,
    "top_chain_path_two": top_chain,
    "knowledge_links": knowledge_links,
    "other_scale": other,
}

with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(baseline, f, ensure_ascii=False, indent=2)

print(f"基线已写入: {OUT_PATH}")
print(f"  顶层夹具脏实体(=C0『22』): {dirty_caliber['top_layer_fixtures']['total']}")
print(f"  Product e2e 残骸: {prod_e2e_total}")
print(f"  伪方法(隔离): {pseudo_total}")
print(f"  非零 RG(真实口径): {nonzero_rg_real} / {rg_real_total}")
print(f"  ProductProtocol 总行: {pp_total}")
