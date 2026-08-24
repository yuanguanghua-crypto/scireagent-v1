# 生产顶部链迁移：Method 73 + Application 20 + RG 24 + M2M + 桥 11,726（dry-run/--apply）
# 运行：docker compose exec -T backend python /tmp/migrate_topchain_prod.py [--apply]
import csv, os, sys
sys.path.insert(0, "/app")  # 容器工作目录，使 config.settings 可导入
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.apps import apps
from django.db import transaction
Method = apps.get_model("knowledge", "Method")
App = apps.get_model("knowledge", "Application")
RG = apps.get_model("knowledge", "ResearchGoal")
mp = apps.get_model("bridges", "MethodProtocol")
Protocol = apps.get_model("knowledge", "Protocol")

DRY = "--apply" not in sys.argv
print("MODE:", "DRY-RUN" if DRY else "APPLY")

def read(name):
    return list(csv.DictReader(open("/tmp/%s" % name, encoding="utf-8")))

methods = read("mig_methods.csv")
apps_ = read("mig_apps.csv")
rgs = read("mig_rgs.csv")
rg_ap = read("mig_rg_ap.csv")
bridges = read("mig_bridges.csv")
proto_map = read("dev_protocol_map.csv")
print("methods:%d apps:%d rgs:%d rg_ap:%d bridges:%d proto_map:%d" %
      (len(methods), len(apps_), len(rgs), len(rg_ap), len(bridges), len(proto_map)))

# ---- 只读验证 ----
exist_m = [m["slug"] for m in methods if Method.objects.filter(slug=m["slug"]).exists()]
exist_a = [a["slug"] for a in apps_ if App.objects.filter(slug=a["slug"]).exists()]
exist_r = [r["slug"] for r in rgs if RG.objects.filter(slug=r["slug"]).exists()]
print("生产已存在 slug：method %d / app %d / rg %d" % (len(exist_m), len(exist_a), len(exist_r)))
if exist_m[:5]: print("  method 冲突样例:", exist_m[:5])

# protocol 映射：dev_id -> prod_id
all_prot = list(Protocol.objects.all().values_list("slug", "version", "id"))
key2id = {}
for s, v, pid in all_prot:
    key2id[(s, v)] = pid
dev_map = {}
miss = []
for row in proto_map:
    v = row["version"] or None
    pid = key2id.get((row["slug"], v))
    if pid is None:
        miss.append(row["slug"])
    dev_map[row["dev_id"]] = pid
print("protocol 映射缺失:", len(miss), miss[:5])
n_bridge_ok = sum(1 for b in bridges if dev_map.get(b["dev_protocol_id"]) is not None)
print("桥可映射:", n_bridge_ok, "/", len(bridges))

if DRY:
    print("DRY-RUN 完成，未写库")
    sys.exit(0)

# ---- APPLY ----
with transaction.atomic():
    # 1. Method 插入（slug 幂等）
    slug2id = {}
    for m in methods:
        obj = Method.objects.filter(slug=m["slug"]).first()
        if obj:
            slug2id[m["slug"]] = obj.id
            continue
        obj = Method.objects.create(
            slug=m["slug"], name=m["name"], canonical_name=m["canonical_name"] or m["name"],
            definition=m["definition"], experimental_purpose=m["experimental_purpose"],
            method_type=m["method_type"] or "", is_test_fixture=False,
        )
        slug2id[m["slug"]] = obj.id
    print("Method 就绪:", len(slug2id))

    # 2. Application 插入
    app_slug2id = {}
    for a in apps_:
        obj = App.objects.filter(slug=a["slug"]).first()
        if obj:
            app_slug2id[a["slug"]] = obj.id
            continue
        obj = App.objects.create(slug=a["slug"], name=a["name"], summary=a["summary"] or "", is_test_fixture=False)
        app_slug2id[a["slug"]] = obj.id
    print("Application 就绪:", len(app_slug2id))

    # 3. method.application FK
    for m in methods:
        if m["app_slug"] and m["app_slug"] in app_slug2id:
            Method.objects.filter(slug=m["slug"]).update(application_id=app_slug2id[m["app_slug"]])
    print("method.application 已关联")

    # 4. ResearchGoal 插入 + M2M
    rg_slug2id = {}
    for r in rgs:
        obj = RG.objects.filter(slug=r["slug"]).first()
        if obj:
            rg_slug2id[r["slug"]] = obj.id
            continue
        obj = RG.objects.create(slug=r["slug"], name=r["name"], summary=r["summary"] or "", is_test_fixture=False)
        rg_slug2id[r["slug"]] = obj.id
    print("RG 就绪:", len(rg_slug2id))
    for row in rg_ap:
        rg = RG.objects.filter(slug=row["rg_slug"]).first()
        ap = App.objects.filter(slug=row["app_slug"]).first()
        if rg and ap:
            rg.application_collection.add(ap)
    print("RG↔AP M2M 已关联:", len(rg_ap))

    # 5. 桥插入（幂等）
    existing = set(mp.objects.values_list("protocol_id", "method_id"))
    n_new = n_skip_proto = n_skip_dup = n_skip_method = 0
    for b in bridges:
        prod_pid = dev_map.get(b["dev_protocol_id"])
        mid = slug2id.get(b["method_slug"])
        if prod_pid is None:
            n_skip_proto += 1
            continue
        if mid is None:
            n_skip_method += 1
            continue
        if (prod_pid, mid) in existing:
            n_skip_dup += 1
            continue
        mp.objects.create(protocol_id=prod_pid, method_id=mid,
                          evidence_source=b["evidence_source"],
                          status=b["status"] or "review", display_order=0)
        existing.add((prod_pid, mid))
        n_new += 1
    print("桥写入: %d | 跳过协议缺失: %d | 跳过重复: %d | 跳过方法缺失: %d" %
          (n_new, n_skip_proto, n_skip_dup, n_skip_method))

# ---- 闸门 ----
print("=== 闸门 ===")
print("Method 总数:", Method.objects.count())
print("Application 总数:", App.objects.count())
print("RG 总数:", RG.objects.count())
print("桥总数:", mp.objects.count())
print("孤儿桥:", mp.objects.filter(protocol__isnull=True).count() + mp.objects.filter(method__isnull=True).count())
