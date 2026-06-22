"""全量产品知识资产扫描
遍历所有 109 个产品，运行三个工具，生成统计报告。
"""
import sys, os, json, time, csv
from datetime import datetime
from collections import Counter, defaultdict

sys.path.insert(0, r'E:\scireagent-tencent\backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
os.environ['DB_ENGINE'] = 'sqlite'
os.environ['BIOPROCORPUS_DIR'] = r'E:\scireagent-tencent\backend\data\bioprocorpus'
sys.stdout.reconfigure(encoding='utf-8')

import django; django.setup()
from apps.commerce.models import Product
from apps.commerce.services.validators.product_validator import ProductValidator
from apps.knowledge.services.literature_recommender import LiteratureRecommender
from apps.knowledge.services.protocol_recommender import (
    ProtocolRecommender, BioProCorpusIndexer, ProtocolRetriever,
)

# ── 初始化 ──
print('=' * 65)
print('  全量产品知识资产扫描')
print(f'  开始时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print('=' * 65)

validator = ProductValidator()
lit_recommender = LiteratureRecommender()

# 初始化 BioProCorpus 推荐器
indexer = BioProCorpusIndexer(data_dir=os.environ['BIOPROCORPUS_DIR'])
indexer.build()
print(f'\n  BioProCorpus 索引: {indexer.size()} 篇协议')
proto_recommender = ProtocolRecommender(retriever=ProtocolRetriever(indexer=indexer))

products = list(Product.objects.all().order_by('id'))
print(f'  产品总数: {len(products)}')
print()

# ── 统计指标 ──
stats = {
    "total": len(products),
    "has_cas": 0,
    "has_smiles": 0,
    "has_both": 0,
    "pubchem_found": 0,
    "pubchem_match": 0,
    "pubchem_mismatch": 0,
    "has_literature": 0,
    "has_protocol": 0,
    "total_literature_refs": 0,
    "total_protocols": 0,
    "by_category": Counter(),
    "by_literature_count": Counter(),
    "by_protocol_count": Counter(),
    "mismatch_details": [],
    "top_applications": Counter(),
    "top_methods": Counter(),
}

# ── 逐产品扫描 ──
results = []
for idx, product in enumerate(products):
    if (idx + 1) % 20 == 0:
        print(f'  进度: {idx+1}/{len(products)} ({datetime.now().strftime("%H:%M:%S")})')

    row = {
        "id": product.id,
        "name": product.name,
        "cas": product.cas or "",
        "smiles": bool(product.smiles),
        "category": product.category_l1 or "",
    }

    # 基础统计
    if product.cas:
        stats["has_cas"] += 1
    if product.smiles:
        stats["has_smiles"] += 1
    if product.cas and product.smiles:
        stats["has_both"] += 1
    stats["by_category"][product.category_l1 or "uncategorized"] += 1

    # ── 工具一：产品校验器 ──
    try:
        report = validator.validate(product)
        row["pubchem_cid"] = report.pubchem_cid
        row["pubchem_match"] = report.pubchem_match
        row["mismatches"] = report.mismatches

        if report.pubchem_cid:
            stats["pubchem_found"] += 1
            if report.pubchem_match:
                stats["pubchem_match"] += 1
            else:
                stats["pubchem_mismatch"] += 1
                stats["mismatch_details"].append({
                    "id": product.id, "name": product.name,
                    "fields": report.mismatches,
                })
    except Exception as e:
        row["pubchem_error"] = str(e)

    # ── 工具三：文献推荐器（重写为直接调用 PubMed 多策略） ──
    try:
        lit_result = lit_recommender.recommend(product, top_k=5)
        refs = lit_result.get("references", [])
        apps = lit_result.get("applications", [])
        methods = lit_result.get("methods", [])
        row["literature_count"] = len(refs)
        row["applications"] = apps
        row["methods"] = methods
        row["refs"] = [{"pmid": r["pmid"], "title": r["title"][:60]} for r in refs[:3]]

        if refs:
            stats["has_literature"] += 1
            stats["total_literature_refs"] += len(refs)
            stats["by_literature_count"][len(refs)] += 1
            for a in apps:
                stats["top_applications"][a] += 1
            for m in methods:
                stats["top_methods"][m] += 1
    except Exception as e:
        row["literature_error"] = str(e)

    # ── 工具二：BioProCorpus 推荐器 ──
    try:
        proto_result = proto_recommender.recommend(product.name, top_k=3)
        row["protocol_count"] = len(proto_result)
        row["protocols"] = [{"title": p["protocol"]["title"][:60], "score": p["relevance_score"]}
                           for p in proto_result[:2]]

        if proto_result:
            stats["has_protocol"] += 1
            stats["total_protocols"] += len(proto_result)
            stats["by_protocol_count"][len(proto_result)] += 1
    except Exception as e:
        row["protocol_error"] = str(e)

    # PubMed 限速
    time.sleep(0.5)
    results.append(row)

# ── 报告生成 ──
print()
print('=' * 65)
print('  📊 扫描统计报告')
print('=' * 65)
print(f'''
  产品总数:             {stats["total"]}
  有 CAS 号:            {stats["has_cas"]} ({stats["has_cas"]/stats["total"]*100:.0f}%)
  有 SMILES:            {stats["has_smiles"]} ({stats["has_smiles"]/stats["total"]*100:.0f}%)
  两者都有:             {stats["has_both"]} ({stats["has_both"]/stats["total"]*100:.0f}%)
''')

print('  ── 产品校验器 (PubChem) ──')
print(f'  PubChem 查到:      {stats["pubchem_found"]}')
print(f'  SMILES 一致:       {stats["pubchem_match"]}')
print(f'  SMILES 不一致:     {stats["pubchem_mismatch"]}')

if stats["pubchem_mismatch"] > 0:
    print(f'  差异字段统计:')
    field_counter = Counter()
    for d in stats["mismatch_details"]:
        for f in d["fields"]:
            field_counter[f] += 1
    for f, c in field_counter.most_common():
        print(f'    {f}: {c} 个产品')

print()
print('  ── 文献推荐器 (PubMed) ──')
print(f'  找到文献的产品:   {stats["has_literature"]} ({stats["has_literature"]/stats["total"]*100:.0f}%)')
print(f'  总文献数:         {stats["total_literature_refs"]}')
if stats["has_literature"] > 0:
    print(f'  平均每产品:       {stats["total_literature_refs"]/stats["has_literature"]:.1f} 篇')
print(f'  文献数分布:       {dict(sorted(stats["by_literature_count"].items()))}')
print()
print(f'  提取的应用场景 Top 10:')
for app, count in stats["top_applications"].most_common(10):
    print(f'    {app}: {count}')
print()
print(f'  提取的实验方法 Top 10:')
for method, count in stats["top_methods"].most_common(10):
    print(f'    {method}: {count}')

print()
print('  ── 协议推荐器 (BioProCorpus) ──')
print(f'  匹配到协议的产品: {stats["has_protocol"]} ({stats["has_protocol"]/stats["total"]*100:.0f}%)')
print(f'  总协议匹配数:     {stats["total_protocols"]}')
if stats["has_protocol"] > 0:
    print(f'  平均每产品:       {stats["total_protocols"]/stats["has_protocol"]:.1f} 条')
print(f'  协议数分布:       {dict(sorted(stats["by_protocol_count"].items()))}')

# ── 分类覆盖率 ──
print()
print('  ── 分类覆盖 ──')
for cat, count in stats["by_category"].most_common():
    lit_count = sum(1 for r in results if r.get("literature_count", 0) > 0 and r["category"] == cat)
    print(f'  {cat}: {count} 个产品, {lit_count} 个有文献 ({lit_count/count*100:.0f}%)')

# ── 问题产品 ──
print()
print('  ── 需要关注的产品 ──')
# 无 CAS + 无 SMILES + 无文献
needy = [r for r in results if not r.get("literature_count") and not r.get("pubchem_cid")]
print(f'  PubChem 查不到 + 无文献: {len(needy)} 个')
for r in needy[:10]:
    print(f'    [{r["id"]}] {r["name"]}')

print()
print(f'  扫描完成: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

# ── 导出为 JSON ──
output_path = r'E:\scireagent-tencent\backend\data\scan_report.json'
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump({"stats": dict(stats), "results": results}, f, ensure_ascii=False, indent=2)
print(f'\n  报告已导出: {output_path}')
print('=' * 65)
