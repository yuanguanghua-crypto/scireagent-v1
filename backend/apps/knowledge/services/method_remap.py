"""S2 核心逻辑：按重挂表把真实 Method 重挂到正确 Application；
把「整句实验描述冒充 Method」的伪 Method 整体重挂到隔离用 catch-all Application
（F3 Option A：零删除，保留全部 Protocol / Product 桥接）。

守铁律①：不删除任何 Product / Protocol / 顶部实体（ResearchGoal / Application /
Method 本身）。
- 重挂    = 改 Method.application FK
- 伪 Method = 不删，整体重挂到新建的 catch-all Application
            （research_goal=None，使其脱离任意 RG 导航树，解除对 FL 的塌缩贡献）
            MethodProtocol / ProductMethod 桥接行原样保留（零删除，守 Path 一）
"""
from django.db import transaction
from django.utils.text import slugify
from apps.knowledge.models import Application, Method


# ---- v2 方案 S2 真实重挂配置 ----
# method_name -> target_application_name（仅列需要重挂的；Enzymatic Labeling /
# End Labeling / Random Primer Method 归属本就正确，不重挂）
REMAP_TABLE = {
    'Click Chemistry': 'Click Chemistry Labeling',
    'Sanger Sequencing': 'Sequencing',
    'Streptavidin Purification': 'RNA/Protein Purification',
    'FISH Technique': 'FISH',
    'T7 Transcription': 'In Vitro Transcription',
    'Real-Time Quantitative PCR (qPCR)': 'PCR/qPCR',
    'Illumina Sequencing': 'Sequencing',
}
PSEUDO_METHODS = [
    'Administration of an AAV shuffled library mixed with patient serum into mice, '
    'followed by isolation and characterization of Nab-escaping AAV chimeric capsid mutants.',
    'Generation of Murine Leukemia Virus (MLV)-based pseudotyped particles incorporating '
    'heterologous envelope glycoproteins, such as the Middle East Respiratory Syndrome '
    'Coronavirus (MERS-CoV) spike (S), with reporter genes like luciferase for infectivity '
    'quantification.',
    'Loading of calcium-sensitive fluorescence dye fluo-3 AM into guard cells, combined with '
    'confocal laser scanning microscopy, to record Ca2+cyt changes upon ABA (abscisic acid) '
    'or PA (phosphatidic acid) treatment.',
    'Purification of 5-hydroxymethylcytosine carbamoyltransferase and in vitro assays '
    'converting 5-hydroxymethylcytosine (5hmC) to 5-carbamoyloxymethylcytosine (5cmC) using '
    'DNA, RNA, and single nucleotide/deoxynucleotide substrates.',
    'Separation of collagen crosslinks using a diamond hydride column with water and '
    'acetonitrile solvents containing 0.1% formic acid, followed by mass spectrometry '
    'detection.',
]
# F3 Option A：伪 Method 重挂目标（隔离用 catch-all，research_goal=None）
PSEUDO_TARGET_APPLICATION = 'Other / Experimental Descriptions'


def apply_method_remap(remap_table, pseudo_methods, pseudo_target_app_name,
                       dry_run=False):
    """按配置重挂 Method→Application，并把伪 Method 重挂到 catch-all Application。

    返回 report dict 供命令打印与测试断言。dry_run 时零写入（事务回滚）。
    """
    report = {
        'remapped': [],
        'reparented_pseudo': [],
        'created_catchall_app': False,
        'missing_apps': [],
        'missing_methods': [],
    }

    with transaction.atomic():
        # 1) 重挂真实 Method（幂等：已正确的不改写）
        for method_name, app_name in remap_table.items():
            try:
                method = Method.objects.get(name=method_name)
            except Method.DoesNotExist:
                report['missing_methods'].append(method_name)
                continue
            try:
                app = Application.objects.get(name=app_name)
            except Application.DoesNotExist:
                report['missing_apps'].append(app_name)
                continue
            if method.application_id != app.id:
                report['remapped'].append((method_name, app_name))
                if not dry_run:
                    method.application = app
                    method.save(update_fields=['application'])

        # 2) 伪 Method 重挂到 catch-all Application（Option A：零删除）
        catchall = Application.objects.filter(name=pseudo_target_app_name).first()
        if catchall is None:
            report['created_catchall_app'] = True
            if not dry_run:
                catchall = Application.objects.create(
                    name=pseudo_target_app_name,
                    research_goal=None,
                    slug=slugify(pseudo_target_app_name),
                )
        for pseudo_name in pseudo_methods:
            try:
                method = Method.objects.get(name=pseudo_name)
            except Method.DoesNotExist:
                report['missing_methods'].append(pseudo_name)
                continue
            already = catchall is not None and method.application_id == catchall.id
            if not already:
                report['reparented_pseudo'].append((pseudo_name, pseudo_target_app_name))
                if not dry_run and catchall is not None:
                    method.application = catchall
                    method.save(update_fields=['application'])

        if dry_run:
            transaction.set_rollback(True)

    return report
