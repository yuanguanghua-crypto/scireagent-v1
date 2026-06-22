"""快速测试三个工具"""
import sys, os
sys.path.insert(0, r'E:\scireagent-tencent\backend')
sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
os.environ['DB_ENGINE'] = 'sqlite'

import django
django.setup()

from apps.commerce.models import Product
from apps.commerce.services.validators.product_validator import ProductValidator
from apps.knowledge.services.protocol_recommender import ProtocolRecommender
from apps.knowledge.services.dvr_agent import DVRProtocolAgent

product = Product.objects.filter(cas__gt='', smiles__gt='').first()
pad = lambda s, n: s + ' ' * (n - len(s))

# ── 工具一 ──
print('=' * 65)
print('                       工具一：产品校验器')
print('=' * 65)
print(f'  产品: [{product.id}] {product.name}')
print(f'  CAS: {product.cas}')
print(f'  SMILES: {product.smiles}')
validator = ProductValidator()
report = validator.validate(product)
print(f'  PubChem CID: {report.pubchem_cid}')
print(f'  SMILES 匹配: {"匹配" if report.pubchem_match else "不匹配"}')
print(f'  不匹配字段: {report.mismatches}')
print(f'  协议匹配数: {len(report.matched_protocols)}')
print(f'  总体判定: {"一致" if report.overall_match else "需关注"}')
print()

# ── 工具二 ──
print('=' * 65)
print('                       工具二：方案推荐器')
print('=' * 65)
recommender = ProtocolRecommender()
recs = recommender.recommend(product.name, top_k=3)
if recs:
    for i, r in enumerate(recs):
        print(f'  {i+1}. {r["protocol"]["title"]}')
        print(f'     相关度: {r["relevance_score"]:.2f}')
        print(f'     来源: {r["match_reason"]}')
else:
    print('  (暂无匹配协议 - 需先运行 BioProCorpus 索引构建)')
print()

# ── 工具三 ──
print('=' * 65)
print('                       工具三：DVR知识链填充器')
print('=' * 65)
agent = DVRProtocolAgent()
result = agent.generate(product)
print(f'  迭代次数: {result.iterations}')
print(f'  最终状态: {result.final_state}')
print(f'  是否通过: {"通过" if result.passed else "未通过"}')
print(f'  需人工审核: {"是" if result.need_review else "否"}')
if result.protocol:
    print(f'  生成步骤 ({len(result.protocol.get("steps", []))} 条):')
    for i, s in enumerate(result.protocol.get('steps', [])):
        print(f'    {i+1}. {s}')
print()
print('=' * 65)
print('                        测试完成')
print('=' * 65)
