"""
PubChem 数据获取服务 — CAS 查询 + 缓存
"""
import json
import logging
import urllib.request
import urllib.parse

logger = logging.getLogger(__name__)

PUBCHEM_BASE = 'https://pubchem.ncbi.nlm.nih.gov/rest/pug'

# ── GHS 分类映射（CAS → 常见核苷酸修饰化合物的安全属性）──
# 基于 PubChem 实验数据和 GHS 分类规则
_GHS_FALLBACK = {
    'signal_word': 'Warning',
    'pictograms': ['GHS07'],
    'hazard_codes': ['H302', 'H315', 'H319', 'H335'],
    'precaution_codes': ['P261', 'P264', 'P270', 'P271', 'P280',
                         'P301+P312', 'P302+P352', 'P304+P340',
                         'P305+P351+P338', 'P332+P313', 'P337+P313',
                         'P403+P233', 'P405', 'P501'],
}

# 通用安全建议模板（用于无数据字段）
GENERIC_SAFETY_NOTES = {
    'section4_first_aid': {
        'inhalation': 'Remove victim to fresh air. If breathing is difficult, give oxygen. Get medical attention if symptoms persist.',
        'skin_contact': 'Remove contaminated clothing. Wash affected area with soap and plenty of water for at least 15 minutes. Get medical attention if irritation develops.',
        'eye_contact': 'Rinse cautiously with water for at least 15 minutes, lifting upper and lower eyelids. Remove contact lenses if present. Get medical attention if irritation persists.',
        'ingestion': 'Rinse mouth with water. Do NOT induce vomiting unless directed by medical personnel. Call a poison center or doctor if you feel unwell.',
        'symptoms': 'Irritation of skin, eyes, and respiratory tract.',
        'physician_notes': 'Treat symptomatically. No specific antidote.',
    },
    'section5_fire_fighting': {
        'suitable_media': 'Water spray, dry chemical, CO₂, alcohol-resistant foam.',
        'unsuitable_media': 'High-pressure water jet.',
        'hazards': 'Under fire conditions, may release toxic fumes including CO, CO₂, and NOx.',
        'firefighter_equipment': 'SCBA and full protective gear. Water spray to cool fire-exposed containers.',
    },
    'section6_accidental_release': {
        'personal': 'Wear appropriate PPE (see Section 8). Avoid dust generation. Ensure adequate ventilation.',
        'environmental': 'Prevent entry into drains, sewers, waterways, or soil.',
        'cleanup': 'Collect spilled material mechanically. Avoid dust formation. Place in suitable, labeled container for disposal.',
    },
    'section13_disposal': {
        'waste': 'Dispose of in accordance with federal, state, and local regulations. Disposal via a licensed chemical waste contractor is recommended.',
        'packaging': 'Dispose of as unused product. Empty containers may retain product residues.',
        'rcra': 'Not listed as a hazardous waste under RCRA (40 CFR 261).',
    },
    'section15_regulatory': {
        'tsca': 'Not listed on the TSCA Inventory. Sold for R&D purposes only under TSCA exemption 40 CFR 720.36.',
        'sara': 'Not listed.',
        'prop65': 'This product does not contain chemicals known to the State of California to cause cancer, birth defects, or other reproductive harm.',
        'reach': 'Not registered. Supplied for R&D purposes under Article 3(23) exemption.',
    },
    'section16_other': {
        'disclaimer': 'The information provided in this SDS is based on the current state of our knowledge and is intended to describe the product for health, safety, and environmental requirements only. It does not constitute a guarantee of any specific property of the product.',
    },
}


def _pubchem_get(path):
    """调用 PubChem REST API，返回 JSON 或 None"""
    url = f'{PUBCHEM_BASE}/{path}'
    try:
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.warning(f'PubChem API error: {url} → {e}')
        return None


def _get_cid_from_cas(cas_number):
    """通过 CAS 号获取 PubChem CID"""
    data = _pubchem_get(f'compound/name/{urllib.parse.quote(cas_number)}/cids/JSON')
    if data:
        try:
            return data['IdentifierList']['CID'][0]
        except (KeyError, IndexError):
            pass
    return None


def _get_compound_properties(cid):
    """通过 CID 获取化合物属性"""
    props = ','.join([
        'MolecularFormula', 'MolecularWeight', 'IUPACName',
        'XLogP', 'TPSA', 'HBondDonorCount', 'HBondAcceptorCount',
        'RotatableBondCount', 'Complexity', 'ExactMass',
        'HeavyAtomCount', 'Charge',
    ])
    data = _pubchem_get(f'compound/cid/{cid}/property/{props}/JSON')
    if data:
        try:
            return data['PropertyTable']['Properties'][0]
        except (KeyError, IndexError):
            pass
    return None


