"""CAS 号标准化共享工具。

strip + 去 dash + upper，用于跨源化学等同性比对。
非 CAS 形态（如 SMILES、产品名）返回 None——这也用于规避
PubChemEnhancer ChEMBL fallback 把 SMILES 错塞进 cas_resolved 的坑
（pubchem_enhancer.py:454）。
"""
import re

_CAS_PATTERN = re.compile(r"^\s*(\d{2,7})-(\d{2})-(\d)\s*$")


def cas_normalize(raw) -> str | None:
    """CAS 标准化：通过形态校验后返回去 dash 大写形式；非 CAS 返回 None。

    '1927-31-7' → '1927317'
    ' 1927-31-7 ' → '1927317'
    'CC(=O)O' (SMILES) → None
    '' / None → None
    """
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None
    m = _CAS_PATTERN.match(s)
    if not m:
        return None
    # 形态通过即标准化（不做校验位重算——跨源比对只需确定性，不需校验位权威）
    return (m.group(1) + m.group(2) + m.group(3)).upper()


def is_cas_like(raw) -> bool:
    """快速判断字符串是否 CAS 形态（不标准化，仅布尔）。"""
    return _CAS_PATTERN.match(str(raw or "")) is not None
