# Step 2 只读探查：真实 Product 数据状态（不写库）
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.apps import apps
from django.db.models import Count, Q

# 定位 Product 模型
Product = None
for m in apps.get_models():
    if m.__name__ == "Product":
        Product = m
        break
assert Product is not None, "Product model not found"
print("MODEL:", Product)
print("TOTAL_PRODUCTS:", Product.objects.count())

# 字段探测
all_fields = Product._meta.get_fields()
text_fields = [f.name for f in all_fields
               if f.get_internal_type() in ("CharField", "TextField")]
print("TEXT_FIELDS:", text_fields)
print("ALL_FIELD_NAMES:", [f.name for f in all_fields])

# 来源/类别型分布（仅文本字段里疑似分类的）
cat_like = [f for f in text_fields
            if f.lower() in ("source", "vendor", "data_source", "category",
                             "product_class", "product_type", "supplier")]
for f in cat_like:
    qs = Product.objects.values(f).annotate(c=Count("id")).order_by("-c")
    print(f"\n== {f} distribution (top 25) ==")
    for r in qs[:25]:
        print("   ", r)

# 测序相关 consumables 关键词命中
kw = ["sequenc", "library prep", "library preparation", "adapter", "index",
      "primer", "ngs", "illumina", "pacbio", "nanopore", "rna-seq", "dna-seq",
      "cdna", "rt-pcr", "pcr", "rna extraction", "dna extraction"]
print("\n== SEQUENCING / NUCLEIC-ACID KEYWORD HITS ==")
q = Q()
for f in text_fields:
    for k in kw:
        q |= Q(**{f"{f}__icontains": k})
hits = Product.objects.filter(q)
print("HIT_COUNT:", hits.count())
for p in hits.values("id", "name")[:60]:
    print("   ", p)
