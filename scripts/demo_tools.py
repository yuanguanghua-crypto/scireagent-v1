"""三个工具完整演示"""
import sys, os

# 配置
BIOPROCORPUS = r'E:\scireagent-tencent\backend\data\bioprocorpus'
sys.path.insert(0, r'E:\scireagent-tencent\backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
os.environ['DB_ENGINE'] = 'sqlite'
os.environ['BIOPROCORPUS_DIR'] = BIOPROCORPUS
sys.stdout.reconfigure(encoding='utf-8')

import django; django.setup()
from apps.commerce.models import Product
from apps.commerce.services.validators.product_validator import ProductValidator
from apps.knowledge.services.protocol_recommender import (
    ProtocolRecommender, BioProCorpusIndexer, ProtocolRetriever,
)
from apps.knowledge.services.dvr_agent import DVRProtocolAgent

# 选产品 - 选一个既有CAS又有SMILES的
product = Product.objects.filter(cas__gt='', smiles__gt='').first()

print('=' * 70)
print('  产品: [{id}] {name}'.format(id=product.id, name=product.name))
print('  CAS: {cas}'.format(cas=product.cas))
print('  分类: {cat}'.format(cat=product.category_l1))
print()
print('  【工具一：产品校验器】')
print('  ─────────────────────────────────────────────────────')
validator = ProductValidator()
report = validator.validate(product)
print('   PubChem 查询: CID={cid}'.format(cid=report.pubchem_cid))
print('   SMILES 一致性: {status}'.format(
    status='一致' if report.pubchem_match else '不一致（差异字段: {m}）'.format(m=report.mismatches)))
print()
print('  【工具二：方案推荐器】')
print('  ─────────────────────────────────────────────────────')
# 手动构建索引后再检索
indexer = BioProCorpusIndexer(data_dir=BIOPROCORPUS)
indexer.build()
retriever = ProtocolRetriever(indexer=indexer)
recommender = ProtocolRecommender(retriever=retriever)

for term in [product.name, 'click chemistry', 'CuAAC', 'nucleotide']:
    recs = recommender.recommend(term, top_k=2)
    if recs:
        print('   搜索 "{t}": 找到 {n} 条'.format(t=term, n=len(recs)))
        for r in recs:
            t = r['protocol']['title']
            if len(t) > 60:
                t = t[:57] + '...'
            print('     [{s:.1f}] {title}'.format(s=r['relevance_score'], title=t))
    else:
        print('   搜索 "{t}": 无匹配'.format(t=term))
print()
print('  【工具三：DVR 知识链填充器】')
print('  ─────────────────────────────────────────────────────')
agent = DVRProtocolAgent()
result = agent.generate(product)
print('   迭代: {it} 次 | 最终状态: {st} | 通过: {ok}'.format(
    it=result.iterations, st=result.final_state,
    ok='是' if result.passed else '否（需审核）'))
if result.protocol:
    steps = result.protocol.get('steps', [])
    print('   生成了 {n} 条步骤:'.format(n=len(steps)))
    for i, s in enumerate(steps):
        print('     {i}. {step}'.format(i=i+1, step=s))
print()
print('=' * 70)
print('  演示完成')
print('=' * 70)
