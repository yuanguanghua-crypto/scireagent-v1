# step9c_rg.py —— 顶部链重建②：RG 研究领域层（24 个策展 + M:N 关联）
import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.apps import apps
from django.db import transaction
ResearchGoal = apps.get_model("knowledge", "ResearchGoal")
Application = apps.get_model("knowledge", "Application")

# 24 个研究领域 RG：name / slug / summary / 覆盖 Application(slug 列表)
RGS = [
    ("Cancer Biology", "cancer-biology", "癌症发生发展与转移机制研究",
     ["sequencing-library-prep", "sequencing-technologies", "cell-culture-differentiation", "microscopy-imaging", "cloning-genome-editing", "enzymology-biochemical-assays"]),
    ("Neurobiology & Behavior", "neurobiology-behavior", "神经功能、可塑性与行为机制",
     ["model-organism-invivo-behavioral", "microscopy-imaging", "enzymology-biochemical-assays"]),
    ("Neurodegenerative Disease", "neurodegenerative-disease", "神经退行性疾病（阿尔茨海默/帕金森等）病理机制",
     ["western-blotting", "enzymology-biochemical-assays", "microscopy-imaging", "protein-downstream-processing"]),
    ("Immunology & Inflammation", "immunology-inflammation", "免疫应答、炎症与免疫调控",
     ["immune-cell-analysis-immunoassays", "cell-culture-differentiation", "microbial-pathogen-assays"]),
    ("Infectious Disease & Microbiology", "infectious-disease", "病原微生物、病毒感染与传播机制",
     ["microbial-pathogen-assays", "sequencing-technologies", "pcr-amplification"]),
    ("Metabolic Disease", "metabolic-disease", "代谢疾病与代谢调控紊乱",
     ["metabolite-sample-preparation", "enzymology-biochemical-assays"]),
    ("Developmental Biology", "developmental-biology", "发育与形态发生机制",
     ["cell-culture-differentiation", "microscopy-imaging", "immunostaining-histology"]),
    ("Stem Cell & Regenerative Biology", "stem-cell-regeneration", "干细胞多能性、分化与再生",
     ["cell-culture-differentiation", "cloning-genome-editing"]),
    ("Plant Biology & Stress", "plant-biology-stress", "植物生理、发育与胁迫应答",
     ["enzymology-biochemical-assays", "metabolite-sample-preparation", "microbial-pathogen-assays"]),
    ("Environmental Science & Ecology", "environmental-ecology", "环境监测、生态与生物多样性",
     ["environmental-sampling-edna", "nucleic-acid-extraction", "microbial-pathogen-assays"]),
    ("Structural Biology", "structural-biology", "生物大分子结构与功能",
     ["protein-production", "protein-downstream-processing", "microscopy-imaging", "enzymology-biochemical-assays"]),
    ("Chemical Biology & Drug Discovery", "chemical-biology-drug", "化学生物学探针与药物发现",
     ["peptide-synthesis", "particle-microsphere-synthesis", "enzymology-biochemical-assays", "metabolite-sample-preparation"]),
    ("Genomics & Epigenomics", "genomics-epigenomics", "基因组结构、序列与表观修饰",
     ["nucleic-acid-extraction", "sequencing-library-prep", "sequencing-technologies", "cloning-genome-editing", "pcr-amplification"]),
    ("Transcriptomics & Gene Expression", "transcriptomics-expression", "基因表达定量与转录调控",
     ["sequencing-library-prep", "pcr-amplification", "microscopy-imaging"]),
    ("Proteomics & Protein Function", "proteomics-protein", "蛋白组学、蛋白功能与修饰",
     ["protein-extraction", "western-blotting", "enzymology-biochemical-assays", "metabolite-sample-preparation"]),
    ("Cell Biology & Signaling", "cell-biology-signaling", "细胞结构、功能与信号转导",
     ["cell-culture-differentiation", "microscopy-imaging", "immune-cell-analysis-immunoassays", "enzymology-biochemical-assays"]),
    ("Genetics & Gene Function", "genetics-gene-function", "遗传学、基因功能与表型关联",
     ["cloning-genome-editing", "pcr-amplification", "nucleic-acid-extraction"]),
    ("Microbiology & Microbiome", "microbiology-microbiome", "微生物生理、生态与微生物组",
     ["microbial-pathogen-assays", "nucleic-acid-extraction", "sequencing-library-prep"]),
    ("RNA Biology", "rna-biology", "RNA 代谢、调控与功能",
     ["nucleic-acid-extraction", "sequencing-library-prep", "pcr-amplification", "western-blotting"]),
    ("Aging & Longevity", "aging-longevity", "衰老机制与寿命调控",
     ["cell-culture-differentiation", "enzymology-biochemical-assays", "model-organism-invivo-behavioral"]),
    ("Pharmacology & Toxicology", "pharmacology-toxicology", "药物代谢、药效与毒性",
     ["metabolite-sample-preparation", "enzymology-biochemical-assays", "model-organism-invivo-behavioral", "immune-cell-analysis-immunoassays"]),
    ("Agriculture & Food Science", "agriculture-food", "作物、食品与微生物应用",
     ["microbial-pathogen-assays", "environmental-sampling-edna", "enzymology-biochemical-assays"]),
    ("Synthetic Biology", "synthetic-biology", "工程化生物系统与合成生物学",
     ["cloning-genome-editing", "protein-production", "particle-microsphere-synthesis"]),
    ("Biophysics", "biophysics", "生物分子与细胞的物理机制",
     ["microscopy-imaging", "protein-downstream-processing", "enzymology-biochemical-assays"]),
]

