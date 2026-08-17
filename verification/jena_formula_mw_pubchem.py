#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""step2：用 PubChem 收口 step1 的 14 条 formula↔MW「待确认」记录。

设计（与用户确认）：
- step1 的离线解析器不会处理括号分组 / 结构式注释（如 `C50H60N6O21P2S4 (free acid)`、
  结构式 `CH3CH(OH)CH 2 C(CH 3 ) 2 OH`），会把这类算成 MW=0 或错值而误报 mismatch。
- 本脚本用「正确公式解析器」复算，再用 PubChem（CAS > systematic_name > product_name）
  取权威 formula / MW / InChIKey 逐项裁定，给出每条的确定性 verdict。
- 同时全量复扫 2098 条，给出「真正的 formula↔MW 矛盾」总条数，完成对 step1 指标的收口。

输出：
  verification/jena_formula_mw_pubchem.md   人类可读裁定报告
  verification/jena_formula_mw_pubchem.csv  逐条裁定（供筛选）
"""
import json
import re
import os
import csv
import time
import urllib.request
import urllib.parse
from collections import defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSONL = os.path.join(REPO, "backend", "data", "jena", "jena_products_v2.jsonl")
CSV_14 = os.path.join(REPO, "verification", "jena_intrinsic_report.csv")
OUT_MD = os.path.join(REPO, "verification", "jena_formula_mw_pubchem.md")
OUT_CSV = os.path.join(REPO, "verification", "jena_formula_mw_pubchem.csv")
STATE = os.path.join(REPO, "verification", "jena_formula_mw_pubchem.state.json")

ATOMIC = {
    'H': 1.008, 'C': 12.011, 'N': 14.007, 'O': 15.999, 'P': 30.974, 'S': 32.06,
    'F': 18.998, 'Cl': 35.45, 'Br': 79.904, 'I': 126.90, 'Na': 22.990, 'K': 39.098,
    'Mg': 24.305, 'Ca': 40.078, 'Fe': 55.845, 'Zn': 65.38, 'Cu': 63.546, 'B': 10.81,
    'Si': 28.085, 'Li': 6.94, 'Mn': 54.938, 'Co': 58.933, 'Ni': 58.693, 'Se': 78.96,
    'As': 74.922, 'Mo': 95.95, 'Au': 196.97, 'Ag': 107.87, 'Pt': 195.08, 'Ru': 101.07,
    'Rh': 102.91, 'Ir': 192.22, 'Ti': 47.867, 'V': 50.942, 'Cr': 51.996, 'Al': 26.982,
    'Ba': 137.33, 'Pb': 207.2, 'Hg': 200.59, 'Cd': 112.41, 'Be': 9.012, 'Te': 127.60,
}
ELEM_RE = re.compile(r'([A-Z][a-z]?)(\d*)')


# ── 正确公式解析器（括号分组 + 剥离注释括号）────────────────────────────
def _parse_grouped(s):
    """递归式括号分组解析。s 已去空格、无水合物点、无聚合物 n。返回元素计数 dict 或 None。"""
    stack = [{}]
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c == '(':
            stack.append({})
            i += 1
            continue
        if c == ')':
            j = i + 1
            num = ''
            while j < n and s[j].isdigit():
                num += s[j]
                j += 1
            mult = int(num) if num else 1
            top = stack.pop()
            base = stack[-1]
            for el, cnt in top.items():
                base[el] = base.get(el, 0) + cnt * mult
            i = j
            continue
        m = ELEM_RE.match(s, i)
        if not m:
            return None
        el = m.group(1)
        cnt = int(m.group(2) or 1)
        i = m.end()
        if el not in ATOMIC:
            return None
        stack[-1][el] = stack[-1].get(el, 0) + cnt
    return stack[0] if stack and stack[0] else None


def parse_formula_strict(formula):
    """剥离 (free acid)/(sodium salt) 类注释括号，正确解析结构式括号与 *nH2O / ·nH2O 水合物。

    返回元素计数 dict 或 None（含聚合物 n / 无法解析的字符）。
    """
    if not isinstance(formula, str) or not formula.strip():
        return None
    s = formula.replace(' ', '')
    if 'n' in s or 'x' in s:
        return None  # 聚合物，无法静态计算
    # 以 * 或 · 作为水合物/加合物分隔符分段解析（如 MgSO4*7H2O → MgSO4 + 7×H2O）
    total = {}
    for seg in re.split(r'[*·]', s):
        m = re.match(r'^(\d+)(.*)$', seg)  # 段首整数系数（如 "7H2O"）
        mult = 1
        if m:
            mult = int(m.group(1))
            seg = m.group(2)
        if not seg:
            continue
        # 剥离「注释括号」：内部若能被解析为合法元素分组则保留（真括号），否则视为注释删除
        seg2 = re.sub(
            r'\(([^()]*)\)',
            lambda mm: mm.group(0) if _parse_grouped(mm.group(1)) is not None else '',
            seg,
        )
        d = _parse_grouped(seg2)
        if d is None:
            return None
        for el, cnt in d.items():
            total[el] = total.get(el, 0) + cnt * mult
    return total if total else None


def mw_of(d):
    return sum(ATOMIC[e] * c for e, c in d.items())


def hill(d):
    parts = []
    if 'C' in d:
        parts.append(f"C{d['C']}")
        if 'H' in d:
            parts.append(f"H{d['H']}")
    for el in sorted(d):
        if el in ('C', 'H'):
            continue
        parts.append(f"{el}{d[el]}")
    return ''.join(parts)


def tol_for(mw):
    return max(5.0, 0.05 * mw)


# ── PubChem PUG-REST ──────────────────────────────────────────────────
def _http_get_json(url, timeout=25):
    req = urllib.request.Request(url, headers={'User-Agent': 'jena-verify/1.0'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def query_pubchem(anchor):
    """返回 dict(formula,mw,inchikey) 或 None(404 未收录)；网络瞬断抛异常交由重试。"""
    base = 'https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/'
    props = 'MolecularFormula,MolecularWeight,InChIKey'
    q = urllib.parse.quote(anchor)
    url = f'{base}{q}/property/{props}/JSON'
    try:
        d = _http_get_json(url)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    props_tbl = d.get('PropertyTable', {}).get('Properties')
    if not props_tbl:
        return None
    p = props_tbl[0]
    return {
        'formula': p.get('MolecularFormula'),
        'mw': p.get('MolecularWeight'),
        'inchikey': p.get('InChIKey'),
    }


def query_pubchem_with_fallback(anchor):
    """先整串查，404 则尝试去掉逗号后盐注释再查。返回 (result, used_anchor)。"""
    try:
        r = query_pubchem(anchor)
        if r is not None:
            return r, anchor
    except Exception:
        raise  # 网络错，交给上层退避
    # 404 → 去掉逗号后的盐/形式注释再试
    if ',' in anchor:
        cleaned = anchor.split(',')[0].strip()
        if cleaned and cleaned != anchor:
            r2 = query_pubchem(cleaned)
            if r2 is not None:
                return r2, cleaned
    return None, anchor


def best_anchor(rec):
    cas = (rec.get('cas_number') or '').strip()
    if re.match(r'^\d{2,7}-\d{2}-\d$', cas):
        return ('cas', cas)
    nm = (rec.get('systematic_name') or '').strip().strip('"').strip("'")
    if nm:
        return ('name', nm)
    pn = (rec.get('product_name') or '').strip()
    if pn:
        return ('name', pn)
    return (None, None)


def pubchem_with_retry(anchor, max_tries=4):
    """指数退避重试（应对 VPN 不稳 / 限频）。全部失败抛 RuntimeError。"""
    last = None
    for attempt in range(1, max_tries + 1):
        try:
            return query_pubchem_with_fallback(anchor)
        except Exception as e:  # 网络/超时
            last = e
            if attempt < max_tries:
                time.sleep(2 ** attempt)  # 2,4,8
    raise RuntimeError(f'pubchem retry exhausted: {type(last).__name__} {last}')


# ── 主流程 ────────────────────────────────────────────────────────────
def load_jsonl():
    recs = []
    with open(JSONL, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def find_14_catalogs():
    cats = []
    with open(CSV_14, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if row['issue'] == 'mw:mw_formula_mismatch' and row['tier'] == 'deferred':
                cats.append(row['catalog_no'])
    return cats


def adjudicate(rec, pc):
    """pc = PubChem dict 或 None。返回 (verdict, note)。"""
    jf = rec.get('molecular_formula')
    jmw_raw = rec.get('molecular_weight')
    try:
        jmw = float(str(jmw_raw).strip())
    except Exception:
        jmw = None
    d = parse_formula_strict(jf)
    calc = mw_of(d) if d else None
    self_ok = (calc is not None and jmw is not None and abs(calc - jmw) <= tol_for(calc))

    if pc is None:
        if self_ok:
            return ('FALSE_POSITIVE',
                    f'正确解析器复算自洽(calc={calc:.2f}≈stored={jmw:.2f})；PubChem 未收录→step1 解析器误报')
        return ('GENUINE_INTERNAL_CONTRADICTION',
                f'正确解析器仍矛盾(calc={calc:.2f} vs stored={jmw:.2f})；PubChem 未收录(多为专有染料/标记物)→需依 source_url 厂商 datasheet 人工核对')
    pc_mw = pc.get('mw')
    pc_formula = pc.get('formula')
    try:
        pc_mwf = float(str(pc_mw).strip())
    except Exception:
        pc_mwf = None
    pc_hill = hill(parse_formula_strict(pc_formula)) if pc_formula else None
    j_hill = hill(d) if d else None

    mw_match_pc = (pc_mwf is not None and jmw is not None and abs(jmw - pc_mwf) <= tol_for(pc_mwf))
    formula_match = (pc_hill is not None and j_hill is not None and pc_hill == j_hill)

    if self_ok and mw_match_pc:
        return ('OK_CONFIRMED',
                f'PubChem 确认 jena MW 正确(formula={pc_formula}, MW={pc_mwf:.2f})；step1 系解析器误报')
    if (not self_ok) and mw_match_pc and formula_match:
        return ('JENA_FORMULA_FORMAT_ONLY',
                f'jena MW 与 PubChem 一致({jmw:.2f}≈{pc_mwf:.2f})，但 jena 公式写法(结构式/注释)非 Hill；值正确')
    if (not self_ok) and mw_match_pc and (not formula_match):
        return ('JENA_FORMULA_WRONG',
                f'jena MW 与 PubChem 一致({jmw:.2f}≈{pc_mwf:.2f})，但 jena 公式({j_hill})≠PubChem({pc_hill})→公式字段错')
    if self_ok and (not mw_match_pc):
        return ('MW_DISCREPANCY',
                f'jena 公式自洽(calc={calc:.2f})但与 PubChem MW({pc_mwf:.2f})不符→可能异构体/盐型差异，需人工核对')
    return ('BOTH_DIFFER',
            f'jena 公式与 MW 均与 PubChem 不符(formula {j_hill} vs {pc_hill}; MW {jmw:.2f} vs {pc_mwf:.2f})→jena 错误概率高')


def main():
    recs = load_jsonl()
    by_cat = {r.get('jena_catalog_no'): r for r in recs}
    target = find_14_catalogs()
    print(f'[load] jsonl={len(recs)} target14={len(target)}')

    # 全量复扫：用正确解析器统计真正的 formula↔MW 矛盾总数（收口 step1 的「14」指标）
    genuine_all = []
    for r in recs:
        f = r.get('molecular_formula')
        mw = r.get('molecular_weight')
        if not isinstance(mw, (int, float)) and not (isinstance(mw, str) and mw.strip()):
            continue
        try:
            smw = float(str(mw).strip())
        except Exception:
            continue
        d = parse_formula_strict(f)
        if d is None:
            continue
        c = mw_of(d)
        if abs(c - smw) > tol_for(c):
            genuine_all.append(r.get('jena_catalog_no'))
    print(f'[rescan] 正确解析器下全量真正 formula↔MW 矛盾 = {len(genuine_all)} 条')

    # 断点续跑
    state = {}
    if os.path.exists(STATE):
        try:
            state = json.load(open(STATE, encoding='utf-8'))
        except Exception:
            state = {}

    rows = []
    summary = defaultdict(int)
    for cat in target:
        rec = by_cat.get(cat)
        if cat in state:  # 已裁定（含 unresolved），跳过
            rows.append(state[cat])
            summary[state[cat]['verdict']] += 1
            continue
        if rec is None:
            print(f'  [warn] {cat} not found in jsonl')
            continue
        atype, anchor = best_anchor(rec)
        pc = None
        pc_err = ''
        used_anchor = anchor
        if anchor is None:
            pc_err = 'no anchor (无 CAS/name)'
        else:
            try:
                pc, used_anchor = pubchem_with_retry(anchor)
            except RuntimeError as e:
                pc_err = f'NETWORK_FAIL: {e}'
        verdict, note = adjudicate(rec, pc)
        # PubChem 未按锚点拿到 → 标记 unresolved 便于二次重跑
        if pc is None and pc_err.startswith('NETWORK_FAIL'):
            verdict = 'UNRESOLVED_NETWORK'
            note = pc_err
        row = {
            'catalog_no': cat,
            'product': (rec.get('product_name') or '')[:50],
            'anchor_type': atype or '',
            'anchor': (used_anchor or '')[:110],
            'jena_formula': rec.get('molecular_formula') or '',
            'jena_mw': rec.get('molecular_weight'),
            'calc_mw_correct_parser': (f'{mw_of(parse_formula_strict(rec.get("molecular_formula"))):.2f}'
                                       if parse_formula_strict(rec.get('molecular_formula')) else 'n/a'),
            'pubchem_formula': (pc or {}).get('formula') or '',
            'pubchem_mw': (pc or {}).get('mw') or '',
            'pubchem_inchikey': ((pc or {}).get('inchikey') or '')[:14],
            'verdict': verdict,
            'note': note,
        }
        rows.append(row)
        summary[verdict] += 1
        state[cat] = row
        json.dump(state, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        print(f'  {cat:14s} anchor={atype} -> {verdict}')
        if anchor:
            time.sleep(1.5)  # 礼貌间隔，避免限频

    # 写 CSV
    cols = ['catalog_no', 'product', 'anchor_type', 'anchor', 'jena_formula', 'jena_mw',
            'calc_mw_correct_parser', 'pubchem_formula', 'pubchem_mw', 'pubchem_inchikey',
            'verdict', 'note']
    with open(OUT_CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for row in rows:
            w.writerow(row)

    # 写 MD
    L = []
    L.append('# step2 · 14 条 formula↔MW 待确认记录 · PubChem 收口裁定\n')
    L.append(f'> 数据源：`backend/data/jena/jena_products_v2.jsonl`（2098 条）  ')
    L.append(f'> 裁定脚本：`verification/jena_formula_mw_pubchem.py`（正确解析器 + PubChem PUG-REST）  ')
    L.append(f'> 全量复扫：用正确解析器后，**真正的 formula↔MW 矛盾 = {len(genuine_all)} 条**（step1 报告称 14，系解析器误报夸大）\n')
    L.append('## 裁定汇总\n')
    L.append('| verdict | 计数 | 含义 |')
    L.append('|---------|-----:|------|')
    vdesc = {
        'FALSE_POSITIVE': 'step1 解析器误报；正确解析器下 jena 自洽',
        'OK_CONFIRMED': 'PubChem 确认 jena MW 正确；step1 误报',
        'JENA_FORMULA_FORMAT_ONLY': 'jena MW 正确，仅公式写法非 Hill',
        'JENA_FORMULA_WRONG': 'jena MW 对但公式字段错',
        'MW_DISCREPANCY': 'jena 公式自洽但与 PubChem MW 不符，需人工核对',
        'GENUINE_INTERNAL_CONTRADICTION': 'jena 公式与 MW 自身矛盾（正确解析器仍不符），PubChem 未收录',
        'BOTH_DIFFER': 'jena 公式与 MW 均与 PubChem 不符',
        'UNRESOLVED_NETWORK': 'PubChem 网络失败，需二次重跑',
    }
    for k, c in sorted(summary.items(), key=lambda x: -x[1]):
        L.append(f'| `{k}` | {c} | {vdesc.get(k, "")} |')
    L.append('\n## 逐条裁定\n')
    L.append('| catalog_no | anchor | jena formula | jena MW | 正确解析器MW | PubChem formula | PubChem MW | verdict | note |')
    L.append('|-----------|--------|--------------|--------:|--------------|---------------|------------|---------|------|')
    for row in rows:
        L.append(
            f"| {row['catalog_no']} | {row['anchor_type']} | {row['jena_formula']!r} | {row['jena_mw']} "
            f"| {row['calc_mw_correct_parser']} | {row['pubchem_formula'] or '-'} | {row['pubchem_mw'] or '-'} "
            f"| `{row['verdict']}` | {row['note'][:80]} |"
        )
    if genuine_all:
        L.append('\n## 全量真正矛盾清单（正确解析器，共 %d 条）\n' % len(genuine_all))
        L.append('> 含 14 条待确认之外的真实矛盾（若有），用于收口 step1 指标。\n')
        for c in genuine_all:
            L.append(f'- {c}')
    with open(OUT_MD, 'w', encoding='utf-8') as f:
        f.write('\n'.join(L))

    print(f'[done] rows={len(rows)} genuine_all={len(genuine_all)}')
    print(f'[out] {OUT_MD}')
    print(f'[out] {OUT_CSV}')


if __name__ == '__main__':
    main()
