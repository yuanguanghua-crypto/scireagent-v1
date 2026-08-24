# L3 v4 收口落地：Method 桥写入 + INV 综述 facet（dry-run/--apply）
# 用户认可：evidence_source=lexicon_auto、新增桥 status=review、sup/blank 账外不写桥
import os, sys, csv, json
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.apps import apps
from django.db import transaction
Protocol = apps.get_model("knowledge", "Protocol")
Method = apps.get_model("knowledge", "Method")
mp = apps.get_model("bridges", "MethodProtocol")
FacetValue = apps.get_model("knowledge", "FacetValue")
ProtocolFacet = apps.get_model("knowledge", "ProtocolFacet")

DRY = "--apply" not in sys.argv
OUT = r"C:\Users\yuankaifeng\WorkBuddy\2026-07-08-11-22-32\_audit_tmp"
V4 = r"C:\Users\yuankaifeng\Downloads\L3_curation_workfile_v4.csv"
M51 = r"C:\Users\yuankaifeng\Downloads\M51_rectified_v5.csv"

# 1. 合并 v4 + M51 修正
rows = list(csv.DictReader(open(V4, encoding="utf-8-sig")))
m51 = list(csv.DictReader(open(M51, encoding="utf-8-sig")))
merged = {r["protocol_id"]: r for r in rows}
for r in m51:
    if r["protocol_id"] in merged:
        merged[r["protocol_id"]]["corrected_method"] = r["corrected_method"]
        merged[r["protocol_id"]]["confidence"] = r["confidence"]
print("合并协议数:", len(merged), "| DRY:", DRY)

# 2. Method id_code -> Method 对象
ents = json.load(open(os.path.join(OUT, "step6_method_entities.json"), encoding="utf-8"))
code2slug = {e["id_code"]: e["slug"] for e in ents}
slug2m = {m.slug: m for m in Method.objects.all()}

# 3. 分类
method_rows, inv_rows, sup_rows, blank_rows = [], [], [], []
for pid, r in merged.items():
    cm = (r.get("corrected_method") or "").strip()
    if not cm:
        blank_rows.append(pid)
    elif cm == "SUP-BIOINFO":
        sup_rows.append(pid)
    elif cm == "INV-REVIEW":
        inv_rows.append(pid)
    else:
        method_rows.append((pid, cm, (r.get("confidence") or "").strip()))
print("method: %d | inv: %d | sup: %d | blank: %d" %
      (len(method_rows), len(inv_rows), len(sup_rows), len(blank_rows)))

# 4. 写桥（幂等）
existing = set(mp.objects.values_list("protocol_id", "method_id"))
new_bridge = 0
skipped_dup = 0
missing_method = 0
missing_protocol = 0
to_create = []
for pid, code, conf in method_rows:
    slug = code2slug.get(code)
    m = slug2m.get(slug) if slug else None
    if not m:
        missing_method += 1
        continue
    p = Protocol.objects.filter(id=int(pid)).first()
    if not p:
        missing_protocol += 1
        continue
    if (p.id, m.id) in existing:
        skipped_dup += 1
        continue
    to_create.append((p, m, conf))

if not DRY:
    with transaction.atomic():
        for p, m, conf in to_create:
            mp.objects.create(protocol=p, method=m, evidence_source="lexicon_auto",
                              status="review", display_order=0)
    new_bridge = len(to_create)
else:
    new_bridge = len(to_create)
print("新桥将写入: %d | 跳过重复: %d | 缺 Method 实体: %d | 缺 Protocol: %d" %
      (new_bridge, skipped_dup, missing_method, missing_protocol))

# 5. INV -> 综述 facet（幂等）
fv = FacetValue.objects.filter(facet_type="study_type", value="Systematic Review").first()
new_facet = 0
if fv:
    have_pf = set(ProtocolFacet.objects.filter(facet=fv).values_list("protocol_id", flat=True))
    inv_targets = [pid for pid in inv_rows if int(pid) not in have_pf]
    if not DRY:
        with transaction.atomic():
            for pid in inv_targets:
                p = Protocol.objects.filter(id=int(pid)).first()
                if p:
                    ProtocolFacet.objects.create(protocol=p, facet=fv, source="auto")
                    new_facet += 1
    else:
        new_facet = len(inv_targets)
print("INV 综述 facet 将写入: %d（目标 %d，已有 %d）" % (new_facet, len(inv_rows), len(inv_rows) - (new_facet if not DRY else len(inv_targets))))

# 6. 验证闸门（dry-run 与 apply 后都跑）
print("\n=== 验证闸门 ===")
checks = []
n_total = mp.objects.count()
n_lex = mp.objects.filter(evidence_source="lexicon_auto").count()
n_rev = mp.objects.filter(status="review").count()
print("桥总数: %d | lexicon_auto: %d | status=review: %d" % (n_total, n_lex, n_rev))
orphan = mp.objects.filter(protocol__isnull=True).count() + mp.objects.filter(method__isnull=True).count()
print("孤儿桥: %d" % orphan)
print("综述 facet 总数: %d" % (ProtocolFacet.objects.filter(facet=fv).count() if fv else 0))
print("\n完成。%s" % ("dry-run（未写库）" if DRY else "已 apply 写库"))
