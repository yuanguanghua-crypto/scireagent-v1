# step8_apply.py —— L2 人工回填入库（修 3 条错误 + 应用 8369 条修正）
# 处理：INV-REVIEW→删桥+facet 综述；SUP-BIOINFO→删桥；其余→method 更新 evidence_source=manual_curated
import os, json, csv
from collections import Counter
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.apps import apps
from django.db import transaction
Method = apps.get_model("knowledge", "Method")
MethodProtocol = apps.get_model("bridges", "MethodProtocol")
FacetValue = apps.get_model("knowledge", "FacetValue")
ProtocolFacet = apps.get_model("knowledge", "ProtocolFacet")

OUT = r"C:\Users\yuankaifeng\WorkBuddy\2026-07-08-11-22-32\_audit_tmp"
SRC = r"C:\Users\yuankaifeng\Downloads\L2_curation_workfile_corrected.csv"
entities = json.load(open(os.path.join(OUT, "step6_method_entities.json"), encoding="utf-8"))
slug_of = {e["id_code"]: e["slug"] for e in entities}

# 3 条明确错误修正（验收结论）
FIX = {"5405": "M15", "10407": "M11b", "11110": "M49"}
REVIEW_IDS = {"13034", "1636", "1166", "11161", "5711", "7854", "2877", "7180", "7255", "1936"}

rows = list(csv.DictReader(open(SRC, encoding="utf-8-sig")))
assert len(rows) == 8369, "回填行数异常: %d" % len(rows)
plan = {r["protocol_id"]: (FIX.get(r["protocol_id"]) or (r["corrected_method"] or "").strip()) for r in rows}

n_inv = sum(1 for v in plan.values() if v == "INV-REVIEW")
n_sup = sum(1 for v in plan.values() if v == "SUP-BIOINFO")
n_method = sum(1 for v in plan.values() if v not in ("INV-REVIEW", "SUP-BIOINFO", ""))
n_empty = sum(1 for v in plan.values() if not v)
print("计划：method=%d, INV=%d, SUP=%d, 空=%d" % (n_method, n_inv, n_sup, n_empty))

# 修正后校验合法性
bad = [pid for pid, v in plan.items() if v and v not in slug_of and v not in ("INV-REVIEW", "SUP-BIOINFO")]
print("非法 corrected（修正后）:", len(bad), bad[:10])
assert not bad, "存在非法 id_code，中止"

with transaction.atomic():
    n_del = 0; n_upd = 0; n_new = 0; n_facet = 0; n_review = 0
    for pid, corr in plan.items():
        # 删除该协议现有 lexicon_auto 桥（若有）
        mp_qs = MethodProtocol.objects.filter(protocol_id=int(pid), evidence_source="lexicon_auto")
        n_del += mp_qs.count()
        mp_qs.delete()
        if corr == "INV-REVIEW":
            fv, _ = FacetValue.objects.get_or_create(
                facet_type="study_type", kind="", value="Systematic Review",
                defaults={"slug": "study_type-systematic-review", "description": "系统综述/元分析研究类型"})
            pf, created = ProtocolFacet.objects.get_or_create(protocol_id=int(pid), facet=fv, defaults={"source": "cluster_main"})
            if created:
                n_facet += 1
            continue
        if corr == "SUP-BIOINFO":
            continue  # 生信：不关联 Method（桥已删）
        if not corr:
            continue
        m = Method.objects.filter(slug=slug_of[corr]).first()
        if not m:
            print("!! Method 缺失:", corr, pid)
            continue
        mp, created = MethodProtocol.objects.get_or_create(
            method=m, protocol_id=int(pid),
            defaults={"evidence_source": "manual_curated", "display_order": 0,
                      "status": "review" if pid in REVIEW_IDS else "active"},
        )
        if created:
            n_new += 1
        else:
            mp.evidence_source = "manual_curated"
            mp.display_order = 0
            mp.status = "review" if pid in REVIEW_IDS else mp.status
            mp.save(update_fields=["evidence_source", "display_order", "status"])
            n_upd += 1
        if pid in REVIEW_IDS:
            n_review += 1
    print("执行：删 lexicon_auto 桥=%d，新建=%d，更新=%d，综述 facet=%d，存疑标 review=%d"
          % (n_del, n_new, n_upd, n_facet, n_review))

# 验证
mp_auto = MethodProtocol.objects.filter(evidence_source="lexicon_auto").count()
mp_manual = MethodProtocol.objects.filter(evidence_source="manual_curated").count()
mp_legacy = MethodProtocol.objects.filter(evidence_source="legacy").count()
mp_review = MethodProtocol.objects.filter(status="review").count()
orphan = MethodProtocol.objects.filter(method__isnull=True).count() + MethodProtocol.objects.filter(protocol__isnull=True).count()
print("== 验证 ==")
print("lexicon_auto（应=0，L2 已全部转人工）:", mp_auto)
print("manual_curated:", mp_manual)
print("legacy:", mp_legacy)
print("status=review（存疑 10）:", mp_review)
print("孤儿:", orphan)
print("桥总数:", MethodProtocol.objects.count())
