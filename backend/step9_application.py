# step9_application.py —— 顶部链重建①：Application 技术族层（dev）
# 旧 15 测试种子标 fixture → 创建 19 个真实技术族 → 73 Method.application 填上
import os, json
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.apps import apps
from django.db import transaction
Application = apps.get_model("knowledge", "Application")
Method = apps.get_model("knowledge", "Method")

OUT = r"C:\Users\yuankaifeng\WorkBuddy\2026-07-08-11-22-32\_audit_tmp"
entities = json.load(open(os.path.join(OUT, "step6_method_entities.json"), encoding="utf-8"))

# 19 个技术族（草案 A 编号 → 英文名/定义）
APPS = {
    "A1":   ("Nucleic Acid Extraction", "从生物样本提取纯化核酸（DNA/RNA）的技术族", "nucleic-acid-extraction"),
    "A2":   ("Protein Extraction", "蛋白提取/裂解/增溶技术族", "protein-extraction"),
    "A2b":  ("Metabolite Sample Preparation", "代谢物/脂质/细胞器样本制备技术族", "metabolite-sample-preparation"),
    "A3":   ("Sequencing & Library Prep", "测序文库制备与测序技术族", "sequencing-library-prep"),
    "A4":   ("PCR & Amplification", "PCR 扩增与反转录技术族", "pcr-amplification"),
    "A5":   ("Cloning & Genome Editing", "克隆、转化与基因组编辑技术族", "cloning-genome-editing"),
    "A6":   ("Protein Production", "重组蛋白表达技术族", "protein-production"),
    "A6b":  ("Protein Downstream Processing", "蛋白纯化/层析技术族", "protein-downstream-processing"),
    "A7":   ("Cell Culture & Differentiation", "细胞培养、分离与分化技术族", "cell-culture-differentiation"),
    "A8":   ("Immune Cell Analysis & Immunoassays", "免疫细胞分析与免疫测定技术族", "immune-cell-analysis-immunoassays"),
    "A9":   ("Microscopy & Imaging", "显微成像技术族", "microscopy-imaging"),
    "A10":  ("Immunostaining & Histology", "免疫染色与组织学技术族", "immunostaining-histology"),
    "A11":  ("Western Blotting", "蛋白印迹检测技术族", "western-blotting"),
    "A12a": ("Peptide Synthesis", "多肽合成技术族", "peptide-synthesis"),
    "A12b": ("Particle/Microsphere Synthesis", "微粒/微球/小分子合成技术族", "particle-microsphere-synthesis"),
    "A13":  ("Enzymology & Biochemical Assays", "酶学与生化测定技术族", "enzymology-biochemical-assays"),
    "A14":  ("Microbial & Pathogen Assays", "微生物与病原检测技术族", "microbial-pathogen-assays"),
    "A15":  ("Model Organism / In-vivo / Behavioral Studies", "模式生物、体内实验与行为学研究技术族", "model-organism-invivo-behavioral"),
    "A17":  ("Environmental Sampling & eDNA Analysis", "环境采样与 eDNA 分析技术族", "environmental-sampling-edna"),
}

# Step 1: 旧 Application 测试种子 → fixture
old = Application.objects.exclude(is_test_fixture=True)
print("1. 旧 Application 测试种子（fixture=False）:", old.count(), "→ 标 fixture=True")
for a in old:
    print("   ", a.id, a.name)
old.update(is_test_fixture=True)

# Step 2: 创建 19 个技术族（research_goal 暂空，RG 下一刀）
created = []
with transaction.atomic():
    for code, (name, summary, slug) in APPS.items():
        app, is_new = Application.objects.get_or_create(
            slug=slug,
            defaults={"name": name, "summary": summary, "is_test_fixture": False, "sort_order": 0},
        )
        if is_new:
            created.append((code, name))
        else:
            print("   已存在:", slug, "→ 复用")
print("2. 新建 Application 技术族:", len(created))
for c, n in created:
    print("   ", c, n)

# Step 3: 73 Method.application 按 app_code 填上
slug_by_code = {k: v[2] for k, v in APPS.items()}
n_fill = 0; n_missing = []
with transaction.atomic():
    for e in entities:
        m = Method.objects.filter(slug=e["slug"]).first()
        if not m:
            n_missing.append(e["id_code"])
            continue
        app_slug = slug_by_code.get(e["app_code"])
        if not app_slug:
            n_missing.append(e["id_code"] + ":no-app")
            continue
        app = Application.objects.filter(slug=app_slug).first()
        if m.application_id != app.id:
            m.application = app
            m.save(update_fields=["application"])
            n_fill += 1
print("3. Method.application 填写/更新:", n_fill, "| 未处理:", len(n_missing), n_missing[:10])

# Step 4: 验证
print("\n== 验证 ==")
print("Application 总数:", Application.objects.count(),
      "| 真实(fixture=False):", Application.objects.filter(is_test_fixture=False).count(),
      "| fixture:", Application.objects.filter(is_test_fixture=True).count())
m_real = Method.objects.filter(is_test_fixture=False)
print("Method 真实:", m_real.count(), "| 有 application:", m_real.exclude(application=None).count(),
      "| 无 application:", m_real.filter(application=None).count())
from collections import Counter
cnt = Counter(m.application.slug for m in m_real.exclude(application=None).select_related('application'))
print("Method→Application 分布:", dict(sorted(cnt.items(), key=lambda x: -x[1])))