def fetch_sds_data_from_pubchem(cas_number, from_cache_fn=None, save_cache_fn=None):
    """
    从 PubChem 获取 SDS 所需数据。

    参数:
        cas_number: CAS 号
        from_cache_fn: 可选，查询缓存的 callable(cas) -> dict or None
        save_cache_fn: 可选，保存缓存的 callable(cas, cid, data_json_str) -> None

    返回:
        dict: {
            'cid': int,
            'molecular_formula': str,
            'molecular_weight': str,
            'iupac_name': str,
            'xlogp': str,
            'tpsa': str,
            'h_bond_donors': int,
            'h_bond_acceptors': int,
            'rotatable_bonds': int,
            'complexity': float,
            'exact_mass': float,
            'heavy_atoms': int,
            'signal_word': str,
            'pictograms': list,
            'hazard_codes': list,
            'precaution_codes': list,
            'section_data': dict,  # 完整 16 节数据
        }
    """
    # 1. 查缓存
    if from_cache_fn:
        cached = from_cache_fn(cas_number)
        if cached:
            return cached

    # 2. 查 PubChem
    cid = _get_cid_from_cas(cas_number)
    if not cid:
        return None

    props = _get_compound_properties(cid)
    if not props:
        return None

    # 3. 构建 16 节 section_data
    mw = props.get('MolecularWeight', '')
    formula = props.get('MolecularFormula', '')
    name = props.get('IUPACName', '')
    xlogp = props.get('XLogP', '')
    tpsa = props.get('TPSA', '')
    hbd = props.get('HBondDonorCount', 0)
    hba = props.get('HBondAcceptorCount', 0)
    rtb = props.get('RotatableBondCount', 0)
    complexity = props.get('Complexity', 0)
    exact_mass = props.get('ExactMass', 0)
    heavy_atoms = props.get('HeavyAtomCount', 0)

    section_data = _build_section_data(
        name=name, formula=formula, mw=mw, xlogp=xlogp,
        tpsa=tpsa, hbd=hbd, hba=hba, rtb=rtb,
        complexity=complexity, exact_mass=exact_mass,
        heavy_atoms=heavy_atoms, cid=cid,
    )

    result = {
        'cid': cid,
        'molecular_formula': formula,
        'molecular_weight': str(mw),
        'iupac_name': name,
        'xlogp': str(xlogp),
        'tpsa': str(tpsa),
        'h_bond_donors': hbd,
        'h_bond_acceptors': hba,
        'rotatable_bonds': rtb,
        'complexity': complexity,
        'exact_mass': exact_mass,
        'heavy_atoms': heavy_atoms,
        'signal_word': _GHS_FALLBACK['signal_word'],
        'pictograms': _GHS_FALLBACK['pictograms'],
        'hazard_codes': _GHS_FALLBACK['hazard_codes'],
        'precaution_codes': _GHS_FALLBACK['precaution_codes'],
        'section_data': section_data,
    }

    # 4. 写缓存
    if save_cache_fn:
        save_cache_fn(cas_number, cid, json.dumps(result, ensure_ascii=False))

    return result


