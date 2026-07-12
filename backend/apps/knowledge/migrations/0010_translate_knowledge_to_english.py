"""Translate wrongly-imported Chinese knowledge content to English.

The initial data import populated ResearchGoal/Application/Method names and
descriptions in Chinese. The product of this platform is English-only, so this
one-off data migration rewrites those rows to English, keyed by primary key so
it is independent of the exact current (Chinese) string values.

Runs on both SQLite (dev) and Postgres (prod). Reversible.
"""

from django.db import migrations


def _has_cjk(s):
    return bool(s) and any('\u4e00' <= ch <= '\u9fff' for ch in s)


def translate_knowledge(apps, schema_editor):
    ResearchGoal = apps.get_model('knowledge', 'ResearchGoal')
    Application = apps.get_model('knowledge', 'Application')
    Method = apps.get_model('knowledge', 'Method')

    goals = {
        23: ("RNA Labeling & Detection",
             "Fluorescent or biotin labeling of RNA with modified nucleotides for RNA localization, tracking, and quantitative analysis."),
        24: ("DNA Labeling & Probe Preparation",
             "Label DNA with modified deoxynucleotides to prepare nucleic acid probes for hybridization detection."),
        25: ("Gene Expression Analysis",
             "Analyze gene expression levels via PCR, sequencing, or microarray technologies."),
        26: ("Genome Sequencing",
             "Determine DNA sequences for variant detection, genome analysis, and diagnostics."),
        27: ("Cytogenetic Diagnostics",
             "Detect chromosomal abnormalities using FISH and related techniques for genetic disease diagnosis."),
        28: ("RNA Purification & Interaction Studies",
             "Purify RNA or study RNA-protein interactions using biotin-labeled nucleotides."),
        29: ("In Vitro Transcription & RNA Synthesis",
             "Synthesize RNA in vitro for mRNA vaccines, RNA probes, or functional studies."),
        30: ("Pathogen Detection",
             "Rapidly detect pathogenic microorganisms using PCR or probe-based techniques."),
    }
    for pk, (name, summary) in goals.items():
        obj = ResearchGoal.objects.filter(pk=pk).first()
        if obj:
            obj.name = name
            obj.summary = summary
            obj.save()

    # (name, summary); name=None means keep the existing (already-English) name.
    apps_map = {
        30: ("Fluorescent Labeling", "Label nucleic acids with fluorescent dyes (Cy3, Cy5, fluorescein, etc.)."),
        31: ("Biotin Labeling", "Label nucleic acids with biotin and detect via the streptavidin system."),
        32: ("Click Chemistry Labeling", "Conjugate labels to nucleic acids via click chemistry reactions."),
        33: (None, "Polymerase chain reaction amplification and quantification of DNA."),
        34: ("Sequencing", "Determine DNA or RNA sequences."),
        35: (None, "Fluorescence in situ hybridization for DNA/RNA localization in cells."),
        36: ("In Vitro Transcription", "Synthesize RNA molecules in vitro."),
        37: ("RNA/Protein Purification", "Purify molecules using the biotin-streptavidin system."),
    }
    for pk, (name, summary) in apps_map.items():
        obj = Application.objects.filter(pk=pk).first()
        if obj:
            if name is not None and _has_cjk(obj.name):
                obj.name = name
            obj.summary = summary
            obj.save()

    methods = {
        35: ("Enzymatic Labeling",
             "Incorporate labeled nucleotides into newly synthesized nucleic acid strands using a polymerase.",
             "Introduce labels during DNA/RNA synthesis.",
             "Simple to perform\nEven labeling",
             "Labeling efficiency depends on the enzyme"),
        36: ("Random Primer Method",
             "Synthesize labeled probes using random hexamer primers and Klenow fragment.",
             "Prepare high-specific-activity DNA probes.",
             "Even labeling\nHigh specific activity",
             "Non-uniform probe length"),
        37: ("End Labeling",
             "Add labels to the termini of nucleic acids.",
             "Label the 5' or 3' end of a probe.",
             "Defined labeling position",
             "Low specific activity"),
        38: ("T7 Transcription",
             "Synthesize RNA using T7 RNA polymerase.",
             "Large-scale RNA preparation.",
             "High yield\nFast",
             "Requires a T7 promoter"),
        39: ("Real-Time Quantitative PCR (qPCR)",
             "Monitor PCR amplification in real time via fluorescent signal.",
             "Quantitative detection of DNA.",
             "High sensitivity\nQuantifiable",
             "Requires a standard curve"),
        40: ("Sanger Sequencing",
             "Dideoxy chain-termination method for DNA sequencing.",
             "Determine DNA sequence.",
             "High accuracy\nLong read length",
             "Low throughput"),
        41: ("Illumina Sequencing",
             "Sequence-by-synthesis.",
             "High-throughput DNA sequencing.",
             "High throughput\nLow cost",
             "Short read length"),
        42: ("FISH Technique",
             "Hybridize fluorescent probes with DNA in cells.",
             "Detect chromosomal abnormalities.",
             "High spatial resolution",
             "Requires specialized equipment"),
        43: ("Click Chemistry",
             "Copper-catalyzed azide-alkyne cycloaddition.",
             "Bioorthogonal labeling.",
             "High specificity\nEfficient reaction",
             "Requires copper catalyst"),
        44: ("Streptavidin Purification",
             "High-affinity biotin-streptavidin binding.",
             "Purify biotin-labeled molecules.",
             "Extremely high affinity",
             "Harsh elution conditions"),
    }
    for pk, (name, summary, purpose, advantages, limitations) in methods.items():
        obj = Method.objects.filter(pk=pk).first()
        if obj:
            obj.name = name
            obj.summary = summary
            obj.purpose = purpose
            obj.advantages = advantages
            obj.limitations = limitations
            obj.save()