# Step 1: 旧 RG 测试种子 → fixture
old = ResearchGoal.objects.exclude(is_test_fixture=True)
print("1. 旧 RG 测试种子:", old.count(), "→ fixture=True")
old.update(is_test_fixture=True)

# Step 2: 创建 24 个 RG + M:N 关联
created_list = []
with transaction.atomic():
    for name, slug, summary, app_slugs in RGS:
        rg, is_new = ResearchGoal.objects.get_or_create(
            slug=slug,
            defaults={"name": name, "summary": summary, "is_test_fixture": False, "priority": 0},
        )
        apps = Application.objects.filter(slug__in=app_slugs, is_test_fixture=False)
        rg.application_collection.set(apps)
        if is_new:
            created_list.append((slug, name, apps.count()))
        else:
            print("   复用:", slug)
print("2. 新建 RG:", len(created_list))
for c, n, k in created_list:
    print("   ", c, "|", n, "| 关联 AP:", k)

# Step 3: 验证
print("\n== 验证 ==")
print("RG 总数:", ResearchGoal.objects.count(),
      "| 真实:", ResearchGoal.objects.filter(is_test_fixture=False).count(),
      "| fixture:", ResearchGoal.objects.filter(is_test_fixture=True).count())
n_rg_with = ResearchGoal.objects.filter(is_test_fixture=False, application_collection__isnull=False).distinct().count()
print("真实 RG 有 AP 关联:", n_rg_with, "/", ResearchGoal.objects.filter(is_test_fixture=False).count())
# 每个真实 Application 至少挂 1 个 RG？
apps_real = Application.objects.filter(is_test_fixture=False)
orphan_ap = [a.slug for a in apps_real if a.research_goal_collections.count() == 0]
print("无 RG 关联的真实 Application:", len(orphan_ap), orphan_ap)
# 统计每个 RG 的 AP 数
from collections import Counter
cnt = Counter()
for rg in ResearchGoal.objects.filter(is_test_fixture=False):
    cnt[rg.application_collection.count()] += 1
print("RG 覆盖 AP 数分布:", dict(sorted(cnt.items())))