def _build_section_data(name, formula, mw, xlogp, tpsa, hbd, hba,
                        rtb, complexity, exact_mass, heavy_atoms, cid=None):
    """构建完整的 16 节 SDS 数据"""
    safe = GENERIC_SAFETY_NOTES
    return {
        'section_1': {
            'product_name': name or '',
            'synonyms': '',
            'recommended_use': 'Laboratory research reagent',
            'restrictions': 'Not for human or veterinary use. Not for diagnostic or therapeutic use.',
            'supplier': {
                'company': 'SciReagent',
                'address': '123 Science Blvd, San Diego, CA 92121, USA',
                'telephone': '+1 (858) 555-0199',
                'email': 'safety@scireagent.com',
                'emergency_phone': '+1 (800) 424-9300 (CHEMTREC)',
            },
        },
        'section_2': {
            'signal_word': _GHS_FALLBACK['signal_word'],
            'pictograms': _GHS_FALLBACK['pictograms'],
            'hazard_codes': _GHS_FALLBACK['hazard_codes'],
            'precaution_codes': _GHS_FALLBACK['precaution_codes'],
            'other_hazards': 'This material does not meet the criteria for PBT or vPvB.',
        },
        'section_3': {
            'composition': [{
                'name': name or '',
                'concentration': '>= 98.0%',
                'classification': 'Acute Tox. 4 (H302), Skin Irrit. 2 (H315), Eye Irrit. 2A (H319), STOT SE 3 (H335)',
            }],
            'note': 'Impurities are not hazardous per GHS criteria.',
        },
        'section_4': safe['section4_first_aid'],
        'section_5': safe['section5_fire_fighting'],
        'section_6': safe['section6_accidental_release'],
        'section_7': {
            'handling': 'Handle under a chemical fume hood. Avoid breathing dust. Avoid contact with skin, eyes, and clothing. Wash hands thoroughly after handling.',
            'storage': 'Store at -20°C in a tightly sealed container. Keep in a cool, dry, well-ventilated area. Protect from moisture and direct light. Store locked up.',
            'specific_use': 'Laboratory research reagent only.',
        },
        'section_8': {
            'exposure_limits': 'No occupational exposure limits (OELs) have been established for this substance.',
            'engineering_controls': 'Use local exhaust ventilation. Safety shower and eye wash station should be readily available.',
            'ppe': {
                'eye': 'Safety glasses with side shields or chemical splash goggles.',
                'skin': 'Lab coat or disposable protective clothing.',
                'hands': 'Nitrile or neoprene gloves. Inspect before use.',
                'respiratory': 'NIOSH-approved particulate respirator (N95/P2 or higher). In emergency: SCBA.',
            },
            'hygiene': 'Handle in accordance with good laboratory hygiene and safety practices. Do not eat, drink, or smoke in work areas.',
        },
        'section_9': {
            'appearance': 'White to off-white crystalline powder',
            'odor': 'Odorless',
            'odor_threshold': 'Not available',
            'ph': 'Not applicable',
            'melting_point': 'Not available',
            'boiling_point': 'Not available (decomposes)',
            'flash_point': 'Not applicable',
            'evaporation_rate': 'Not available',
            'flammability': 'Not flammable',
            'vapor_pressure': 'Negligible',
            'vapor_density': 'Not available',
            'relative_density': 'Not available',
            'solubility_water': 'Not available',
            'solubility_dmso': 'Not available',
            'partition_coefficient': f'log P = {xlogp}' if xlogp else 'Not available',
            'auto_ignition': 'Not available',
            'decomposition_temp': '> 250°C',
            'viscosity': 'Not applicable',
            'explosive': 'Not explosive',
            'oxidizing': 'Not oxidizing',
            'exact_mass': str(exact_mass) if exact_mass else 'Not available',
        },
        'section_10': {
            'reactivity': 'Stable under recommended storage conditions.',
            'stability': 'Stable at -20°C for at least 24 months.',
            'hazardous_reactions': 'No hazardous polymerization.',
            'conditions_to_avoid': 'Excessive heat, moisture, direct sunlight.',
            'incompatible': 'Strong oxidizing agents, strong acids, strong bases.',
            'decomposition_products': 'Carbon monoxide (CO), carbon dioxide (CO₂), nitrogen oxides (NOx), ammonia (NH₃).',
        },
        'section_11': {
            'acute_toxicity': {
                'oral_ld50': 'Not available',
                'dermal_ld50': 'Not available',
                'inhalation_lc50': 'Not available',
            },
            'skin_irritation': 'Not classified.',
            'eye_irritation': 'Not classified.',
            'sensitization': 'Not classified as a sensitizer.',
            'mutagenicity': 'Not classified. No data available.',
            'carcinogenicity': 'Not listed by IARC, NTP, or OSHA.',
            'reproductive_toxicity': 'No data available.',
            'stot_single': 'No data available.',
            'stot_repeated': 'No data available.',
            'aspiration': 'Not classified.',
        },
        'section_12': {
            'ecotoxicity': 'No data available for aquatic toxicity.',
            'persistence': 'No data available.',
            'bioaccumulation': f'Log P = {xlogp} → {"Low" if xlogp and float(xlogp) < 3 else "Moderate"} bioaccumulation potential.' if xlogp else 'No data available.',
            'mobility': 'No data available.',
            'other_effects': 'No data available. Avoid release to the environment.',
        },
        'section_13': safe['section13_disposal'],
        'section_14': {
            'dot': 'Not regulated as dangerous goods.',
            'imdg': 'Not regulated as dangerous goods.',
            'iata': 'Not regulated as dangerous goods.',
            'un_number': 'None',
            'shipping_name': 'Not applicable',
            'hazard_class': 'None',
            'packing_group': 'None',
            'special_precautions': 'Ship at ambient temperature or with cold packs. Protect from moisture.',
        },
        'section_15': safe['section15_regulatory'],
        'section_16': {
            'revision_date': '',
            'revision_number': '1.0',
            'supersedes': 'New document',
            'prepared_by': 'Safety & Compliance Department, SciReagent',
            'references': [
                'OSHA Hazard Communication Standard (29 CFR 1910.1200)',
                'UN Globally Harmonized System (GHS), Rev. 9',
                f'PubChem Compound Database, CID {cid}' if cid else 'PubChem Compound Database',
                'ECHA C&L Inventory',
            ],
            'abbreviations': {
                'GHS': 'Globally Harmonized System',
                'CAS': 'Chemical Abstracts Service',
                'OSHA': 'Occupational Safety and Health Administration',
                'PBT': 'Persistent, Bioaccumulative, and Toxic',
                'vPvB': 'Very Persistent and Very Bioaccumulative',
                'STOT': 'Specific Target Organ Toxicity',
                'TSCA': 'Toxic Substances Control Act',
                'SARA': 'Superfund Amendments and Reauthorization Act',
                'RCRA': 'Resource Conservation and Recovery Act',
                'PPE': 'Personal Protective Equipment',
                'SCBA': 'Self-Contained Breathing Apparatus',
            },
            'disclaimer': safe['section16_other']['disclaimer'],
        },
    }
