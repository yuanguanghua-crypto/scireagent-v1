"""PubChem Data Enhancer Service

通过 pubchempy 封装 PubChem 查询能力，为产品提供：
- 完整分子属性（MW, LogP, TPSA, HBD, HBA, RotBonds）
- Lipinski 五规则检查
- Tanimoto 相似度搜索
- 产品名 → CAS/SMILES/Formula/MW 自动解析
- PubChem 官方结构图 URL
- ChEMBL REST API fallback（PubChem 查不到时自动尝试）
"""
import logging
from typing import Optional
import requests

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

    def _extract_properties_from_compound(self, c) -> dict:
        """从已获取的 pubchempy Compound 对象直接提取关键属性。

        避免二次 API 调用（get_full_properties 会重新查 PubChem，增加延迟和失败概率）。
        同时兼容 pubchempy 1.0.5 的字段变更（canonical_smiles → smiles）。
        """
        smiles = getattr(c, 'smiles', '') or getattr(c, 'connectivity_smiles', '') or ''
        return {
            'cid': c.cid,
            'molecular_formula': c.molecular_formula or '',
            'molecular_weight': c.molecular_weight or 0,
            'canonical_smiles': smiles,
            'isomeric_smiles': getattr(c, 'isomeric_smiles', None) or smiles,
            'iupac_name': c.iupac_name or '',
            'inchi': c.inchi or '',
            'inchikey': c.inchikey or '',
            'xlogp': getattr(c, 'xlogp', None),
            'tpsa': getattr(c, 'tpsa', None),
            'h_bond_donor_count': getattr(c, 'h_bond_donor_count', None),
            'h_bond_acceptor_count': getattr(c, 'h_bond_acceptor_count', None),
            'rotatable_bond_count': getattr(c, 'rotatable_bond_count', None),
            'complexity': getattr(c, 'complexity', None),
            'exact_mass': getattr(c, 'exact_mass', None),
            'monoisotopic_mass': getattr(c, 'monoisotopic_mass', None),
            'charge': getattr(c, 'charge', None),
            'heavy_atom_count': getattr(c, 'heavy_atom_count', None),
        }

    def _search_by_namespace(self, identifier: str, namespace: str = 'name') -> list:
        """按指定 namespace 搜索，返回 Compound 对象列表。

        支持的 namespace: name, smiles, inchi, inchikey, cid, formula
        name namespace 额外：substance fallback + 片段降级
        """
        results = pcp.get_compounds(identifier, namespace)
        if results:
            return list(results)
        # substance fallback
        if namespace in ('name', 'smiles', 'inchi'):
            try:
                cids = pcp.get_cids(identifier, namespace, 'substance', list_return='flat')
                if cids:
                    return [pcp.Compound.from_cid(cid) for cid in cids[:5]]
            except Exception:
                pass
        return []

    def _fallback_search_by_tokens(self, name: str) -> list:
        """name 的片段降级搜索。

        "Biotin-16-ddUTP" → 提取 "ddUTP" 搜索 → CID 72245。
        """
        import re
        tokens = re.split(r'[\s\-_,;]+', name.strip())
        skip = {'biotin', 'amino', 'dutp', 'utp', 'atp', 'gtp', 'ctp', 'dntp'}
        for token in tokens:
            if len(token) < 3 or token.lower() in skip:
                continue
            try:
                compounds = self._search_by_namespace(token, 'name')
                if compounds:
                    return compounds
            except Exception:
                continue
        return []

    def resolve_to_properties(self, identifier: str, namespace: str = 'name') -> dict:
        """按指定 namespace 搜索 PubChem → ChEMBL，解析化学属性。

        namespace: name / smiles / inchi / inchikey / cid
        PubChem 搜不到时自动尝试 ChEMBL REST API。
        属性从 Compound 对象直接提取，不二次调用 API。
        """
        if not self.available or not identifier:
            return {'error': 'pubchempy not available or empty identifier'}

        try:
            results = self._search_by_namespace(identifier, namespace)

            # name namespace 的片段降级
            fallback_used = False
            if not results and namespace == 'name':
                results = self._fallback_search_by_tokens(identifier)
                fallback_used = bool(results)

            # ── PubChem 搜不到 → ChEMBL fallback ──
            if not results:
                return self._chembl_search(identifier)

            # Multiple results → candidates list
            if len(results) > 1:
                candidates = []
                for c in results[:5]:
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
                    'namespace': namespace,
                    'candidates': candidates,
                    'fallback_used': fallback_used,
                }

            # Single result → extract properties directly
            c = results[0]
            cas = self._extract_cas_from_synonyms(c)
            properties = self._extract_properties_from_compound(c)

            return {
                'source': 'pubchem',
                'found': True,
                'namespace': namespace,
                'resolved_name': c.iupac_name or identifier,
                'cid': c.cid,
                'properties': properties,
                'cas_resolved': cas,
                'candidates': [],
                'fallback_used': fallback_used,
            }

        except Exception as e:
            logger.warning(f"Resolve failed for {identifier} ({namespace}): {e}")
            return {'error': str(e), 'found': False, 'namespace': namespace, 'candidates': []}

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

    # ── ChEMBL REST API Fallback ────────────────────────────

    CHEMBL_SEARCH_URL = "https://www.ebi.ac.uk/chembl/api/data/molecule/search"
    CHEMBL_TIMEOUT = 30  # seconds — ChEMBL 搜索端点响应慢，需要更长超时

    def _chembl_search(self, identifier: str) -> dict:
        """PubChem 搜不到时，用 ChEMBL REST API 作为 fallback。

        返回与 PubChem 统一 schema 的 dict。ChEMBL API 失败时返回 found: False。
        """
        try:
            params = {
                "q": identifier,
                "format": "json",
                "limit": 5,
            }
            resp = requests.get(
                self.CHEMBL_SEARCH_URL,
                params=params,
                timeout=self.CHEMBL_TIMEOUT,
            )
            if not resp.ok:
                return self._not_found(identifier)

            data = resp.json()
            molecules = data.get("molecules", [])

            if not molecules:
                return self._not_found(identifier)

            if len(molecules) > 1:
                # Multiple candidates
                candidates = []
                for mol in molecules[:5]:
                    props = mol.get("molecule_properties") or {}
                    structures = mol.get("molecule_structures") or {}
                    candidates.append({
                        "cid": mol.get("molecule_chembl_id", ""),
                        "iupac_name": mol.get("pref_name", ""),
                        "molecular_formula": props.get("full_molformula", ""),
                        "molecular_weight": props.get("full_mwt", 0),
                        "cas": "",  # ChEMBL doesn't always have CAS
                    })
                return {
                    "source": "chembl",
                    "found": True,
                    "namespace": "name",
                    "candidates": candidates,
                    "fallback_used": False,
                }

            # Single result
            mol = molecules[0]
            props = mol.get("molecule_properties") or {}
            structures = mol.get("molecule_structures") or {}
            chembl_id = mol.get("molecule_chembl_id", "")

            properties = {
                "cid": chembl_id,
                "molecular_formula": props.get("full_molformula", ""),
                "molecular_weight": props.get("full_mwt", 0),
                "canonical_smiles": structures.get("canonical_smiles", ""),
                "isomeric_smiles": structures.get("canonical_smiles", ""),
                "iupac_name": mol.get("pref_name", ""),
                "inchi": structures.get("standard_inchi", ""),
                "inchikey": structures.get("standard_inchi_key", ""),
                "xlogp": props.get("alogp"),
                "tpsa": props.get("psa"),
                "h_bond_donor_count": props.get("hbd"),
                "h_bond_acceptor_count": props.get("hba"),
                "rotatable_bond_count": props.get("rtb"),
                "complexity": None,
                "exact_mass": None,
                "monoisotopic_mass": None,
                "charge": props.get("full_molformula_charge"),
                "heavy_atom_count": props.get("heavy_atoms"),
            }

            return {
                "source": "chembl",
                "found": True,
                "namespace": "name",
                "resolved_name": mol.get("pref_name") or identifier,
                "cid": chembl_id,
                "properties": properties,
                "cas_resolved": structures.get("canonical_smiles"),  # will use SMILES as identity hint
                "candidates": [],
                "fallback_used": True,
                "search_note": "Not found in PubChem — results from ChEMBL",
            }

        except Exception as e:
            logger.warning(f"ChEMBL fallback failed for {identifier}: {e}")
            return self._not_found(identifier)

    def _not_found(self, identifier: str) -> dict:
        """统一未找到响应"""
        return {
            "source": "pubchem",
            "found": False,
            "namespace": "name",
            "candidates": [],
            "search_hint": (
                f'"{identifier}" not found in PubChem or ChEMBL. '
                "Try: (1) enter SMILES/FW manually, "
                "(2) check the compound name on pubchem.ncbi.nlm.nih.gov "
                "or ebi.ac.uk/chembl."
            ),
        }

    # ── RDKit 属性函数 ─────────────────────────────────────

    @staticmethod
    def canonicalize_smiles(smiles: str) -> str:
        """用 RDKit 标准化 SMILES 字符串。
        成功返回 canonical SMILES，失败返回空字符串。"""
        try:
            from rdkit import Chem
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                return ""
            return Chem.MolToSmiles(mol, canonical=True)
        except Exception:
            return ""

    @staticmethod
    def tanimoto_similarity(smiles1: str, smiles2: str) -> float:
        """计算两个 SMILES 之间的 Tanimoto 相似度（Morgan FP, radius=2）。
        失败返回 0.0。"""
        try:
            from rdkit import Chem
            from rdkit.Chem import DataStructs
            from rdkit.Chem.rdMolDescriptors import GetMorganFingerprintAsBitVect

            m1 = Chem.MolFromSmiles(smiles1)
            m2 = Chem.MolFromSmiles(smiles2)
            if m1 is None or m2 is None:
                return 0.0
            fp1 = GetMorganFingerprintAsBitVect(m1, 2)
            fp2 = GetMorganFingerprintAsBitVect(m2, 2)
            return DataStructs.TanimotoSimilarity(fp1, fp2)
        except Exception:
            return 0.0

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
