"""PubChem Data Enhancer Service

通过 pubchempy 封装 PubChem 查询能力，为产品提供：
- 完整分子属性（MW, LogP, TPSA, HBD, HBA, RotBonds）
- Lipinski 五规则检查
- Tanimoto 相似度搜索
- 产品名 → CAS/SMILES/Formula/MW 自动解析
- PubChem 官方结构图 URL
"""
import logging
from typing import Optional

try:
    import pubchempy as pcp
    PUBCHEMPY_AVAILABLE = True
except ImportError:
    PUBCHEMPY_AVAILABLE = False
    pcp = None

logger = logging.getLogger(__name__)


class PubChemEnhancer:
    """PubChem 数据增强器"""

    def __init__(self):
        if not PUBCHEMPY_AVAILABLE:
            logger.warning("pubchempy not installed — PubChemEnhancer disabled")

    @property
    def available(self) -> bool:
        return PUBCHEMPY_AVAILABLE

    # ── 完整分子属性 ────────────────────────────────────

    def get_full_properties(self, identifier: str, namespace: str = 'name') -> Optional[dict]:
        """通过 CAS 号或产品名获取完整分子属性"""
        if not self.available:
            return None
        try:
            compounds = pcp.get_compounds(identifier, namespace)
            if not compounds:
                return None
            c = compounds[0]
            properties = {
                'cid': c.cid,
                'molecular_formula': c.molecular_formula or '',
                'molecular_weight': c.molecular_weight or 0,
                'canonical_smiles': getattr(c, 'smiles', '') or getattr(c, 'connectivity_smiles', '') or '',
                'isomeric_smiles': getattr(c, 'smiles', None) or getattr(c, 'isomeric_smiles', None) or '',
                'iupac_name': c.iupac_name or '',
                'inchi': c.inchi or '',
                'inchikey': c.inchikey or '',
                'xlogp': c.xlogp,
                'tpsa': c.tpsa,
                'h_bond_donor_count': c.h_bond_donor_count,
                'h_bond_acceptor_count': c.h_bond_acceptor_count,
                'rotatable_bond_count': c.rotatable_bond_count,
                'complexity': c.complexity,
                'exact_mass': c.exact_mass,
                'monoisotopic_mass': c.monoisotopic_mass,
                'charge': c.charge,
                'heavy_atom_count': c.heavy_atom_count,
            }
            return properties
        except Exception as e:
            logger.warning(f"PubChem property lookup failed for {identifier}: {e}")
            return None

    def _get_field_safe(self, compound, field_name):
        """安全获取 compound 属性，避免 pubchempy 1.0.5 的 deprecation 问题。"""
        val = getattr(compound, field_name, None)
        if val is None and field_name == 'canonical_smiles':
            val = getattr(compound, 'smiles', None) or getattr(compound, 'connectivity_smiles', None)
        return val if val else ''

    # ── Lipinski 五规则 ──────────────────────────────────

    def check_lipinski(self, properties: dict) -> dict:
        """Lipinski 五规则检查

        规则:
          1. Molecular Weight ≤ 500
          2. LogP ≤ 5
          3. H-Bond Donor ≤ 5
          4. H-Bond Acceptor ≤ 10
          5. Rotatable Bonds ≤ 10
        """
        if not properties:
            return {'passed': False, 'violations': ['No properties available'], 'details': {}}

        mw = properties.get('molecular_weight') or 0
        logp = properties.get('xlogp')
        hbd = properties.get('h_bond_donor_count')
        hba = properties.get('h_bond_acceptor_count')
        rot = properties.get('rotatable_bond_count')

        violations = []
        details = {}

        details['mw_ok'] = float(mw) <= 500
        if not details['mw_ok']:
            violations.append(f'Molecular weight {mw} > 500')

        if logp is not None:
            details['logp_ok'] = float(logp) <= 5
            if not details['logp_ok']:
                violations.append(f'LogP {logp} > 5')
        else:
            details['logp_ok'] = None  # unknown

        if hbd is not None:
            details['hbd_ok'] = int(hbd) <= 5
            if not details['hbd_ok']:
                violations.append(f'H-bond donors {hbd} > 5')
        else:
            details['hbd_ok'] = None

        if hba is not None:
            details['hba_ok'] = int(hba) <= 10
            if not details['hba_ok']:
                violations.append(f'H-bond acceptors {hba} > 10')
        else:
            details['hba_ok'] = None

        if rot is not None:
            details['rot_ok'] = int(rot) <= 10
            if not details['rot_ok']:
                violations.append(f'Rotatable bonds {rot} > 10')
        else:
            details['rot_ok'] = None

        return {
            'passed': len(violations) == 0,
            'violations': violations,
            'details': details,
        }

    # ── 相似度搜索 ──────────────────────────────────────

    def find_similar(self, smiles: str, threshold: int = 85, max_results: int = 5) -> list:
        """Tanimoto 相似度搜索 — 返回相似化合物的基本信息"""
        if not self.available or not smiles:
            return []
        try:
            results = pcp.get_compounds(
                smiles,
                'smiles',
                searchtype='similarity',
                Threshold=threshold,
                MaxRecords=max_results,
            )
            similar = []
            for c in results:
                similar.append({
                    'cid': c.cid,
                    'iupac_name': c.iupac_name or '',
                    'molecular_formula': c.molecular_formula or '',
                    'molecular_weight': c.molecular_weight or 0,
                    'canonical_smiles': getattr(c, 'smiles', '') or getattr(c, 'connectivity_smiles', '') or '',
                })
            return similar
        except Exception as e:
            logger.warning(f"Similarity search failed for SMILES: {e}")
            return []

    # ── 产品名 → 属性解析（自动补全）──────────────────────

    def resolve_to_properties(self, name: str) -> dict:
        """从产品名解析化学属性，用于自动补全表单"""
        if not self.available or not name:
            return {'error': 'pubchempy not available or empty name'}

        try:
            results = pcp.get_compounds(name, 'name')
            if not results:
                # Try substance-based lookup as fallback
                try:
                    cids = pcp.get_cids(name, 'name', 'substance', list_return='flat')
                    if cids:
                        compounds = [pcp.Compound.from_cid(cid) for cid in cids[:5]]
                        results = compounds
                except Exception:
                    pass

            if not results:
                return {
                    'source': 'pubchem',
                    'found': False,
                    'candidates': [],
                }

            # If multiple results, return as candidates
            if len(results) > 1:
                candidates = []
                for c in results[:5]:
                    # Try to extract CAS from synonyms
                    cas = self._extract_cas_from_synonyms(c)
                    candidates.append({
                        'cid': c.cid,
                        'iupac_name': c.iupac_name or '',
                        'molecular_formula': c.molecular_formula or '',
                        'molecular_weight': c.molecular_weight or 0,
                        'cas': cas,
                    })
                return {
                    'source': 'pubchem',
                    'found': True,
                    'candidates': candidates,
                }

            # Single result
            c = results[0]
            cas = self._extract_cas_from_synonyms(c)
            properties = self.get_full_properties(str(c.cid), 'cid')

            return {
                'source': 'pubchem',
                'found': True,
                'resolved_name': c.iupac_name or name,
                'cid': c.cid,
                'properties': properties or {},
                'cas_resolved': cas,
                'candidates': [],
            }

        except Exception as e:
            logger.warning(f"Resolve failed for {name}: {e}")
            return {'error': str(e), 'found': False, 'candidates': []}

    def _extract_cas_from_synonyms(self, compound) -> Optional[str]:
        """从 PubChem 的同义词列表中提取 CAS 号"""
        try:
            import re
            if not compound.synonyms:
                return None
            for syn in compound.synonyms:
                match = re.match(r'^(\d{2,7}-\d{2}-\d)$', syn.strip())
                if match:
                    return match.group(1)
        except Exception:
            pass
        return None

    # ── PubChem 结构图 URL ───────────────────────────────

    @staticmethod
    def get_structure_image_url(identifier: str, namespace: str = 'name',
                                 image_format: str = 'PNG',
                                 image_size: str = '300x300') -> str:
        """返回 PubChem 官方结构图 URL

        支持的 namespace: 'cid', 'name', 'smiles', 'inchi', 'inchikey'
        支持格式: 'PNG', 'SVG'
        """
        ns_map = {'cid': 'cid', 'name': 'name', 'smiles': 'smiles',
                   'inchi': 'inchi', 'inchikey': 'inchikey'}
        ns = ns_map.get(namespace, 'name')
        encoded = identifier.replace('#', '%23')
        return (f'https://pubchem.ncbi.nlm.nih.gov/rest/pug/'
                f'compound/{ns}/{encoded}/{image_format}'
                f'?image_size={image_size}')
