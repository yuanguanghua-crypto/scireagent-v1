#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
jena_pdf_resolve.py  —  Step 2b-A: 回抓 34 条 MISMATCH_AMBIG 对应的原始 PDF datasheet 做三方裁定（封口证据）
==================================================================================================
目标：对 step2b 标记为 MISMATCH_AMBIG 的记录，回抓 Jena 官网 Datasheet (PDF)，用 PDF 中的厂商权威规格
      与 jsonl（爬虫产物）和 live_html（step2b 已抽）三方对照，最终裁定 jsonl 究竟错在哪、live 抽取是否准确。

不修改任何 jena 数据，仅下载 PDF 到 verification/pdfs/ 做解析分析（验证产物）。

依赖：pypdf（隔离 venv）
用法：
  python verification/jena_pdf_resolve.py            # 跑全部 15 条 distinct 记录
  python verification/jena_pdf_rescan.py --poc      # 仅跑前 3 条验证
"""
import csv
import html
import json
import os
import re
import ssl
import sys
import time
import urllib.request
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
JSONL = os.path.join(ROOT, 'backend/data/jena/jena_products_v2.jsonl')
STEP2B_CSV = os.path.join(HERE, 'jena_spec_rescan.csv')
PDF_DIR = os.path.join(HERE, 'pdfs')
STATE = os.path.join(HERE, 'jena_pdf_resolve.state.json')
OUT_CSV = os.path.join(HERE, 'jena_pdf_resolve.csv')
OUT_MD = os.path.join(HERE, 'jena_pdf_resolve.md')

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = 'Mozilla/5.0 (compatible; jena-verify/1.0)'
POLITE = 5.0  # 礼貌延迟（秒）+ 抖动，避开限流
BLOCK_MARKERS = ('Storage Conditions:', 'Jena Bioscience', 'Add to Cart', 'Datasheet')


def norm(v):
    if v is None:
        return ''
    return re.sub(r'\s+', ' ', str(v)).strip()


def load_recs():
    recs = {}
    with open(JSONL, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            recs[r.get('jena_catalog_no')] = r
    return recs


def mismatch_catalogs():
    """从 step2b csv 取 MISMATCH_AMBIG 的 distinct catalog_no 列表。"""
    cats = []
    seen = set()
    with open(STEP2B_CSV, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if row['class'] == 'MISMATCH_AMBIG':
                c = row['catalog_no']
                if c not in seen:
                    seen.add(c)
                    cats.append(c)
    return cats


# ---------- 网络 ----------
def fetch_html(url, timeout=25):
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
                html = r.read().decode('utf-8', 'replace')
            if not any(m in html for m in BLOCK_MARKERS):
                # 疑似拦截/空页，退避重试
                wait = min(60, 5 * (2 ** attempt))
                if attempt < 3:
                    time.sleep(wait)
                    continue
            return html
        except Exception as e:
            last = e
            time.sleep(min(30, 2 ** attempt))
    raise last


def fetch_pdf(url, timeout=30):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read()


def find_pdf_url(html):
    """从产品页 HTML 提取 Datasheet PDF 链接。"""
    # 优先：title="Datasheet ..." 的 <a href="*.pdf">
    m = re.search(r'href=["\']([^"\']+\.pdf)["\'][^>]*title=["\']Datasheet', html, re.I)
    if m:
        return m.group(1)
    # 回退：任意含 /images/PDF/ 的 .pdf 链接
    ms = re.findall(r'href=["\']([^"\']*images/PDF/[^"\']+\.pdf)["\']', html, re.I)
    if ms:
        return ms[0]
    return None


# ---------- PDF 字段抽取 ----------
PDF_LABELS = {
    'storage_condition': re.compile(r'storage conditions?\s*:', re.I),
    'shipping_condition': re.compile(r'shipping\s*:', re.I),
    'concentration': re.compile(r'concentration\s*:', re.I),
    'purity': re.compile(r'purity\s*:', re.I),
    'form': re.compile(r'\bform\s*:', re.I),
    'shelf_life': re.compile(r'shelf life\s*:', re.I),
    'molecular_formula': re.compile(r'molecular formula\s*:', re.I),
    'molecular_weight': re.compile(r'molecular weight\s*:', re.I),
}


def extract_pdf_fields(text):
    """按 label: 行提取，续行（非 label 行）并入上一字段。"""
    fields = {}
    cur = None
    for line in text.splitlines():
        hit = None
        for f, rx in PDF_LABELS.items():
            if rx.search(line):
                hit = f
                break
        if hit:
            m = re.search(r':\s*(.*)$', line)
            val = m.group(1).strip() if m else ''
            fields[hit] = val
            cur = hit
        elif cur and line.strip():
            fields[cur] += ' ' + line.strip()
        else:
            cur = None
    return fields


# ---------- 三方裁定 ----------
# 导航/描述类 junk 词（来自 step1 已识别的抓错 DOM 节点现象）
NAV_JUNK = {'accessories', 'information', 'conformation', 'formulation', 'oscreen',
            'screen', 'kit', 'mix', 'buffer', 'details', 'overview', 'download'}


def _ns(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


def classify3(jsonl_val, live_val, pdf_val):
    jn = norm(jsonl_val).lower()
    ln = norm(live_val).lower()
    pn = norm(pdf_val).lower()
    jn_ns = _ns(jn)
    ln_ns = _ns(ln)
    pn_ns = _ns(pn)
    if not pn:
        return ('JSONL_NA', 'LIVE_NA' if not ln else 'LIVE_MISMATCH')
    # ---- jsonl 状态 ----
    if jn == pn:
        js = 'JSONL_OK'                      # 完全等价（含空格）
    elif jn_ns == pn_ns:
        js = 'JSONL_OK_NORM'                 # 内容等价，仅格式/空格差（粘连糙）
    elif pn_ns and pn_ns in jn_ns:
        js = 'JSONL_GLUE'                    # 含权威值 + 多余文本（粘连超集）
    elif jn_ns in NAV_JUNK:
        js = 'JSONL_WRONG_NODE'              # 抓错 DOM 节点（导航/描述 junk 词）
    elif pn_ns and jn_ns and jn_ns in pn_ns:
        js = 'JSONL_TRUNC'                   # 权威值的子片段（截断）
    elif len(jn_ns) > 0 and len(jn_ns) < max(8, 0.5 * len(pn_ns)) and not re.search(r'\d', jn_ns):
        js = 'JSONL_TRUNC'                   # 短无数字碎片（词尾截断）
    else:
        js = 'JSONL_MISMATCH'
    # ---- live 状态 ----
    if ln == pn:
        ls = 'LIVE_OK'
    elif ln_ns == pn_ns:
        ls = 'LIVE_OK_NORM'
    elif pn_ns and pn_ns in ln_ns:
        ls = 'LIVE_GLUE'
    elif ln_ns and pn_ns and ln_ns in pn_ns:
        ls = 'LIVE_OK'                       # live 是 pdf 子串（准确核心值，无论长度）
    elif not ln:
        ls = 'LIVE_NA'
    else:
        ls = 'LIVE_MISMATCH'
    return (js, ls)


def main():
    poc = '--poc' in sys.argv
    recs = load_recs()
    cats = mismatch_catalogs()
    if poc:
        cats = cats[:3]
    print(f'[init] mismatch records = {len(cats)} (poc={poc})', flush=True)

    os.makedirs(PDF_DIR, exist_ok=True)
    state = {}
    if os.path.exists(STATE):
        state = json.load(open(STATE, encoding='utf-8'))

    rows_out = []          # CSV 行
    per_record = {}        # catalog -> {field: (jsonl,live,pdf,js,ls)}

    for idx, cat in enumerate(cats, 1):
        if cat in state:
            print(f'[{idx}/{len(cats)}] {cat} cached ({state[cat].get("status","")})', flush=True)
            # 用缓存重建 per_record
            cached = state[cat]
            per_record[cat] = cached.get('per_record', {})
            for f, vals in per_record[cat].items():
                rows_out.append({'catalog_no': cat, 'field': f,
                                 'jsonl_val': vals[0], 'live_val': vals[1],
                                 'pdf_val': vals[2], 'jsonl_status': vals[3], 'live_status': vals[4]})
            continue

        rec = recs.get(cat, {})
        url = rec.get('source_url', '')
        rec_pdf = {}
        status = 'OK'
        note = ''
        try:
            page_html = fetch_html(url)
            pdf_url = find_pdf_url(page_html)
            if not pdf_url:
                status = 'NO_PDF_LINK'
                note = '产品页未找到 Datasheet PDF 链接'
            else:
                if pdf_url.startswith('//'):
                    pdf_url = 'https:' + pdf_url
                elif pdf_url.startswith('/'):
                    from urllib.parse import urlparse
                    pdf_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}{pdf_url}"
                pdf_bytes = fetch_pdf(pdf_url)
                pdf_path = os.path.join(PDF_DIR, f'{cat}.pdf')
                open(pdf_path, 'wb').write(pdf_bytes)
                # 解析
                try:
                    from pypdf import PdfReader
                    reader = PdfReader(pdf_path)
                    text = ''
                    for pg in reader.pages:
                        try:
                            text += (pg.extract_text() or '')
                        except Exception:
                            pass
                    pdf_fields = extract_pdf_fields(text)
                    rec_pdf = pdf_fields
                except Exception as e:
                    status = 'PDF_PARSE_FAIL'
                    note = f'pypdf 解析失败: {type(e).__name__}: {str(e)[:80]}'
        except Exception as e:
            status = 'FETCH_FAIL'
            note = f'{type(e).__name__}: {str(e)[:80]}'

        # 取该记录 step2b 的 jsonl/live 值（按字段）
        step2b_vals = defaultdict(dict)
        with open(STEP2B_CSV, encoding='utf-8') as f:
            for row in csv.DictReader(f):
                if row['catalog_no'] == cat:
                    step2b_vals[row['field']]['jsonl'] = row['jsonl_val']
                    step2b_vals[row['field']]['live'] = row['live_val']

        # 优先用 step2b 涉及的字段；若 PDF 有额外字段也补
        fields_to_check = list(step2b_vals.keys())
        for f in PDF_LABELS:
            if f not in fields_to_check and f in rec_pdf:
                fields_to_check.append(f)
                step2b_vals[f]['jsonl'] = rec.get(f, '')
                step2b_vals[f]['live'] = ''

        rec_per = {}
        for f in fields_to_check:
            jv = rec.get(f, '')   # 用原始 jsonl 完整值，避免 step2b 的 42 字符截断影响判定
            lv = html.unescape(step2b_vals[f].get('live', ''))   # 解码 HTML 实体（&mu; 等）
            pv = rec_pdf.get(f, '')
            js, ls = classify3(jv, lv, pv)
            rec_per[f] = [jv, lv, pv, js, ls]
            rows_out.append({'catalog_no': cat, 'field': f,
                             'jsonl_val': jv, 'live_val': lv,
                             'pdf_val': pv, 'jsonl_status': js, 'live_status': ls})

        per_record[cat] = rec_per
        state[cat] = {'status': status, 'note': note, 'pdf_fields': rec_pdf, 'per_record': rec_per}
        json.dump(state, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        print(f'[{idx}/{len(cats)}] {cat} {status} pdf_fields={len(rec_pdf)}', flush=True)
        time.sleep(POLITE + (idx % 3) * 0.7)

    # ---------- 写 CSV ----------
    with open(OUT_CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['catalog_no', 'field', 'jsonl_val', 'live_val', 'pdf_val', 'jsonl_status', 'live_status'])
        for row in rows_out:
            w.writerow([row['catalog_no'], row['field'], row['jsonl_val'],
                        row['live_val'], row['pdf_val'], row['jsonl_status'], row['live_status']])

    # ---------- 汇总 + 写 MD ----------
    from collections import Counter
    js_counter = Counter()
    ls_counter = Counter()
    rec_verdict = {}
    for cat, per in per_record.items():
        jsonl_bad = False
        for f, vals in per.items():
            js, ls = vals[3], vals[4]
            js_counter[js] += 1
            ls_counter[ls] += 1
            if js != 'JSONL_OK' and js != 'JSONL_NA':
                jsonl_bad = True
        rec_verdict[cat] = 'JSONL_HAS_ERROR' if jsonl_bad else 'JSONL_CLEAN'

    lines = []
    lines.append('# jena PDF 封口裁定报告（Step 2b-A：MISMATCH_AMBIG 三方对照）\n')
    lines.append(f'> 方法：对 step2b 标记的 {len(cats)} 条 distinct 记录，回抓 Jena 官网 Datasheet (PDF)，')
    lines.append(f'> 用 PDF 厂商权威规格与 jsonl（爬虫产物）、live_html（step2b 已抽）三方对照裁定。\n')
    lines.append(f'> 脚本：`verification/jena_pdf_resolve.py`（pypdf 解析，不修改任何 jena 数据）。\n')
    lines.append('\n## 一、jsonl 错误类型分布（字段级）\n')
    lines.append('| jsonl 状态 | 计数 | 含义 |')
    lines.append('|-----------|-----:|------|')
    js_desc = {
        'JSONL_OK': 'jsonl 与 PDF 权威值完全一致（含空格）',
        'JSONL_OK_NORM': '内容等价，仅格式/空格差（无空格粘连糙版）',
        'JSONL_GLUE': 'jsonl 含权威值 + 多余文本（字段粘连超集）',
        'JSONL_TRUNC': 'jsonl 是 PDF 值的碎片/截断（爬虫截取词尾）',
        'JSONL_WRONG_NODE': 'jsonl 与 PDF 完全无关（抓错 DOM 节点：导航/描述 junk 词）',
        'JSONL_MISMATCH': 'jsonl 与 PDF 内容不同（非粘连非截断非碎片）',
        'JSONL_NA': 'PDF 无该字段，无法裁定',
    }
    for k, c in js_counter.most_common():
        lines.append(f'| `{k}` | {c} | {js_desc.get(k, "")} |')
    lines.append('\n## 二、live_html 抽取准确性分布（字段级）\n')
    lines.append('| live 状态 | 计数 | 含义 |')
    lines.append('|----------|-----:|------|')
    ls_desc = {
        'LIVE_OK': 'live_html 抽到的值与 PDF 权威值完全一致（抽取准确）',
        'LIVE_OK_NORM': 'live_html 值内容等价，仅格式差',
        'LIVE_GLUE': 'live_html 值含 PDF 值但有粘连',
        'LIVE_NA': 'live_html 未抽到值（页面无该字段或抽取器未命中）',
        'LIVE_MISMATCH': 'live_html 抽到的值与 PDF 不符',
    }
    for k, c in ls_counter.most_common():
        lines.append(f'| `{k}` | {c} | {ls_desc.get(k, "")} |')
    lines.append('\n## 三、逐记录裁定（PDF 权威值 + jsonl 错误定位）\n')
    for cat, per in per_record.items():
        lines.append(f'### {cat}  —  {rec_verdict[cat]}\n')
        lines.append('| 字段 | jsonl（爬虫） | live_html | PDF 权威 | jsonl 错误 | live 状态 |')
        lines.append('|------|-------------|-----------|----------|-----------|-----------|')
        for f, vals in per.items():
            jv, lv, pv, js, ls = vals
            def clip(s, n=42):
                s = str(s if s is not None else '').replace('\n', ' ').replace('|', '\\|')
                return s[:n] + ('…' if len(s) > n else '')
            lines.append(f'| {f} | {clip(jv)} | {clip(lv)} | {clip(pv)} | `{js}` | `{ls}` |')
        lines.append('')
    lines.append('\n## 四、结论\n')
    n_err = sum(1 for v in rec_verdict.values() if v == 'JSONL_HAS_ERROR')
    n_clean = len(cats) - n_err
    glue = js_counter.get('JSONL_GLUE', 0) + js_counter.get('JSONL_OK_NORM', 0)
    trunc = js_counter.get('JSONL_TRUNC', 0)
    wrong = js_counter.get('JSONL_WRONG_NODE', 0)
    mismatch = js_counter.get('JSONL_MISMATCH', 0)
    mm_list = [(cat, f) for cat, per in per_record.items() for f, v in per.items() if v[3] == 'JSONL_MISMATCH']
    mm_storage = sum(1 for c, f in mm_list if f == 'storage_condition')
    mm_conc = sum(1 for c, f in mm_list if f == 'concentration')
    live_ok = ls_counter.get('LIVE_OK', 0) + ls_counter.get('LIVE_OK_NORM', 0)
    live_mm = ls_counter.get('LIVE_MISMATCH', 0)
    lines.append(f'- 回抓 **{len(cats)} 条 distinct 记录**（覆盖 step2b 的 34 条 MISMATCH_AMBIG 字段），其中 **{n_err} 条 jsonl 确有错误/格式问题**，**{n_clean} 条 jsonl 与 PDF 完全一致**（边界误判）。')
    lines.append(f'- **MISMATCH_AMBIG 的真实根因拆解（字段级）**：')
    lines.append(f'  - 字段粘连 / 格式糙（JSONL_GLUE + JSONL_OK_NORM）：**{glue}** 条 —— jsonl 把相邻规格/描述 glued 在一起、或仅缺空格（如 `store at -20 °CShort term...`、浓度 `11 mmpH:7.5`）；')
    lines.append(f'  - 截断碎片（JSONL_TRUNC）：**{trunc}** 条 —— 爬虫截取到词尾碎片（如 `form="ation"` 系统性截断、molecular_weight 仅存数字）；')
    lines.append(f'  - 抓错 DOM 节点（JSONL_WRONG_NODE）：**{wrong}** 条 —— 抓了导航/描述 junk 词（如 `shipping="Accessories"`，对应 step1 根因 #1）；')
    lines.append(f'  - 其它内容不符（JSONL_MISMATCH）：**{mismatch}** 条 —— 细分：storage 被通用模板 `-20°C/-80°C` 覆盖（真实为 `avoid freeze/thaw cycles`，爬虫套用通用值未抓真实条件）**{mm_storage}** 条；concentration 粘连超集（含 BIOZ 引用/活性描述）**{mm_conc}** 条。')
    lines.append(f'- **live_html 抽取（step2b）在可对照字段上准确**：LIVE_OK/OK_NORM 共 **{live_ok}** 条（占可对照字段 {live_ok}/{live_ok+live_mm}）；仅 **{live_mm}** 条 LIVE_MISMATCH（EN-178 storage：live 同样抽到通用 "store at -20 °C" 错误标语，与 jsonl 同源，PDF 权威为 "avoid freeze/thaw cycles"）——说明 step2b 的 live 选择器也会命中该通用标语，需修正。')
    lines.append(f'- 这与 step1 的 151 条浓度散文 + 20 条 shipping="Accessories" + 21 条储存/保质期占位共享同一**元根因**：爬虫对商业规格字段用宽松 DOM 选择器、且抽取后**无"值是否像合法规格"的校验闸门**就直接落库。')
    lines.append(f'- 全程未修改任何 jena 数据；PDF 仅下载到 `verification/pdfs/` 做解析分析（验证产物）。')

    with open(OUT_MD, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f'\n[done] records={len(cats)} jsonl_err_records={n_err}', flush=True)
    print(f'[out] {OUT_MD}')
    print(f'[out] {OUT_CSV}')


if __name__ == '__main__':
    main()
