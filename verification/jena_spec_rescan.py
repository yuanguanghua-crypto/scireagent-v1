#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
jena 规格字段「抽样回抓」根因校验（step 2b）

目标：只用 jena 自带的 source_url（= Jena 官网 datasheet 产品页）做对照，
      找出「为什么 jena 规格字段（concentration/storage/shipping/shelf_life/
      purity/form）会出现污染/错值」。
      **本项目只找原因、不修改任何数据。**

方法：
  1. 取样本 = 已知污染记录（step1 报告）+ 随机干净基线；
  2. 回抓每条 live 产品页 HTML；
  3. 用统一的 `<b>标签:</b> 值` 正则抽取规格字段；
  4. 与 jsonl 中该记录的字段值比对，逐字段给根因分类。

根因分类（per field）：
  MATCH              jsonl == live（爬虫忠实 / 源头未变）
  SCRAPER_DOM_ERR    jsonl 是明显 junk（散文 / 导航词如 Accessories），
                     live 是合法值 → 爬虫抓错 DOM 节点（字段↔DOM 映射错）
  UNDER_EXTRACTED    live 有值，jsonl 为空 → 爬虫漏抽
  OVER_EXTRACTED     jsonl 有值，live 无 → 爬虫多抽（或源头已删）
  MISMATCH_AMBIG     jsonl 非空非 junk，live 也非空，但二者不同
                     → 可能是「爬虫错」也可能是「2026-06-28 抓取后源头改了」
                        （drift），需原始抓取 HTML 或 PDF 才能定，本脚本标灰。

诚实声明：
  - 抓取时间 crawled_at 约 2026-06-28；live 当前可能已变。
  - 凡 jsonl 是明显 junk（散文/导航词）→ 必为爬虫错（任何正规 datasheet
    都不会把 shipping 写成 "Accessories" 或 concentration 写成 "phase diagram"）。
  - 凡 jsonl 与 live 均为合法值但不同 → 标 MISMATCH_AMBIG，不武断归责。