def revert_knowledge(apps, schema_editor):
    ResearchGoal = apps.get_model('knowledge', 'ResearchGoal')
    Application = apps.get_model('knowledge', 'Application')
    Method = apps.get_model('knowledge', 'Method')

    goals = {
        23: ("RNA标记与检测", "使用标记的核苷酸对RNA进行荧光或生物素标记，用于RNA定位、追踪和定量分析"),
        24: ("DNA标记与探针制备", "使用标记的脱氧核苷酸对DNA进行标记，制备用于杂交检测的核酸探针"),
        25: ("基因表达分析", "通过PCR、测序或微阵列技术分析基因表达水平"),
        26: ("基因组测序", "测定DNA序列，用于变异检测、基因组分析和诊断"),
        27: ("细胞遗传学诊断", "使用FISH等技术检测染色体异常，用于遗传病诊断"),
        28: ("RNA纯化与相互作用研究", "使用生物素标记的核苷酸纯化RNA或研究RNA-蛋白质相互作用"),
        29: ("体外转录与RNA合成", "在体外合成RNA，用于mRNA疫苗、RNA探针或功能研究"),
        30: ("病原体检测", "使用PCR或探针技术快速检测病原微生物"),
    }
    for pk, (name, summary) in goals.items():
        obj = ResearchGoal.objects.filter(pk=pk).first()
        if obj:
            obj.name = name
            obj.summary = summary
            obj.save()

    apps_map = {
        30: ("荧光标记", "使用荧光染料（Cy3、Cy5、荧光素等）标记核酸"),
        31: ("生物素标记", "使用生物素标记核酸，通过链霉亲和素系统检测"),
        32: ("点击化学标记", "使用点击化学反应将标记物连接到核酸"),
        33: (None, "聚合酶链式反应扩增和定量DNA"),
        34: ("测序", "测定DNA或RNA序列"),
        35: (None, "荧光原位杂交，用于细胞中DNA/RNA定位"),
        36: ("体外转录", "在体外合成RNA分子"),
        37: ("RNA/蛋白质纯化", "使用生物素-链霉亲和素系统纯化分子"),
    }
    for pk, (name, summary) in apps_map.items():
        obj = Application.objects.filter(pk=pk).first()
        if obj:
            if name is not None:
                obj.name = name
            obj.summary = summary
            obj.save()

    methods = {
        35: ("酶促标记法", "使用聚合酶将标记核苷酸掺入新合成的核酸链", "在DNA/RNA合成过程中引入标记物", "操作简单\n标记均匀", "标记效率受酶影响"),
        36: ("随机引物法", "使用随机六聚体引物和Klenow片段合成标记探针", "制备高比活性DNA探针", "标记均匀\n比活性高", "探针长度不均一"),
        37: ("末端标记法", "在核酸末端添加标记物", "标记探针的5'或3'端", "标记位置明确", "比活性低"),
        38: ("T7转录", "使用T7 RNA聚合酶合成RNA", "大量制备RNA", "产量高\n速度快", "需要T7启动子"),
        39: ("实时荧光定量PCR", "通过荧光信号实时监测PCR扩增", "定量检测DNA", "高灵敏度\n可定量", "需要标准曲线"),
        40: ("Sanger测序", "双脱氧链终止法测定DNA序列", "确定DNA序列", "准确性高\n读长长", "通量低"),
        41: ("Illumina测序", "边合成边测序", "高通量DNA测序", "高通量\n成本低", "读长短"),
        42: ("FISH技术", "荧光探针与细胞中DNA杂交", "染色体异常检测", "空间分辨率高", "需要专业设备"),
        43: ("点击化学", "铜催化叠氮-炔烃环加成反应", "生物正交标记", "特异性高\n反应高效", "需要铜催化剂"),
        44: ("链霉亲和素纯化", "生物素-链霉亲和素高亲和力结合", "纯化生物素标记分子", "亲和力极高", "洗脱条件苛刻"),
    }
    for pk, (name, summary, purpose, advantages, limitations) in methods.items():
        obj = Method.objects.filter(pk=pk).first()
        if obj:
            obj.name = name
            obj.summary = summary
            obj.purpose = purpose
            obj.advantages = advantages
            obj.limitations = limitations
            obj.save()


class Migration(migrations.Migration):
    dependencies = [
        ('knowledge', '0009_alter_protocol_name'),
    ]

    operations = [
        migrations.RunPython(translate_knowledge, revert_knowledge),
    ]
