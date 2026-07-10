"""离线产品数据质量分析（不依赖外部 API）"""
import sys, os, json
from collections import Counter

sys.path.insert(0, r'E:\scireagent-tencent\backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
os.environ['DB_ENGINE'] = 'sqlite'
os.environ['BIOPROCORPUS_DIR'] = r'E:\scireagent-tencent\backend\data\bioprocorpus'
sys.stdout.reconfigure(encoding='utf-8')

import django; django.setup()
from apps.commerce.models import Product, SKU
from apps.knowledge.models import Protocol, Method, Application, ResearchGoal, Reference

products = list(Product.objects.all().order_by('id'))
total = len(products)

# ── 1. 基础数据质量 ──
print('=' * 65)
print('  1. 产品基础数据质量')
print('=' * 65)

has_cas = sum(1 for p in products if p.cas)
has_smiles = sum(1 for p in products if p.smiles)
has_formula = sum(1 for p in products if p.formula)
has_mw = sum(1 for p in products if p.molecular_weight)
has_overview = sum(1 for p in products if p.overview)
has_synonyms = sum(1 for p in products if p.synonyms)
has_svg = sum(1 for p in products if p.structure_svg)
has_purity = sum(1 for p in products if p.purity)
has_storage = sum(1 for p in products if p.storage)

cats = Counter(p.category_l1 or 'uncategorized' for p in products)

print(f'''
  产品总数:           {total}
  有 CAS 号:          {has_cas:3d} ({has_cas/total*100:5.1f}%)
  有 SMILES:          {has_smiles:3d} ({has_smiles/total*100:5.1f}%)
  有分子式:           {has_formula:3d} ({has_formula/total*100:5.1f}%)
  有分子量:           {has_mw:3d} ({has_mw/total*100:5.1f}%)
  有产品描述:         {has_overview:3d} ({has_overview/total*100:5.1f}%)
  有同义词:           {has_synonyms:3d} ({has_synonyms/total*100:5.1f}%)
  有结构图:           {has_svg:3d} ({has_svg/total*100:5.1f}%)
  有纯度信息:         {has_purity:3d} ({has_purity/total*100:5.1f}%)
  有储存条件:         {has_storage:3d} ({has_storage/total*100:5.1f}%)
''')

print('  分类分布:')
for cat, n in cats.most_common():
    print(f'    {cat}: {n}')
print()

# ── 2. 已有知识链关联 ──
print('=' * 65)
print('  2. 已有知识链关联')
print('=' * 65)

# 检查 bridges
from apps.bridges.models import ProductMethod, MethodProtocol
from apps.commerce.models import Product
from apps.knowledge.models import Method, Protocol as KnowProtocol

pm_count = ProductMethod.objects.count()
mp_count = MethodProtocol.objects.count()
method_count = Method.objects.count()
protocol_count = KnowProtocol.objects.count()
ref_count = Reference.objects.count()

# 每个产品关联了多少 Method
product_method_links = Counter()
for pm in ProductMethod.objects.all():
    product_method_links[pm.product_id] += 1

products_with_methods = len(product_method_links)
avg_methods = sum(product_method_links.values()) / total if total > 0 else 0

print(f'''
  Method 总数:           {method_count}
  Protocol 总数:         {protocol_count}
  Reference 总数:        {ref_count}
  Product-Method 关联:   {pm_count}
  Method-Protocol 关联:  {mp_count}
  有关联 Method 的产品:  {products_with_methods} ({products_with_methods/total*100:.1f}%)
  平均每产品 Method 数:  {avg_methods:.2f}
''')

# 零关联产品
linked_product_ids = set(product_method_links.keys())
zero_link = [p for p in products if p.id not in linked_product_ids]
print(f'  零关联产品: {len(zero_link)} 个')
if zero_link:
    for p in zero_link[:10]:
        print(f'    [{p.id}] {p.name}')
    if len(zero_link) > 10:
        print(f'    ... 共 {len(zero_link)} 个')
print()

# ── 3. BioProCorpus 本地匹配 ──
print('=' * 65)
print('  3. BioProCorpus 本地协议匹配（离线）')
print('=' * 65)
from apps.knowledge.services.protocol_recommender import (
    BioProCorpusIndexer, ProtocolRetriever, ProtocolRecommender,
)

indexer = BioProCorpusIndexer(data_dir=os.environ['BIOPROCORPUS_DIR'])
indexer.build()
retriever = ProtocolRetriever(indexer=indexer)
recommender = ProtocolRecommender(retriever=retriever)

match_stats = Counter()
for p in products:
    recs = recommender.recommend(p.name, top_k=3)
    match_stats[len(recs)] += 1

print(f'  BioProCorpus 索引: {indexer.size()} 篇协议')
print(f'  匹配分布:')
for n in sorted(match_stats.keys()):
    print(f'    匹配 {n} 条: {match_stats[n]} 个产品 ({match_stats[n]/total*100:.1f}%)')
print()

# ── 4. 知识链缺口分析 ──
print('=' * 65)
print('  4. 知识链缺口分析')
print('=' * 65)

print(f'''
  完整度评级:
    A 级（有 Method + 有 CAS + 有 SMILES）: {sum(1 for p in products if p.id in linked_product_ids and p.cas and p.smiles)}
    B 级（有 Method + 有 CAS 或 SMILES）:   {sum(1 for p in products if p.id in linked_product_ids and (p.cas or p.smiles) and not (p.cas and p.smiles))}
    C 级（有 Method + 无 CAS 无 SMILES）:   {sum(1 for p in products if p.id in linked_product_ids and not p.cas and not p.smiles)}
    D 级（无 Method + 有 CAS 或 SMILES）:   {sum(1 for p in products if p.id not in linked_product_ids and (p.cas or p.smiles))}
    E 级（无 Method + 无 CAS 无 SMILES）:   {sum(1 for p in products if p.id not in linked_product_ids and not p.cas and not p.smiles)}
''')

# ── 5. 总结建议 ──
print('=' * 65)
print('  5. 总结与建议')
print('=' * 65)

print('''
  数据质量问题:
''')
if has_cas < total:
    print(f'    - {total - has_cas} 个产品缺少 CAS 号（影响 PubChem 校验和 PubMed 搜索）')
if has_smiles < total:
    print(f'    - {total - has_smiles} 个产品缺少 SMILES（影响结构校验）')
if not has_svg:
    print(f'    - 所有产品缺少结构图 SVG')
if zero_link:
    print(f'    - {len(zero_link)} 个产品没有任何 Method 关联')

print('''
  基础设施问题:
    - 企业网络代理阻止对外部 API（PubChem / PubMed / NCBI）的 HTTPS 访问
    - 影响：产品校验器和文献推荐器无法正常调用外部数据源
    - 解决：需要配置代理白名单或使用 VPN

  下一步建议:
    1. 修复网络代理问题后再跑全量 PubChem + PubMed 扫描
    2. 优先补全 CAS 号和 SMILES（当前分别缺 {miss_cas}% 和 {miss_smiles}%）
    3. 补全零关联产品的 Method 关联
'''.format(miss_cas=(total-has_cas)/total*100, miss_smiles=(total-has_smiles)/total*100))
