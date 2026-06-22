"""分析扫描报告详情"""
import sys, json
sys.stdout.reconfigure(encoding='utf-8')
with open(r'E:\scireagent-tencent\backend\data\scan_report.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

results = data['results']

# SMILES 不匹配样本
print('=== SMILES 不匹配样本（前8个）===')
mismatches = [r for r in results if r.get('pubchem_match') == False and r.get('pubchem_cid')]
for r in mismatches[:8]:
    print('  [{id}] {name} | CID={cid} | fields={fields}'.format(
        id=r['id'], name=r['name'], cid=r['pubchem_cid'], fields=r['mismatches']))

print()

# 零数据产品
print('=== 零数据产品（25个）===')
zeros = [r for r in results if not r.get('literature_count') and not r.get('pubchem_cid')]
for r in zeros:
    print('  [{id}] {name} | CAS={cas} | smiles={smiles}'.format(
        id=r['id'], name=r['name'], cas=r['cas'] or '-', smiles='Y' if r['smiles'] else 'N'))

print()

# 文献统计
with_refs = [r for r in results if r.get('literature_count', 0) > 0]
print('=== 文献统计 ===')
print('有文献产品: {n} 个'.format(n=len(with_refs)))
print('总计文献: {n} 篇'.format(n=sum(r.get('literature_count',0) for r in results)))

# 输出所有有文献的产品和文献列表（用于导入）
print()
print('=== 文献明细（用于导入数据库）===')
for r in with_refs:
    print('--- PRODUCT:{id}:{name} ---'.format(id=r['id'], name=r['name']))
    for ref in r.get('refs', []):
        print('  PMID:{pmid} | {title}'.format(pmid=ref['pmid'], title=ref.get('title','')))
