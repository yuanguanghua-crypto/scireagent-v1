# step9b_a3split.py —— A3 拆分（A3a Library Prep / A3b Sequencing）+ Method 重分配
import os, json
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.apps import apps
from django.db import transaction
Application = apps.get_model("knowledge", "Application")
Method = apps.get_model("knowledge", "Method")

with transaction.atomic():
    a3 = Application.objects.get(slug="sequencing-library-prep")  # 原 A3
    # A3 → A3a Sequencing Library Preparation
    a3.name = "Sequencing Library Preparation"
    a3.summary = "测序文库制备技术族（扩增子/RNA-seq/染色质 profiling）"
    a3.save(update_fields=["name", "summary"])
    print("A3a:", a3.slug, a3.name)
    # 新建 A3b Sequencing Technologies
    a3b, created = Application.objects.get_or_create(
        slug="sequencing-technologies",
        defaults={"name": "Sequencing Technologies", "summary": "测序平台与长读长测序技术族（Nanopore/PacBio/病毒基因组测序）",
                  "is_test_fixture": False, "sort_order": 0},
    )
    print("A3b:", a3b.slug, a3b.name, "new=", created)
    # Method 重分配：M12/M13 → A3b；其余 A3 的留 A3a
    for slug, target in [("long-read-sequencing", a3b), ("viral-genome-sequencing", a3b)]:
        m = Method.objects.filter(slug=slug).first()
        if m:
            m.application = target
            m.save(update_fields=["application"])
            print("  Method", slug, "→", target.name)
    # 验证
    a3a_m = Method.objects.filter(application=a3).count()
    a3b_m = Method.objects.filter(application=a3b).count()
    print("A3a 挂载 Method:", a3a_m, "| A3b 挂载 Method:", a3b_m)
    n_empty = Method.objects.filter(is_test_fixture=False, application=None).count()
    print("真实 Method 无 application:", n_empty)
