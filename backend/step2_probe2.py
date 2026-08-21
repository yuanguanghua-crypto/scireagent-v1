# Step 2 探查(二)：类别分布 + 精确文库/测序耗材关键词
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.apps import apps
from django.db.models import Count, Q
Product = apps.get_model("commerce", "Product")

def dist(field, top=30):
    print(f"\n=== {field} distribution (top {top}) ===")
    for r in Product.objects.values(field).annotate(c=Count("id")).order_by("-c")[:top]:
        print("   ", r)

dist("category_l1")
dist("category_l2")
dist("product_class")
dist("status")

precise = ["library prep", "library preparation", "sequencing kit", "sequencing reagent",
           "adapter ligation", "index", "rna-seq", "cdna synthesis", "reverse transcriptase",
           "pcr kit", "pcr master mix", "flow cell", "ngs", "ion torrent", "illumina",
           "pacbio", "nanopore", "next generation", "sequencing chemistry", "library kit"]
q = Q()
for f in ["name", "overview", "usage", "category_l1", "category_l2"]:
    for k in precise:
        q |= Q(**{f"{f}__icontains": k})
print("\n=== PRECISE LIBRARY-PREP / SEQUENCING CONSUMABLE HITS ===")
hits = Product.objects.filter(q)
print("HIT_COUNT:", hits.count())
for p in hits.values("id", "name", "category_l1", "category_l2")[:60]:
    print("   ", p)

# 反向：用 nucleotide/dNTP 之外的"核酸相关"粗分类，看整体覆盖面
print("\n=== 整体 name 抽样(前 15 条) ===")
for p in Product.objects.values("id", "name", "category_l1")[:15]:
    print("   ", p)
