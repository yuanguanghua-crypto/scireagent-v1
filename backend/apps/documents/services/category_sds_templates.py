"""
SDS 类别兜底模板 — 四级降级链 L3。

当产品无 CAS / SMILES / InChI / 名称可解析 PubChem 时，按产品分类路径
（ProductClass 自引用树 或 历史 category_l1）匹配一条大类 GHS 分级模板，
复用 pubchem_fetcher._build_section_data 生成通用 16 节骨架，仅按大类覆盖 GHS
（signal_word / pictograms / hazard_codes）。precaution_codes 沿用通用兜底。

返回 dict 或 None（未命中 → 落到 L4 GENERIC 兜底）。无新依赖。
"""
from .pubchem_fetcher import _build_section_data, _GHS_FALLBACK

# ── 大类 GHS 分级（覆盖主要产品线，关键词命中即可）────────
# 研究用试剂普遍为 GHS07（Warning）+ 低毒 H302/H315/H319/H335；
# 生物类（抗体/蛋白）叠加 GHS08（呼吸道致敏 H334）。
_CATEGORY_GHS = {
    'nucleotide': {
        'label': 'Nucleotides & Nucleosides',
        'signal_word': 'Warning',
        'pictograms': ['GHS07'],
        'hazard_codes': ['H302', 'H315', 'H319', 'H335'],
    },
    'nucleoside': {
        'label': 'Nucleotides & Nucleosides',
        'signal_word': 'Warning',
        'pictograms': ['GHS07'],
        'hazard_codes': ['H302', 'H315', 'H319', 'H335'],
    },
    'oligonucleotide': {
        'label': 'Oligonucleotides',
        'signal_word': 'Warning',
        'pictograms': ['GHS07'],
        'hazard_codes': ['H302', 'H315', 'H319', 'H335'],
    },
    'click': {  # click_chemistry
        'label': 'Click Chemistry',
        'signal_word': 'Warning',
        'pictograms': ['GHS07'],
        'hazard_codes': ['H302', 'H315', 'H319', 'H335'],
    },
    'molecular_biology': {
        'label': 'Molecular Biology',
        'signal_word': 'Warning',
        'pictograms': ['GHS07'],
        'hazard_codes': ['H302', 'H315', 'H319', 'H335'],
    },
    'antibod': {  # antibodies
        'label': 'Antibodies / Proteins',
        'signal_word': 'Warning',
        'pictograms': ['GHS07', 'GHS08'],
        'hazard_codes': ['H302', 'H315', 'H319', 'H334', 'H335'],
    },
    'protein': {
        'label': 'Antibodies / Proteins',
        'signal_word': 'Warning',
        'pictograms': ['GHS07', 'GHS08'],
        'hazard_codes': ['H302', 'H315', 'H319', 'H334', 'H335'],
    },
    'peptide': {
        'label': 'Peptides',
        'signal_word': 'Warning',
        'pictograms': ['GHS07'],
        'hazard_codes': ['H302', 'H315', 'H319', 'H335'],
    },
    'protac': {
        'label': 'PROTAC / Small Molecules',
        'signal_word': 'Warning',
        'pictograms': ['GHS07'],
        'hazard_codes': ['H302', 'H315', 'H319', 'H335'],
    },
    'small_molecule': {
        'label': 'Small Molecules',
        'signal_word': 'Warning',
        'pictograms': ['GHS07'],
        'hazard_codes': ['H302', 'H315', 'H319', 'H335'],
    },
    'reagent': {
        'label': 'General Reagents',
        'signal_word': 'Warning',
        'pictograms': ['GHS07'],
        'hazard_codes': ['H302', 'H315', 'H319', 'H335'],
    },
}


def get_category_sds_template(category_path):
    """按分类路径匹配类别 SDS 模板。

    参数:
        category_path: 字符串，如 'Nucleotides & Nucleosides' 或 'Oligonucleotides > siRNA'。

    返回:
        dict: {
            'category_label': str,
            'signal_word': str,
            'pictograms': list,
            'hazard_codes': list,
            'precaution_codes': list,
            'section_data': dict,   # 通用 16 节骨架（Section 2 GHS 已按大类覆盖）
        }
        未命中返回 None（调用方落到 L4 GENERIC 兜底）。
    """
    if not category_path:
        return None

    path_lower = category_path.lower()
    matched = None
    for key, ghs in _CATEGORY_GHS.items():
        if key in path_lower:
            matched = ghs
            break
    if not matched:
        return None

    # 复用通用 16 节骨架，再用大类 GHS 覆盖 Section 2
    section_data = _build_section_data(
        name='', formula='', mw='', xlogp='', tpsa='',
        hbd=0, hba=0, rtb=0, complexity=0, exact_mass=0,
        heavy_atoms=0, cid=None,
    )
    section_data['section_2'].update({
        'signal_word': matched['signal_word'],
        'pictograms': matched['pictograms'],
        'hazard_codes': matched['hazard_codes'],
        'precaution_codes': _GHS_FALLBACK['precaution_codes'],
    })

    return {
        'category_label': matched['label'],
        'signal_word': matched['signal_word'],
        'pictograms': matched['pictograms'],
        'hazard_codes': matched['hazard_codes'],
        'precaution_codes': _GHS_FALLBACK['precaution_codes'],
        'section_data': section_data,
    }
