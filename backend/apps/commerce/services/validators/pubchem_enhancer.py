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
import re
from typing import Optional

from django.core.cache import cache

from core.datasource_client import get_bucket, request_with_resilience
from apps.documents.services.datasource_cache import get_cache, set_cache

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
            get_bucket("pubchem").acquire()
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
            get_bucket("pubchem").acquire()
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
            'synonyms': [s for s in (c.synonyms or [])][:20],
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

    # ── 身份校验 / 交叉校验（防错核心，修复 1/3/4）─────────────────────────
    #
    # 设计原则（用户要求：不能留任何侥幸）：
    #   1) 凡是有 CAS / SMILES / InChI 等可核验标识的查询，必须验证返回化合物
    #      与输入是「同一个分子」才接受；否则一律视为未匹配，绝不当作真值。
    #   2) 仅靠产品名模糊搜索（无 CAS）的结果无法强验证，绝不静默自动套用，
    #      一律降级为 candidates 让用户显式选择。
    #   3) ChEMBL / 片段降级命中同样强制用户选择，不自动采用第一个。
    #   4) 缓存只对「已验证的单结果」生效，避免错误结果被 30 天固化复用。

    @staticmethod
    def _normalize_cas(cas):
        if not cas:
            return ''
        return re.sub(r'\s+', '', str(cas).strip()).upper()

    def _compound_cas_set(self, compound) -> set:
        """提取 PubChem 化合物同义词列表中所有合法 CAS 号（归一化）。"""
        out = set()
        try:
            for syn in (compound.synonyms or []):
                m = re.match(r'^(\d{2,7}-\d{2}-\d)$', str(syn).strip())
                if m:
                    out.add(self._normalize_cas(m.group(1)))
        except Exception:
            pass
        return out

    def _structurally_equal(self, identifier, namespace, compound):
        """结构等价判定：SMILES/InChI/InChIKey 输入时比对 InChIKey。

        Returns: True（等价）/ False（不等价）/ None（无法判定，如 rdkit 不可用）。
        """
        try:
            from rdkit import Chem
        except Exception:
            return None
        try:
            if namespace == 'smiles':
                a = Chem.MolFromSmiles(identifier)
                b_smiles = getattr(compound, 'smiles', '') or getattr(compound, 'canonical_smiles', '') or ''
                b = Chem.MolFromSmiles(b_smiles)
                if a is None or b is None:
                    return None
                return Chem.MolToInchiKey(a) == Chem.MolToInchiKey(b)
            if namespace in ('inchi', 'inchikey'):
                inp = identifier.strip().upper()
                ck = (getattr(compound, 'inchikey', '') or '').upper()
                if ck and ck == inp:
                    return True
                ci = (getattr(compound, 'inchi', '') or '').strip()
                if ci and ci.split('=')[0].upper() == inp.split('=')[0].upper():
                    return True
                return False if (ck or ci) else None
        except Exception:
            return None
        return None

    def _validate_identity(self, identifier, namespace, compound, expected_cas=None):
        """返回 (verified: bool, confidence: str)。

        verified=True 仅当存在可核验证明返回化合物与输入是同一分子：
          - 提供了 CAS（输入或 expected_cas）：化合物同义词必须包含该 CAS；
          - SMILES/InChI/InChIKey：InChIKey 结构等价。
        否则（仅靠名称模糊搜索、无 CAS）=> 未验证。
        confidence: 'verified' | 'rejected' | 'unverified'。
        """
        norm_expected = self._normalize_cas(expected_cas)
        if norm_expected:
            if norm_expected in self._compound_cas_set(compound):
                return True, 'verified'
            # 给了 CAS 但返回化合物不含该 CAS → 拒绝（不是同一个分子）
            return False, 'rejected'
        if namespace in ('smiles', 'inchi', 'inchikey'):
            eq = self._structurally_equal(identifier, namespace, compound)
            if eq is True:
                return True, 'verified'
            if eq is False:
                return False, 'rejected'
            return False, 'unverified'
        # name namespace 且无 CAS → 无法强验证
        return False, 'unverified'

    @staticmethod
    def _norm_formula(f):
        """归一化分子式：去括号注释（如 "(free acid)"）、去空白、大写。"""
        if not f:
            return ''
        s = re.sub(r'\([^)]*\)', '', str(f))
        return re.sub(r'\s+', '', s).upper()

    def _cross_check(self, expected_formula, expected_mw, compound):
        """将返回化合物与文档已提供的 formula/MW 比对。

        Returns: {formula_mismatch, mw_mismatch, doc_value_mismatch}
        doc_value_mismatch=True 表示文档值与权威库值矛盾（提示用户核对文档是否有误）。
        """
        res = {'formula_mismatch': False, 'mw_mismatch': False, 'doc_value_mismatch': False}
        cf = self._norm_formula(expected_formula)
        if cf:
            rf = self._norm_formula(getattr(compound, 'molecular_formula', '') or '')
            if cf and rf and cf != rf:
                res['formula_mismatch'] = True
                res['doc_value_mismatch'] = True
        try:
            emw = float(expected_mw) if expected_mw not in (None, '') else None
        except (TypeError, ValueError):
            emw = None
        if emw is not None:
            try:
                rmw = float(getattr(compound, 'molecular_weight', 0) or 0)
            except (TypeError, ValueError):
                rmw = None
            if rmw is not None and abs(rmw - emw) > 1.0:  # 容差 1.0 Da
                res['mw_mismatch'] = True
                res['doc_value_mismatch'] = True
        return res

    # ── cache-aside 缓存配置 ──────────────────────────────────────────────
    # 命中结果缓存 30 天（分子结构稳定）；not-found/error 不缓存（避免临时故障被长期缓存）
    # 详见 docs/DATASOURCE_RELIABILITY.md §5
    PUBCHEM_CACHE_TTL_FOUND = 60 * 60 * 24 * 30  # 30 天

    def resolve_to_properties(self, identifier: str, namespace: str = 'name',
                               expected_cas: str = None, expected_formula: str = None,
                               expected_mw=None) -> dict:
        """按 namespace 解析化学属性（带 cache-aside 缓存）。

        同一 (namespace, identifier, expected_cas) 的结果缓存 30 天。
        not-found / error / 未验证 / 候选 不缓存（避免错误被长期复用 — 修复 5）。
        缓存层是 best-effort 加速层：任何序列化/连接异常都不影响主流程。
        """
        if not self.available or not identifier:
            return {'error': 'pubchempy not available or empty identifier'}

        # #473-A1 / #475：缓存键纳入文档 formula/MW（ctx），避免同名但文档公式/MW 不同的
        # 两个产品复用同一缓存槽、错配 formula_mismatch/mw_mismatch 状态（跨文档污染，
        # 违反铁律①：文档值不符绝不自动套用）。L1 同键改造见下方 get/set_cache。
        ctx = f"{expected_formula or ''}|{expected_mw or ''}"
        cache_key = f'pubchem:resolve:{namespace}:{identifier}:{expected_cas or ""}:{ctx}'
        try:
            cached = cache.get(cache_key)
        except Exception:
            cached = None
        # 仅信任「带 identity_verified 标记」的新格式缓存；旧格式（修复前）一律重查
        if cached is not None and cached.get('identity_verified') is not None:
            return cached

        l1_entry = get_cache("pubchem", f"{identifier}{ctx}", namespace)
        if l1_entry:
            data = l1_entry.get_data()
            # 旧格式缓存缺 identity_verified 标记 → 视为失效，强制重新解析校验
            if data is not None and data.get('found') and not l1_entry.is_stale \
                    and data.get('identity_verified') is not None:
                return data

        result = self._resolve_to_properties_impl(
            identifier, namespace,
            expected_cas=expected_cas, expected_formula=expected_formula,
            expected_mw=expected_mw)

        # 只缓存「已验证的单结果」（identity_verified 且无候选 / 无不一致）— 修复 5
        cacheable = (
            isinstance(result, dict)
            and result.get('found')
            and result.get('identity_verified')
            and not result.get('requires_review')
            and not result.get('candidates')
            and not result.get('formula_mismatch')
            and not result.get('mw_mismatch')
        )
        if cacheable:
            try:
                cache.set(cache_key, result, self.PUBCHEM_CACHE_TTL_FOUND)
            except Exception as e:
                logger.debug(f"PubChem cache set skipped for {cache_key}: {e}")
            set_cache("pubchem", f"{identifier}{ctx}", namespace, result, ttl_seconds=self.PUBCHEM_CACHE_TTL_FOUND)
        return result

    def _resolve_to_properties_impl(self, identifier: str, namespace: str = 'name',
                                 expected_cas=None, expected_formula=None,
                                 expected_mw=None) -> dict:
        """按指定 namespace 搜索 PubChem → ChEMBL，解析化学属性（无缓存实现）。

        namespace: name / smiles / inchi / inchikey / cid
        PubChem 搜不到时自动尝试 ChEMBL REST API。
        属性从 Compound 对象直接提取，不二次调用 API。

        防错逻辑（修复 1/3/4）：
          - 单结果必做身份校验；CAS/结构不等价则拒绝，绝不自动套用。
          - 仅靠名称模糊搜索（无 CAS）的结果无法强验证 → 降级为 candidates 强制用户选择。
          - ChEMBL / 片段降级命中同样进 candidates，不自动采用第一个。
        """
        if not self.available or not identifier:
            return {'error': 'pubchempy not available or empty identifier'}

        try:
            get_bucket("pubchem").acquire()
            results = self._search_by_namespace(identifier, namespace)

            # name namespace 的片段降级
            fallback_used = False
            if not results and namespace == 'name':
                results = self._fallback_search_by_tokens(identifier)
                fallback_used = bool(results)

            # ── PubChem / 片段降级都没命中 → ChEMBL fallback（强制候选）──
            if not results:
                return self._chembl_search(identifier)

            # Multiple results → candidates（强制用户选择）
            if len(results) > 1:
                candidates = []
                for c in results[:5]:
                    candidates.append(self._build_candidate(
                        c, requires_review=True, confidence='multiple'))
                return {
                    'source': 'pubchem',
                    'found': True,
                    'namespace': namespace,
                    'candidates': candidates,
                    'fallback_used': fallback_used,
                    'identity_verified': False,
                    'requires_review': True,
                    'confidence': 'multiple',
                    'search_hint': 'Multiple PubChem hits — select the correct compound',
                }

            # Single result → 身份校验
            c = results[0]
            verified, confidence = self._validate_identity(identifier, namespace, c, expected_cas)
            cross = self._cross_check(expected_formula, expected_mw, c)

            # 身份(CAS)通过但分子式/MW 与文档(权威)不符 → 视为错误化合物，
            # 降级为需人工核实，绝不自动套用（任务2(b)：根治 PubChem 模糊匹配到错误分子）。
            if verified and (cross['formula_mismatch'] or cross['mw_mismatch']):
                verified = False
                confidence = 'formula_mismatch'

            if confidence == 'rejected':
                # 返回化合物与输入身份（CAS/结构）不符 → 拒绝，绝不套用
                return {
                    'source': 'pubchem',
                    'found': True,
                    'namespace': namespace,
                    'candidates': [],
                    'fallback_used': fallback_used,
                    'identity_verified': False,
                    'requires_review': True,
                    'confidence': 'rejected',
                    'search_hint': (
                        f'PubChem returned a compound whose CAS/structure does not match '
                        f'the input ({expected_cas or identifier}). Not applied automatically — '
                        'enter SMILES/CAS manually or pick a candidate.'
                    ),
                }

            if verified:
                properties = self._extract_properties_from_compound(c)
                return {
                    'source': 'pubchem',
                    'found': True,
                    'namespace': namespace,
                    'resolved_name': c.iupac_name or identifier,
                    'cid': c.cid,
                    'properties': properties,
                    'cas_resolved': self._extract_cas_from_synonyms(c),
                    'candidates': [],
                    'fallback_used': fallback_used,
                    'identity_verified': True,
                    'requires_review': False,
                    'confidence': 'verified',
                    'formula_mismatch': cross['formula_mismatch'],
                    'mw_mismatch': cross['mw_mismatch'],
                    'doc_value_mismatch': cross['doc_value_mismatch'],
                }

            # 仅靠名称模糊搜索（无 CAS）且无法强验证 → 强制用户显式选择
            properties = self._extract_properties_from_compound(c)
            return {
                'source': 'pubchem',
                'found': True,
                'namespace': namespace,
                'resolved_name': c.iupac_name or identifier,
                'cid': c.cid,
                'properties': properties,
                'cas_resolved': self._extract_cas_from_synonyms(c),
                'candidates': [self._build_candidate(
                    c, cross=cross, confidence='unverified', requires_review=True)],
                'fallback_used': fallback_used,
                'identity_verified': False,
                'requires_review': True,
                'confidence': 'unverified',
                'formula_mismatch': cross['formula_mismatch'],
                'mw_mismatch': cross['mw_mismatch'],
                'doc_value_mismatch': cross['doc_value_mismatch'],
                'search_hint': (
                    'Matched by name only (no CAS to verify). Please confirm this is the '
                    'correct compound before applying.'
                ),
            }

        except Exception as e:
            logger.warning(f"Resolve failed for {identifier} ({namespace}): {e}")
            return {'error': str(e), 'found': False, 'namespace': namespace, 'candidates': []}

    def _build_candidate(self, c, cross=None, confidence=None, requires_review=None) -> dict:
        """构造候选化合物条目（供前端显式选择）。

        携带守卫标志（formula_mismatch / mw_mismatch / requires_review / confidence），
        供前端 applyCandidate 据此拦截错误分子（任务2(b)）。
        """
        return {
            'cid': c.cid,
            'iupac_name': c.iupac_name or '',
            'molecular_formula': c.molecular_formula or '',
            'molecular_weight': c.molecular_weight or 0,
            'cas': self._extract_cas_from_synonyms(c),
            'canonical_smiles': getattr(c, 'smiles', '') or getattr(c, 'canonical_smiles', '') or '',
            'inchi': getattr(c, 'inchi', '') or '',
            'formula_mismatch': bool(cross['formula_mismatch']) if cross else False,
            'mw_mismatch': bool(cross['mw_mismatch']) if cross else False,
            'requires_review': bool(requires_review) if requires_review is not None else False,
            'confidence': confidence or '',
        }

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
            resp = request_with_resilience(
                "GET",
                self.CHEMBL_SEARCH_URL,
                source="chembl",
                timeout=self.CHEMBL_TIMEOUT,
                params=params,
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
                        "cas": "",
                        "canonical_smiles": structures.get("canonical_smiles", ""),
                        "inchi": structures.get("standard_inchi", ""),
                    })
                return {
                    "source": "chembl",
                    "found": True,
                    "namespace": "name",
                    "candidates": candidates,
                    "fallback_used": False,
                    "identity_verified": False,
                    "requires_review": True,
                    "confidence": "chembl_unverified",
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
                "synonyms": [],
            }

            candidate = {
                "cid": chembl_id,
                "iupac_name": mol.get("pref_name") or "",
                "molecular_formula": props.get("full_molformula", ""),
                "molecular_weight": props.get("full_mwt", 0),
                "cas": "",
                "canonical_smiles": structures.get("canonical_smiles", ""),
                "inchi": structures.get("standard_inchi", ""),
            }
            return {
                "source": "chembl",
                "found": True,
                "namespace": "name",
                "resolved_name": mol.get("pref_name") or identifier,
                "cid": chembl_id,
                "properties": properties,
                "cas_resolved": None,  # ChEMBL 无 CAS 数据
                "candidates": [candidate],
                "fallback_used": True,
                "identity_verified": False,
                "requires_review": True,
                "confidence": "chembl_unverified",
                "search_note": "Not found in PubChem — results from ChEMBL (unverified, please confirm)",
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