断点续跑：state.json 存 {catalog_no: result_dict}，重跑只补未完成/失败的。
礼貌：每次请求间隔 POLITE 秒 + 指数退避重试。
"""
import json, re, urllib.request, ssl, csv, time, random, sys, os
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
JSONL = os.path.join(ROOT, 'backend/data/jena/jena_products_v2.jsonl')
STEP1_CSV = os.path.join(HERE, 'jena_intrinsic_report.csv')
OUT_MD = os.path.join(HERE, 'jena_spec_rescan.md')
OUT_CSV = os.path.join(HERE, 'jena_spec_rescan.csv')
STATE = os.path.join(HERE, 'jena_spec_rescan.state.json')

POLITE = 5.0
UA = 'Mozilla/5.0 (compatible; jena-verify/1.0)'
UA2 = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'

# 真实产品页必须含至少一个标记；否则视为「拦截/挑战/空页」→ 退避重试
PRODUCT_MARKERS = ['Storage Conditions:', 'Shipping:', 'Jena Bioscience',
                   'Add to Cart', 'Add to cart', 'product-detail']

# 规格字段 → 抽取正则（统一匹配 <b>标签:</b> 后面直到下一个标签的文本）
SPEC_RE = {
    'storage_condition':  re.compile(r'<b>[^<]*?storage conditions?[^<]*?</b>\s*([^<]+)', re.I),
    'shipping_condition': re.compile(r'<b>[^<]*?shipping[^<]*?</b>\s*([^<]+)', re.I),
    'shelf_life':         re.compile(r'<b>[^<]*?shelf life[^<]*?</b>\s*([^<]+)', re.I),
    'concentration':      re.compile(r'<b>[^<]*?\bconcentration\b[^<]*?</b>\s*([^<]+)', re.I),
    'purity':             re.compile(r'<b>[^<]*?\bpurity\b[^<]*?</b>\s*([^<]+)', re.I),
    'form':               re.compile(r'<b>[^<]*?\b(?:physical\s+)?form\b[^<]*?</b>\s*([^<]+)', re.I),
}
# 导航/垃圾词（出现在 jsonl 规格字段里即判定为 junk）
NAV_JUNK = {'accessories', 'overview', 'home', 'products', 'search', 'contact', 'about us'}

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def norm(v):
    if v is None:
        return ''
    return re.sub(r'\s+', ' ', str(v)).strip()


PROSE_MARKERS = ['phase diagram', 'supersaturation', 'slowly increased', 'using the',
                 'e.g.', 'containing', 'for example', 'in order to', 'allow to',
                 'the solution', 'is supplied as', 'seeding experiments',
                 'a point of', 'optimize the growth']

def is_junk(v):
    n = norm(v).lower()
    if n in NAV_JUNK:
        return True
    if '®' in v or '™' in v or '�' in v:   # mojibake / 注册商标符号残留
        return True
    if n in ('.', '..', '-', '', 'n/a'):
        return True
    # 截断碎片：极短、无数字、无已知规格词 → 疑似爬虫截断了词
    if 0 < len(n) < 5 and not re.search(r'\d', n) \
       and not re.search(r'(solid|liquid|solution|powder|lyo|aqueous|white|clear|gel|bead|plate|kit|mix|buffer|water|oil|salt|freeze|dry)', n):
        return True
    # 散文级：长且含散文标记（避免误伤合法长规格值，如 "liquid (Supplied in Sodium Phosphate...)"）
    if len(n) > 40 and any(m in n for m in PROSE_MARKERS):
        return True
    return False


def load_jsonl():
    recs = {}
    for l in open(JSONL, encoding='utf-8'):
        l = l.strip()
        if not l:
            continue
        r = json.loads(l)
        recs[r.get('jena_catalog_no')] = r
    return recs


def build_sample(recs, poc=False):
    """返回 [(catalog_no, reason), ...]"""
    # 1) 污染记录（来自 step1 报告）
    pollution = []
    if os.path.exists(STEP1_CSV):
        with open(STEP1_CSV, encoding='utf-8') as f:
            for row in csv.DictReader(f):
                cat = row['catalog_no']
                field = row['field']
                issue = row['issue']
                snip = row.get('snippet', '')
                if field == 'concentration' and issue.startswith('concentration:'):
                    pollution.append((cat, 'conc_prose'))
                elif field == 'shipping_condition' and 'Accessories' in snip:
                    pollution.append((cat, 'ship_accessories'))
                elif field in ('storage_condition', 'shelf_life') and issue == 'unmappable':
                    pollution.append((cat, 'storage_shelf_unmap'))
    # 去重保序
    seen = set()
    pollution = [x for x in pollution if not (x[0] in seen or seen.add(x[0]))]

    # 2) 干净基线（step1 无 finding 的随机样本）
    flagged = {c for c, _ in pollution}
    clean = [c for c in recs if c not in flagged]
    random.seed(20260716)
    clean_sample = random.sample(clean, min(40, len(clean)))

    if poc:
        # PoC: 全取 accessories + 10 浓度 + 10 储存 + 10 干净
        acc = [(c, r) for c, r in pollution if r == 'ship_accessories']
        conc = [(c, r) for c, r in pollution if r == 'conc_prose'][:10]
        stg = [(c, r) for c, r in pollution if r == 'storage_shelf_unmap'][:10]
        cl = [(c, 'clean_baseline') for c in clean_sample[:10]]
        sample = acc + conc + stg + cl
    else:
        sample = pollution + [(c, 'clean_baseline') for c in clean_sample]
    return sample


def is_product_page(html):
    h = html or ''
    return any(m in h for m in PRODUCT_MARKERS)


def fetch_html(url, timeout=25, max_retry=7):
    """抓取产品页；若返回的是拦截/挑战/空页（HTTP 200 但无产品标记），退避重试。
    最终仍失败则抛异常，由调用方计入 FETCH_FAIL 并留待二次重跑。"""
    last = None
    for attempt in range(max_retry):
        try:
            ua = UA if attempt % 2 == 0 else UA2
            req = urllib.request.Request(url, headers={'User-Agent': ua})
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
                html = r.read().decode('utf-8', 'replace')
            if not is_product_page(html):
                # 限流/拦截页：HTTP 200 但无产品标记 → 退避后重试
                last = RuntimeError('blocked_or_empty_page(no product markers)')
                time.sleep(min(10 * (attempt + 1), 60))
                continue
            return html
        except Exception as e:
            last = e
            time.sleep(min(5 * (attempt + 1), 40))
    raise last


def extract_specs(html):
    out = {}
    for field, rx in SPEC_RE.items():
        m = rx.search(html)
        if m:
            out[field] = norm(m.group(1))
    return out


def classify(jsonl_val, live_val):
    j = norm(jsonl_val)
    lv = norm(live_val)
    if j and is_junk(j):
        # jsonl 是 junk（散文 / 导航词）
        if lv:
            return 'SCRAPER_DOM_ERR'          # live 有合法值且 jsonl 是 junk → 抓错 DOM 节点（确凿）
        return 'SCRAPER_JUNK'                 # live 无此字段 → 爬虫抽到 junk 内容（散文/导航词），根因=错内容抽取
    if j and lv:
        if j.lower() == lv.lower():
            return 'MATCH'
        return 'MISMATCH_AMBIG'
    if j and not lv:
        return 'OVER_EXTRACTED'               # jsonl 有值、live 无 → 爬虫多抽（或源头已删该字段）
    if (not j) and lv:
        return 'UNDER_EXTRACTED'
    return 'BOTH_EMPTY'


def load_state():
    if os.path.exists(STATE):
        return json.load(open(STATE, encoding='utf-8'))
    return {}


def main():
    poc = '--poc' in sys.argv
    recs = load_jsonl()
    sample = build_sample(recs, poc=poc)
    state = load_state()

    print(f'[start] sample={len(sample)} poc={poc} cached={len(state)}')

    rows = []          # 逐字段比对明细
    rec_summary = []   # 每条记录根因汇总
    root_counter = Counter()
    fetch_fail = []

    for i, (cat, reason) in enumerate(sample):
        if cat in state:
            continue
        rec = recs.get(cat)
        if not rec:
            continue
        url = norm(rec.get('source_url'))
        result = {'catalog_no': cat, 'product_name': rec.get('product_name'),
                  'reason': reason, 'source_url': url,
                  'crawled_at': rec.get('crawled_at'), 'fields': {}}

        if 'link.springer.com' in url:
            result['outcome'] = 'SOURCE_URL_OUTLIER'
            result['note'] = 'source_url 指向 springer 而非 jena 产品页（数据质量问题）'
            state[cat] = result
            rec_summary.append(result)
            root_counter['SOURCE_URL_OUTLIER'] += 1
            print(f'  [{i+1}/{len(sample)}] {cat}: SOURCE_URL_OUTLIER')
            continue

        try:
            html = fetch_html(url)
            live = extract_specs(html)
        except Exception as e:
            fetch_fail.append((cat, str(e)[:120]))
            print(f'  [{i+1}/{len(sample)}] {cat}: FETCH_FAIL {type(e).__name__}')
            # 不写 state，下次续跑重试
            time.sleep(POLITE)
            continue

        per_field = {}
        for field in SPEC_RE:
            jv = rec.get(field)
            lv = live.get(field)
            cls = classify(jv, lv)
            per_field[field] = {
                'jsonl': norm(jv), 'live': lv or '', 'class': cls}
            if cls not in ('MATCH', 'BOTH_EMPTY'):
                root_counter[cls] += 1
        result['fields'] = per_field
        # 记录级主因（优先 DOM_ERR / JUNK）
        classes = [v['class'] for v in per_field.values()]
        if 'SCRAPER_DOM_ERR' in classes:
            result['outcome'] = 'SCRAPER_DOM_ERR'
        elif 'SCRAPER_JUNK' in classes:
            result['outcome'] = 'SCRAPER_JUNK'
        elif 'OVER_EXTRACTED' in classes:
            result['outcome'] = 'OVER_EXTRACTED'
        elif 'UNDER_EXTRACTED' in classes:
            result['outcome'] = 'UNDER_EXTRACTED'
        elif 'MISMATCH_AMBIG' in classes:
            result['outcome'] = 'MISMATCH_AMBIG'
        elif 'MATCH' in classes:
            result['outcome'] = 'MATCH'
        else:
            result['outcome'] = 'BOTH_EMPTY'
        state[cat] = result
        rec_summary.append(result)
        print(f'  [{i+1}/{len(sample)}] {cat}: {result["outcome"]}')

        # 逐字段明细行（仅输出非 MATCH/BOTH_EMPTY，便于审查；MATCH 也抽样保留）
        for field in SPEC_RE:
            pf = per_field[field]
            if pf['class'] in ('MATCH', 'BOTH_EMPTY'):
                continue
            rows.append({
                'catalog_no': cat, 'product_name': rec.get('product_name'),
                'reason': reason, 'field': field,
                'jsonl_val': pf['jsonl'], 'live_val': pf['live'],
                'class': pf['class'],
            })
        time.sleep(POLITE + random.uniform(0, 2.5))

    json.dump(state, open(STATE, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)

    # ---- 汇总 ----
    print('\n==== 根因分类（逐字段，排除 MATCH/BOTH_EMPTY）====')
    for k, c in root_counter.most_common():
        print(f'  {k:20s} {c}')
    print(f'  FETCH_FAIL (待二次重跑): {len(fetch_fail)}')
    if fetch_fail:
        for c, e in fetch_fail[:10]:
            print(f'    {c}: {e}')

    # ---- 写 CSV（逐字段明细）----
    with open(OUT_CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['catalog_no', 'product_name', 'reason', 'field',
                    'jsonl_val', 'live_val', 'class'])
        for r in rows:
            w.writerow([r['catalog_no'], r['product_name'], r['reason'],
                        r['field'], r['jsonl_val'], r['live_val'], r['class']])

    # ---- 写 MD ----
    lines = []
    lines.append('# jena 规格字段「抽样回抓」根因校验报告（step 2b）\n')
    lines.append(f'> 对照源：每条记录的 `source_url`（Jena 官网产品页）  ')
    lines.append(f'> 样本：{len(sample)} 条（已知污染 {len(sample)-sum(1 for _,r in sample if r=="clean_baseline")} + 干净基线 {sum(1 for _,r in sample if r=="clean_baseline")}）  ')
    lines.append(f'> 模式：{"PoC（小样本验证）" if poc else "full（已知污染+基线）"}  ')
    lines.append(f'> crawled_at 约 2026-06-28；live 为当前抓取，差异可能含源头 drift。  ')
    lines.append(f'> **本项目只找原因，不修改任何数据。**\n')
    lines.append('## 根因分类汇总（逐字段）\n')
    lines.append('| 根因 | 计数 | 含义 |')
    lines.append('|------|-----:|------|')
    meaning = {
        'SCRAPER_DOM_ERR': 'jsonl 是 junk（散文/导航词），live 合法值 → 爬虫抓错 DOM 节点（确凿）',
        'SCRAPER_JUNK': 'jsonl 是 junk（散文/导航词），live 无此字段 → 爬虫抽到 junk 内容（错内容抽取）',
        'OVER_EXTRACTED': 'jsonl 有值、live 无 → 爬虫多抽（或源头已删该字段）',
        'UNDER_EXTRACTED': 'live 有值、jsonl 空 → 爬虫漏抽',
        'MISMATCH_AMBIG': '双方均合法但不同 → 爬虫错或源头 drift，需原始 HTML/PDF 定',
        'SOURCE_URL_OUTLIER': 'source_url 指向非 jena 产品页（springer 等），本身数据质量问题',
    }
    for k, c in root_counter.most_common():
        lines.append(f'| {k} | {c} | {meaning.get(k, "")} |')
    lines.append(f'| FETCH_FAIL | {len(fetch_fail)} | 抓取失败（VPN/限频），需断点续跑补 |')
    lines.append('\n## 记录级主因\n')
    for r in rec_summary:
        note = r.get('note', '')
        lines.append(f'- `{r["catalog_no"]}` [{r["reason"]}] → **{r["outcome"]}** {("— "+note) if note else ""}')
    lines.append('\n## 逐字段明细（仅非 MATCH/BOTH_EMPTY）\n')
    lines.append('| catalog_no | field | jsonl 值 | live 值 | 分类 |')
    lines.append('|-----------|-------|---------|---------|------|')
    for r in rows:
        j = r['jsonl_val'].replace('|', '/')[:50]
        lv = r['live_val'].replace('|', '/')[:50]
        lines.append(f"| {r['catalog_no']} | {r['field']} | {j} | {lv} | {r['class']} |")

    with open(OUT_MD, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f'\n[out] {OUT_MD}')
    print(f'[out] {OUT_CSV}')


if __name__ == '__main__':
    main()
