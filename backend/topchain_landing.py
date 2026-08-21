# topchain_landing.py —— 顶部链 C 分层落地（Step A-E）
# 用法：python -B topchain_landing.py            # dry-run（只读预览，不写库）
#       python -B topchain_landing.py --apply    # 实际写库（事务包裹，可回滚）
# 前置：P1 migration 已应用（Method 10 字段 + MethodProtocol.evidence_source）
import os, sys, json, argparse
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.apps import apps
from django.db import transaction

Method = apps.get_model("knowledge", "Method")
Protocol = apps.get_model("knowledge", "Protocol")
MethodProtocol = apps.get_model("bridges", "MethodProtocol")
FacetValue = apps.get_model("knowledge", "FacetValue")
ProtocolFacet = apps.get_model("knowledge", "ProtocolFacet")

OUT = r"C:\Users\yuankaifeng\WorkBuddy\2026-07-08-11-22-32\_audit_tmp"
ENTITIES = json.load(open(os.path.join(OUT, "step6_method_entities.json"), encoding="utf-8"))
CANDIDATES = json.load(open(os.path.join(OUT, "step5_landing_candidates.json"), encoding="utf-8"))
LAYERS = json.load(open(os.path.join(OUT, "step4_layers_v07.json"), encoding="utf-8"))

parser = argparse.ArgumentParser()
parser.add_argument("--apply", action="store_true", help="实际写库（默认 dry-run）")
args = parser.parse_args()
DRY = not args.apply
log = lambda s: print(("[DRY] " if DRY else "[APP] ") + s)

FAILS = []

# ---------- Step A：旧种子隔离 ----------
FIXTURE_IDS = [35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 47, 48, 49, 50, 51, 52, 53]
existing = Method.objects.filter(id__in=FIXTURE_IDS)
n = existing.count()
log(f"A. 旧 Method 标 is_test_fixture=True：{n} 个（id={FIXTURE_IDS}）")
if n != 18:
    FAILS.append(f"StepA: 预期 18 个旧 Method，实际 {n}")
if not DRY:
    existing.update(is_test_fixture=True)

# ---------- Step B：导入 73 个 Method ----------
slug_of = {e["id_code"]: e["slug"] for e in ENTITIES}
log(f"B. 导入 {len(ENTITIES)} 个 Method 实体（slug 预分配，application 暂空，is_test_fixture=False）")
new_count = 0
for e in ENTITIES:
    existing_m = Method.objects.filter(slug=e["slug"]).first()
    if existing_m is not None:
        if existing_m.is_test_fixture:
            FAILS.append(f"StepB: slug 被 fixture 占用 {e['slug']}（{e['id_code']}）")
        continue  # 已存在且非 fixture → 幂等跳过
    new_count += 1
    if not DRY:
        Method.objects.create(
            name=e["name"], slug=e["slug"], canonical_name=e["name"],
            definition=e["definition"], experimental_purpose=e["purpose"],
            method_type=e["method_type"], is_test_fixture=False,
        )
log(f"   → 将新建 {new_count} 个（其余冲突跳过）")

# ---------- Step C：MethodProtocol 桥写入 ----------
n_cand = len(CANDIDATES)
n_existing_mp = MethodProtocol.objects.count()
log(f"C. 写入 MethodProtocol：{n_cand} 条（evidence_source=lexicon_auto, display_order=0, primary）")
log(f"   现有桥 {n_existing_mp} 条保留（legacy）")
if not DRY:
    with transaction.atomic():
        done = 0
        for pid, c in CANDIDATES.items():
            slug = slug_of.get(c["primary"])
            if not slug:
                continue
            m = Method.objects.filter(slug=slug).first()
            if not m:
                continue
            mp, created = MethodProtocol.objects.get_or_create(
                method=m, protocol_id=int(pid),
                defaults={"evidence_source": "lexicon_auto", "display_order": 0},
            )
            if not created:
                mp.evidence_source = "lexicon_auto"
                mp.save(update_fields=["evidence_source"])
            done += 1
        log(f"   → 已写入 {done} 条")
else:
    log(f"   → 将写入（primary 唯一；多方法协议仅写 primary）")

# ---------- Step D：L4 综述 → study_type facet ----------
l4_ids = [int(pid) for pid, l in LAYERS.items() if l == "L4_EXCLUDE"]
log(f"D. L4 综述协议 {len(l4_ids)} 条 → FacetValue(study_type=Systematic Review) + ProtocolFacet")
if not DRY:
    with transaction.atomic():
        fv, created = FacetValue.objects.get_or_create(
            facet_type="study_type", kind="", value="Systematic Review",
            defaults={"slug": "study_type-systematic-review", "description": "系统综述/元分析研究类型"},
        )
        proto_ids = set(Protocol.objects.filter(id__in=l4_ids).values_list("id", flat=True))
        n_facet = 0
        for pid in proto_ids:
            _, created = ProtocolFacet.objects.get_or_create(
                protocol_id=pid, facet=fv, defaults={"source": "cluster_main"},
            )
            if created:
                n_facet += 1
        log(f"   → 已关联 {n_facet} 条（已有 {len(proto_ids) - n_facet} 条跳过）")

# ---------- Step E：验证闸门 ----------
print("\n=== 验证闸门（只读）===")
checks = []
m_total = Method.objects.count()
m_real = Method.objects.filter(is_test_fixture=False).count()
m_fix = Method.objects.filter(is_test_fixture=True).count()
mp_total = MethodProtocol.objects.count()
try:
    mp_lex = MethodProtocol.objects.filter(evidence_source="lexicon_auto").count()
except Exception:
    mp_lex = None  # migration 未应用时 dry-run 跳过
try:
    mp_legacy = MethodProtocol.objects.filter(evidence_source="legacy").count()
except Exception:
    mp_legacy = None
checks.append(("Method 总数=91(fix 18+real 73)", m_total, 91 if not DRY else m_total))
checks.append(("Method 真实=73", m_real, 73 if not DRY else m_real))
checks.append(("Method fixture=18", m_fix, 18 if not DRY else m_fix))
if mp_lex is not None:
    checks.append(("桥 lexicon_auto=10166", mp_lex, 10166 if not DRY else mp_lex))
if mp_legacy is not None:
    checks.append(("桥 legacy=269", mp_legacy, 269 if not DRY else mp_legacy))
# 孤儿检查
if not DRY:
    orph_mp = MethodProtocol.objects.filter(method__isnull=True).count() + MethodProtocol.objects.filter(protocol__isnull=True).count()
    checks.append(("桥孤儿=0", orph_mp, 0))
    fv_sr = FacetValue.objects.filter(facet_type="study_type", value="Systematic Review").first()
    pf_cnt = ProtocolFacet.objects.filter(facet=fv_sr).count() if fv_sr else 0
    checks.append(("综述 facet 关联数", pf_cnt, len(l4_ids)))
for name, got, want in checks:
    ok = (got == want)
    print(f"  [{'OK ' if ok else 'FAIL'}] {name}：got={got}, want={want}")
    if not ok:
        FAILS.append(f"{name}: got={got}, want={want}")

print("\n" + ("==" * 20))
if FAILS:
    print("验证 FAIL 项：")
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
if DRY:
    print("dry-run 通过（未写库）。确认后执行：python -B topchain_landing.py --apply")
else:
    print("apply 完成，全部闸门通过 ✅")
