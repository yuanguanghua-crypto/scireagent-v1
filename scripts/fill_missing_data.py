"""补全零数据产品的 CAS/SMILES（通过 PubChem 名称搜索）"""
import sys, os, time, json
sys.path.insert(0, r'E:\scireagent-tencent\backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
os.environ['DB_ENGINE'] = 'sqlite'
sys.stdout.reconfigure(encoding='utf-8')
import django; django.setup()
from apps.commerce.models import Product
import requests

PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

# 零数据产品列表
zero_product_ids = [23, 24, 25, 26, 29, 39, 41, 47, 48, 49, 51, 52,
                    58, 59, 64, 65, 81, 87, 88, 94, 108, 109, 110, 116, 117]

products = Product.objects.filter(id__in=zero_product_ids)
print('=== 补全缺失 CAS/SMILES ===')
print(f'需处理: {len(products)} 个产品\n')

found = 0
for p in products:
    # 清理产品名用于搜索
    name = p.name.replace("'", "").replace('"', "").replace("`", "")
    # 去掉 (1) 后缀
    name = name.replace('(1)', '').replace('(1)', '').strip()

    print(f'  [{p.id}] {p.name}')

    # 尝试从 Pug REST 按名称搜索
    url = f"{PUBCHEM_BASE}/compound/name/{name}/cids/JSON"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            data = r.json()
            cids = data.get("IdentifierList", {}).get("CID", [])
            if cids:
                cid = cids[0]
                # 获取属性
                prop_url = f"{PUBCHEM_BASE}/compound/cid/{cid}/property/MolecularFormula,MolecularWeight,CanonicalSMILES,IsomericSMILES/JSON"
                r2 = requests.get(prop_url, timeout=15)
                if r2.status_code == 200:
                    props = r2.json()["PropertyTable"]["Properties"][0]
                    sm = props.get("CanonicalSMILES") or props.get("IsomericSMILES", "")
                    mf = props.get("MolecularFormula", "")
                    mw = props.get("MolecularWeight", 0)

                    updates = []
                    if not p.smiles and sm:
                        p.smiles = sm
                        updates.append(f'SMILES')
                    if not p.cas:
                        # 按 CID 查 CAS
                        cas_url = f"{PUBCHEM_BASE}/compound/cid/{cid}/property/InChIKey/JSON"
                        r3 = requests.get(cas_url, timeout=15)
                        if r3.status_code == 200:
                            pass  # CAS 需要额外查询

                    if updates:
                        p.save(update_fields=['smiles'] if len(updates) == 1 and 'SMILES' in updates else None)
                        found += 1
                        print(f'    ✅ CID={cid} | SMILES={sm[:50]}... | MF={mf}')
                    else:
                        print(f'    ⚠️  CID={cid}，但无缺失字段')
                else:
                    print(f'    ❌ 属性查询失败')
        elif r.status_code == 404:
            print(f'    ❌ PubChem 未找到')
        else:
            print(f'    ❌ HTTP {r.status_code}')
    except Exception as e:
        print(f'    ❌ 错误: {type(e).__name__}')
    time.sleep(0.5)

print(f'\n补全完成: {found}/{len(products)} 个产品新增了数据')
