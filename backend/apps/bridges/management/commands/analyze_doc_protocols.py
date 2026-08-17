"""只读分析：用 D:\\试剂产品说明文档 的官方用途陈述，给各产品的已关联 Protocol 打分排名，
与当前 featured/display_order 及 Bioz 方案对比。不写库。

用法:
  DB_ENGINE=sqlite python manage.py analyze_doc_protocols
"""
import json, os, re, sys
from collections import Counter
from django.core.management.base import BaseCommand


STOP = set("""a an the of for and or to in on with is are be as at by from into used use using
can may this that these those it its their our your we you they which what when where how
based via per its are was were has have had been being will would could should also such
other each both one two three first second new novel modified chemical product substrate
nucleotide triphosphate analog dye labeled labelling label containing contains contain
""".split())

APP_VOCAB = ['label', 'click', 'seq', 'rna', 'dna', 'cdna', 'fish', 'microarray', 'imaging',
             'ivt', 'transcription', 'probing', 'detect', 'probe', 'capture', 'amplify',
             'pcr', 'hybridiz', 'extension', 'incorporat', 'structure', 'assay', 'stain']


def stem(t):
    if len(t) <= 4:
        return t
    for suf in ('ing', 'ed', 'ly'):
        if t.endswith(suf):
            return t[:-len(suf)]
    if t.endswith('s') and not t.endswith('ss'):
        return t[:-1]
    return t

def tokenize(text):
    if not text:
        return set()
    toks = re.findall(r"[a-z0-9][a-z0-9\+\-]{1,}", text.lower())
    out = set()
    for t in toks:
        if t in STOP or len(t) <= 2:
            continue
        # 英式/美式拼写归一
        t = t.replace('labelling', 'label').replace('labelling', 'label')
        out.add(stem(t))
    return out


class Command(BaseCommand):
    help = 'Cross-reference product spec docs with DB protocol associations (read-only)'

    def handle(self, *args, **opts):
        BASE = r'D:\试剂产品说明文档'
        json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))), 'docx_products.json')
        if not os.path.exists(json_path):
            self.stderr.write(f'ERROR: {json_path} not found. Run docx_extract.py first.')
            return
        records = json.load(open(json_path, encoding='utf-8'))
        by_catalog = {r['catalog']: r for r in records if r['catalog']}

        from apps.commerce.models import Product
        from apps.bridges.models import ProductMethod, MethodProtocol
        from apps.knowledge.models import Protocol, Method

        # 只读取产品 id + catalog（绕开 archived 列）
        prods = list(Product.objects.values('id', 'catalog_no', 'name'))
        cat_to_pid = {}
        for p in prods:
            cn = (p['catalog_no'] or '').strip()
            if cn:
                cat_to_pid[cn] = p['id']

        mapped = [c for c in by_catalog if c in cat_to_pid]
        self.stdout.write(f"文档总数: {len(by_catalog)} | DB 产品总数: {len(prods)} | 文档↔DB 命中: {len(mapped)}")

        # 预载 protocol + method 语料
        prot_cache = {}
        method_cache = {}

        def get_prot(pid):
            if pid not in prot_cache:
                row = Protocol.objects.filter(id=pid).values('id', 'name', 'objective',
                                                             'reagents', 'materials', 'method_id').first()
                prot_cache[pid] = row
            return prot_cache[pid]

        def get_method(mid):
            if mid not in method_cache:
                method_cache[mid] = Method.objects.filter(id=mid).values('id', 'name').first()
            return method_cache[mid]

        total_assoc = 0
        overlap_ge2 = 0
        zero_overlap = 0
        per_product = []
        for cat in mapped:
            pid = cat_to_pid[cat]
            doc = by_catalog[cat]
            doc_tokens = tokenize(doc['usage']) | tokenize(doc['name'])
            # 当前关联协议
            method_ids = list(ProductMethod.objects.filter(product_id=pid).values_list('method_id', flat=True))
            proto_ids = list(MethodProtocol.objects.filter(method_id__in=method_ids)
                             .values_list('protocol_id', flat=True).distinct())
            scored = []
            for prid in proto_ids:
                pr = get_prot(prid)
                if not pr:
                    continue
                m = get_method(pr['method_id']) or {}
                mname = (m.get('name') or '')
                corpus = ' '.join([pr['name'] or '', pr['objective'] or '', pr['reagents'] or '',
                                   pr['materials'] or '', mname])
                p_tokens = tokenize(corpus)
                ov = len(doc_tokens & p_tokens)
                prot_blob = (pr['name'] or '') + ' ' + (pr['objective'] or '') + ' ' + mname
                prot_blob_l = prot_blob.lower()
                app_hits = sum(1 for v in APP_VOCAB if v in prot_blob_l)
                scored.append({'pid': prid, 'name': pr['name'], 'method': mname, 'ov': ov, 'app': app_hits})
            total_assoc += len(scored)
            for s in scored:
                if s['ov'] >= 2:
                    overlap_ge2 += 1
                else:
                    zero_overlap += 1
            scored.sort(key=lambda s: (-s['ov'], -s['app']))
            per_product.append((cat, doc, scored))

        self.stdout.write(f"关联协议总数(命中产品): {total_assoc}")
        if total_assoc:
            self.stdout.write(f"  doc 重叠≥2 (相关): {overlap_ge2} ({100*overlap_ge2/total_assoc:.1f}%)")
            self.stdout.write(f"  doc 重叠<2 (疑似无关): {zero_overlap} ({100*zero_overlap/total_assoc:.1f}%)")

        # 样本：doc 用法 → 当前 Top doc 排名 vs 现状
        self.stdout.write("\n========== 样本：文档用途 → doc 相关性排名(前5) ==========")
        shown = 0
        for cat, doc, scored in per_product:
            if shown >= 12:
                break
            if not scored:
                continue
            shown += 1
            self.stdout.write(f"\n■ {cat} {doc['name']}")
            self.stdout.write(f"  用法: {doc['usage'][:140]}")
            self.stdout.write(f"  当前关联 {len(scored)} 协议, doc相关(≥2) {sum(1 for s in scored if s['ov']>=2)} 个")
            for s in scored[:5]:
                flag = '✓' if s['ov'] >= 2 else '·'
                self.stdout.write(f"    {flag} ov={s['ov']:2d} [{s['method'][:18]:18s}] {s['name'][:52]}")
