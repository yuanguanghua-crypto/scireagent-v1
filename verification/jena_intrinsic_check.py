#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jena 内在校验（A 类：不可能 / 畸形，零外部依赖）。

设计前提（与用户确认）：
- 离线跑"规格污染清单"不依赖任何可信外部源；
- 它只解决 A 类错误——数据违反自身「字段契约」或「内部算术矛盾」，
  这类错误不需要知道"正确值"就能判定错。

校验项：
  A1  concentration 类型契约（散文污染 / 超长 / 有数字无单位）
  A2  molecular_formula ↔ molecular_weight 内部算术自洽
  A3  cas_number CAS 校验位（mod-10，纯算法，无网络）
  A4  storage / shipping / shelf_life 枚举可映射性
  A5  编码污染（U+FFFD / 控制字符 / NBSP）
  A6  字段类型违反（MW 非数字 / formula 含非法元素）
  A7  product_name 重复（碰撞风险，仅信息级）

输出：
  verification/jena_intrinsic_report.md  人类可读报告
  verification/jena_intrinsic_report.csv 逐条记录（供筛选）
"""
import json
import re
import os
import csv
from collections import Counter, defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSONL = os.path.join(REPO, "backend", "data", "jena", "jena_products_v2.jsonl")
OUT_MD = os.path.join(REPO, "verification", "jena_intrinsic_report.md")
OUT_CSV = os.path.join(REPO, "verification", "jena_intrinsic_report.csv")

# ── 平均原子量（常用元素）─────────────────────────────────────────────
ATOMIC = {
    'H': 1.008, 'C': 12.011, 'N': 14.007, 'O': 15.999, 'P': 30.974, 'S': 32.06,
    'F': 18.998, 'Cl': 35.45, 'Br': 79.904, 'I': 126.90, 'Na': 22.990, 'K': 39.098,
    'Mg': 24.305, 'Ca': 40.078, 'Fe': 55.845, 'Zn': 65.38, 'Cu': 63.546, 'B': 10.81,
    'Si': 28.085, 'Li': 6.94, 'Mn': 54.938, 'Co': 58.933, 'Ni': 58.693, 'Se': 78.96,
    'As': 74.922, 'Mo': 95.95, 'Au': 196.97, 'Ag': 107.87, 'Pt': 195.08, 'Ru': 101.07,
    'Rh': 102.91, 'Ir': 192.22, 'Ti': 47.867, 'V': 50.942, 'Cr': 51.996, 'Al': 26.982,
    'Ba': 137.33, 'Pb': 207.2, 'Hg': 200.59, 'Cd': 112.41, 'Be': 9.012, 'Te': 127.60,
}

# ── A1 concentration 契约 ─────────────────────────────────────────────
PROSE = re.compile(
    r'phase diagram|supersaturation|using the|containing|is slowly|'
    r'the point of|we recommend|please note|this product|for example|'
    r'solution is|the buffer|add (the|an?) ', re.I)
UNIT = re.compile(
    r'mM|µM|μM|nM|pM|M\b|%|w/v|mg|µg|μg|ng|g/ml|g/l|ml|µl|μl|units?/µ?l|\b\d+\s*x\b', re.I)
METH = re.compile(r'photometrically|spectrophotometric|hplc|page|\bpage\b', re.I)


def conc_issue(v):
    if not isinstance(v, str) or not v.strip():
        return None
    s = v.strip()
    if len(s) > 40:
        return 'too_long'
    if PROSE.search(s):
        return 'prose'
    has_digit = bool(re.search(r'\d', s))
    has_unit = bool(UNIT.search(s))
    if has_digit and not has_unit and not METH.search(s):
        return 'digit_no_unit'
    return None


# ── A2 formula ↔ MW 自洽 ──────────────────────────────────────────────
FORMULA_CLEAN = re.compile(r'^[A-Za-z0-9()]*$')
FORMULA_TOKEN = re.compile(r'([A-Z][a-z]?)(\d*)')


def compute_mw(formula):
    """返回 (mw, ok)。无法计算（聚合物 n / 非标准元素 / 含水合物点）返回 (None, False)。"""
    if not isinstance(formula, str) or not formula.strip():
        return None, False
    f = formula.replace(' ', '').replace('·', '').replace('*', '')
    if not FORMULA_CLEAN.match(f) or 'n' in f or 'x' in f:
        return None, False
    try:
        mw = 0.0
        for m in FORMULA_TOKEN.finditer(f):
            sym, cnt = m.group(1), m.group(2)
            if sym not in ATOMIC:
                return None, False
            mw += ATOMIC[sym] * (int(cnt) if cnt else 1)
        return mw, True
    except Exception:
        return None, False


def mw_issue(formula, mw_raw):
    if not isinstance(formula, str) or not formula.strip():
        return None
    if not isinstance(mw_raw, (int, float)) and not (isinstance(mw_raw, str) and mw_raw.strip()):
        return None
    try:
        stored = float(str(mw_raw).strip())
    except Exception:
        return 'mw_not_numeric'
    comp, ok = compute_mw(formula)
    if not ok:
        return None  # 聚合物/含水合物等无法静态计算，跳过（非 A 类）
    tol = max(5.0, 0.05 * comp)  # 5% 或 5.0 绝对，容忍水合物/同位素小幅偏差
    if abs(comp - stored) > tol:
        return 'mw_formula_mismatch'  # 细节见 snippet(formula/mw)
    return None


def formula_malformed(formula):
    if not isinstance(formula, str) or not formula.strip():
        return None
    f = formula.replace(' ', '').replace('·', '').replace('*', '')
    if not FORMULA_CLEAN.match(f) or 'n' in f or 'x' in f:
        return None  # 聚合物等合法但不可算，不判畸形
    # 解析看是否有非法元素符号
    for m in FORMULA_TOKEN.finditer(f):
        if m.group(1) not in ATOMIC:
            return f'bad_element({m.group(1)})'
    return None


# ── A3 CAS 校验位（mod-10）─────────────────────────────────────────────
def cas_check(cas):
    """返回 True / False / None(format 不符)。"""
    if not isinstance(cas, str) or not cas.strip():
        return None
    m = re.match(r'^(\d{2,7})-(\d{2})-(\d)$', cas.strip())
    if not m:
        return None  # 格式不符，单独由 cas_format 标记
    digits = m.group(1) + m.group(2)
    check = int(m.group(3))
    total = 0
    for i, d in enumerate(reversed(digits), start=1):
        total += int(d) * i
    return (total % 10) == check


def cas_format_issue(cas):
    if not isinstance(cas, str) or not cas.strip():
        return None
    if not re.match(r'^\d{2,7}-\d{2}-\d$', cas.strip()):
        return 'cas_bad_format'
    return None


# ── A4 枚举可映射性（复刻 jena_index.normalize_* 的关键词逻辑，免 Django 导入）──
def storage_map(v):
    if not isinstance(v, str) or not v.strip():
        return None
    s = v.lower()
    # 任意温度表达（含范围如 8-10 °C、-20°C、4°C）即视为可映射
    if re.search(r'\d\s*°?\s*c', s) or 'ambient' in s or 'room' in s:
        return True
    return False


def ship_map(v):
    if not isinstance(v, str) or not v.strip():
        return None
    s = v.lower()
    if any(k in s for k in ['dry ice', 'gel pack', 'cold pack', 'blue ice', 'ice pack', 'ambient', 'room']) \
            or re.search(r'\d\s*°?\s*c', s):  # "shipped at 4 °C" 等冷运亦视为可映射
        return True
    return False


def shelf_map(v):
    if not isinstance(v, str) or not v.strip():
        return None
    s = v.lower()
    if 'n/a' in s or ' not ' in s or s.startswith('not '):
        return None
    if re.search(r'\d+\s*month', s) or re.search(r'\d+\s*year', s):
        return True
    return False


# ── A5 编码污染 ───────────────────────────────────────────────────────
def encoding_issue(value):
    if not isinstance(value, str):
        return None
    if '�' in value:
        return 'replacement_char'
    if ' ' in value:  # NBSP U+00A0（注意：非常规空格）
        return 'nbsp'
    if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', value):
        return 'control_char'
    return None


# ── 主流程 ────────────────────────────────────────────────────────────
def main():
    recs = []
    with open(JSONL, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    n = len(recs)
    print(f"[load] {n} records from {JSONL}")

    findings = []          # list of dict(catalog_no, product_name, field, issue, tier, snippet)
    per_record = defaultdict(list)
    issue_counter = Counter()
    tier_counter = Counter()
    flagged_records = 0

    def add(cat_local, field, issue_key, snip, tier):
        issue_counter[issue_key] += 1
        tier_counter[tier] += 1
        per_record[cat_local].append((field, issue_key, snip, tier))

    # 预扫 product_name 重复（A7）
    name_seen = {}
    dup_names = set()
    for r in recs:
        nm = (r.get('product_name') or '').strip().lower()
        if not nm:
            continue
        if nm in name_seen:
            dup_names.add(nm)
        else:
            name_seen[nm] = 1

    for r in recs:
        cat = (r.get('jena_catalog_no') or '').strip()
        pname = (r.get('product_name') or '').strip()

        # A1 concentration
        ci = conc_issue(r.get('concentration'))
        if ci:
            add(cat, 'concentration', f'concentration:{ci}', snippet(r.get('concentration')), 'corruption')

        # A2 formula ↔ MW
        mi = mw_issue(r.get('molecular_formula'), r.get('molecular_weight'))
        if mi:
            tier = 'deferred' if mi == 'mw_formula_mismatch' else 'corruption'
            add(cat, 'mw_formula', f'mw:{mi}',
                f"formula={r.get('molecular_formula')!r} mw={r.get('molecular_weight')!r}", tier)
        fm = formula_malformed(r.get('molecular_formula'))
        if fm:
            add(cat, 'molecular_formula', f'formula:{fm.split("(")[0]}', snippet(r.get('molecular_formula')), 'corruption')

        # A3 CAS（区分：单值校验位 / 多值盐注释 / 非法）
        cas_raw = r.get('cas_number')
        if isinstance(cas_raw, str) and cas_raw.strip():
            s = cas_raw.strip()
            if re.match(r'^\d{2,7}-\d{2}-\d$', s):
                cv = cas_check(s)
                if cv is False:
                    add(cat, 'cas_number', 'cas:checksum_invalid', s, 'corruption')
            else:
                tokens = re.findall(r'\d{2,7}-\d{2}-\d', s)
                if tokens and (',' in s or ';' in s or '(' in s or len(tokens) >= 2):
                    add(cat, 'cas_number', 'cas:multi_value', s, 'structural')
                else:
                    add(cat, 'cas_number', 'cas:malformed', s, 'corruption')

        # A4 storage / shipping / shelf_life 可映射性
        for field, mapper, tag in [
            ('storage_condition', storage_map, 'storage'),
            ('shipping_condition', ship_map, 'shipping'),
            ('shelf_life', shelf_map, 'shelf_life'),
        ]:
            mp = mapper(r.get(field))
            if mp is False:
                raw = r.get(field)
                if tag == 'shipping' and isinstance(raw, str) and 'access' in raw.lower():
                    tier = 'corruption'   # "Accessories" 是错位污染
                else:
                    tier = 'structural'   # 通用说明占位（see labels）
                add(cat, field, f'{tag}:unmappable', snippet(raw), tier)

        # A5 编码（扫描全部字符串字段）
        for field, val in r.items():
            ei = encoding_issue(val)
            if ei:
                add(cat, field, f'encoding:{ei}', snippet(val), 'corruption')

        # A6 MW 非数字
        mw_raw = r.get('molecular_weight')
        if mw_raw is not None and mw_raw != '' and not isinstance(mw_raw, (int, float)):
            try:
                float(str(mw_raw).strip())
            except Exception:
                add(cat, 'molecular_weight', 'mw:not_numeric', snippet(mw_raw), 'corruption')

        if per_record[cat]:
            flagged_records += 1
            for (field, issue_key, snip, tier) in per_record[cat]:
                findings.append({
                    'catalog_no': cat, 'product_name': pname,
                    'field': field, 'issue': issue_key, 'tier': tier, 'snippet': snip,
                })

    # 写 CSV
    with open(OUT_CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['catalog_no', 'product_name', 'field', 'issue', 'tier', 'snippet'])
        for row in findings:
            w.writerow([row['catalog_no'], row['product_name'], row['field'],
                        row['issue'], row['tier'], row['snippet']])

    # 写 MD
    TIERS = [
        ('corruption', 'Tier 1 · 确定性损坏（爬虫/清洗引入，高置信）',
         '违反字段契约或内部算术，无需外部真值即可判定为错误。'),
        ('structural', 'Tier 2 · 结构性 / 匹配不可用（非损坏，但需关注）',
         '数据本身未必错，但格式使匹配器无法使用，或仅为通用说明占位。'),
        ('deferred', 'Tier 3 · 待 step2 外部确认（疑似，需 PubChem 裁定）',
         '离线无法判定，疑似内部矛盾，需 step2 用 PubChem 比对确认。'),
    ]
    desc = {
        'concentration:prose': 'concentration 含散文描述（爬虫错位硬污染）',
        'concentration:too_long': 'concentration 超长（>40字符，描述泄漏）',
        'concentration:digit_no_unit': 'concentration 有数字但无浓度单位',
        'mw:mw_formula_mismatch': 'formula 理论 MW 与存储 MW 矛盾（离线疑似，step2 确认）',
        'mw:mw_not_numeric': 'molecular_weight 非数字',
        'mw:not_numeric': 'molecular_weight 非数字',
        'formula:bad_element': 'molecular_formula 含无法识别元素',
        'cas:checksum_invalid': 'cas_number 校验位(mod-10)不通过（清洗损坏）',
        'cas:multi_value': 'cas_number 含多值/盐注释（匹配器单值键无法使用）',
        'cas:malformed': 'cas_number 格式非法且非多值',
        'storage:unmappable': 'storage_condition 为通用说明占位，无温度',
        'shipping:unmappable': 'shipping_condition 无法归一化（Accessories=错位污染）',
        'shelf_life:unmappable': 'shelf_life 为通用说明占位',
        'encoding:nbsp': '含 NBSP(U+00A0) 非常规空白',
        'encoding:replacement_char': '含 U+FFFD 替换符（编码损坏）',
        'encoding:control_char': '含控制字符',
    }
    itier = {fr['issue']: fr['tier'] for fr in findings}

    lines = []
    lines.append('# jena 内在校验报告（A 类：不可能 / 畸形，零外部依赖）\n')
    lines.append(f'> 数据源：`backend/data/jena/jena_products_v2.jsonl`  \n')
    lines.append(f'> 记录总数：**{n}** ｜ 命中记录：**{flagged_records}**（{100*flagged_records/n:.1f}%） ｜ 异常条目：**{len(findings)}**  \n')
    lines.append(f'> 分层：确定性损坏 **{tier_counter["corruption"]}** ｜ 结构性 **{tier_counter["structural"]}** ｜ 待确认 **{tier_counter["deferred"]}**  \n')
    lines.append(f'> 生成脚本：`verification/jena_intrinsic_check.py`（不依赖 PubChem / 不联网）\n')

    for tier_key, tier_title, tier_note in TIERS:
        items = [(k, c) for k, c in issue_counter.items() if itier.get(k) == tier_key]
        lines.append(f'\n## {tier_title}\n')
        lines.append(f'> {tier_note}\n')
        if items:
            lines.append('| 异常类型 | 计数 | 说明 |')
            lines.append('|---------|-----:|------|')
            for k, c in sorted(items, key=lambda x: -x[1]):
                lines.append(f'| `{k}` | {c} | {desc.get(k, "")} |')
        else:
            lines.append('> （无）')

    lines.append('\n## A7 product_name 重复（碰撞风险，信息级）\n')
    lines.append(f'> 共 **{len(dup_names)}** 个 product_name 出现重复（jena 用 catalog_no 作主键，名字重复仅提示 name 匹配碰撞风险）。\n')
    if dup_names:
        for nm in sorted(dup_names)[:40]:
            lines.append(f'- {nm}')
        if len(dup_names) > 40:
            lines.append(f'- …（其余 {len(dup_names)-40} 条见 CSV）')

    lines.append('\n## 异常记录明细（节选前 80 条，全量见 CSV）\n')
    lines.append('| catalog_no | product | field | issue | tier | snippet |')
    lines.append('|-----------|--------|-------|-------|------|---------|')
    for row in findings[:80]:
        snip = row['snippet'].replace('|', '\\|').replace('\n', ' ')
        if len(snip) > 70:
            snip = snip[:67] + '...'
        lines.append(f"| {row['catalog_no']} | {row['product_name'][:22]} | {row['field']} | {row['issue']} | {row['tier']} | {snip} |")
    if len(findings) > 80:
        lines.append(f'\n> 其余 {len(findings)-80} 条见 `jena_intrinsic_report.csv`。')

    with open(OUT_MD, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    # 控制台摘要
    print(f"[done] flagged_records={flagged_records} findings={len(findings)}")
    print(f"  corruption={tier_counter['corruption']} structural={tier_counter['structural']} deferred={tier_counter['deferred']}")
    for k, c in issue_counter.most_common():
        print(f"  [{itier.get(k,'?')[:4]}] {k:34s} {c}")
    print(f"[out] {OUT_MD}")
    print(f"[out] {OUT_CSV}")


def snippet(v, n=70):
    if v is None:
        return ''
    s = str(v)
    return s if len(s) <= n else s[:n] + '...'


if __name__ == '__main__':
    main()
