import json

with open(r'C:\Users\55248.PC\WorkBuddy\2026-06-16-16-41-11\knowledge_graph_v3.json', encoding='utf-8') as f:
    data = json.load(f)

print('=== JSON 顶层键 ===')
for k in data:
    if k != 'metadata':
        print(f'  {k}: {len(data[k])} 条')

print()
print('=== 产品第一个示例 ===')
p = data['Product'][0]
print(f'  名称: {p["name"]}')
print(f'  catalog: {p["catalog_no"]}')
print(f'  CAS: {p.get("cas_no","")}')
print(f'  关联 protocols: {len(p.get("protocols",[]))}')
print(f'  关联 applications: {len(p.get("applications",[]))}')
print(f'  SKU 数: {len(p.get("skus",[]))}')

print()
print('=== SKU 示例 ===')
sku = data['SKU'][0]
print(f'  SKU: {sku}')
