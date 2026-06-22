"""通过 PubChem 灵活名称搜索补全缺失数据"""
import sys, os, time, requests
sys.path.insert(0, r'E:\scireagent-tencent\backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
os.environ['DB_ENGINE'] = 'sqlite'
sys.stdout.reconfigure(encoding='utf-8')
import django; django.setup()
from apps.commerce.models import Product

base = 'https://pubchem.ncbi.nlm.nih.gov/rest/pug'
zero_ids = [23, 24, 25, 26, 29, 39, 41, 47, 48, 49, 51, 52, 58, 59, 64, 65, 81, 87, 88, 94, 108, 109, 110, 116, 117]

products = Product.objects.filter(id__in=zero_ids)
found = 0
for p in products:
    # 生成多个候选搜索名
    names = []
    clean = p.name.replace("'", "").replace('"', "").replace("`", "").replace("(1)", "").strip()
    names.append(clean)
    # 去掉修饰前缀
    import re
    simpler = re.sub(r"^[\d]'-|^[\d]-", "", clean).strip(" -").strip("-")
    if simpler != clean:
        names.append(simpler)
    # 取核心词
    parts = clean.replace("-", " ").split()
    if len(parts) > 1:
        names.append(" ".join(parts[-3:]))
    names = list(set(n for n in names if len(n) > 3))

    for name in names:
        try:
            url = f'{base}/compound/name/{name}/cids/JSON'
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                cids = r.json().get("IdentifierList", {}).get("CID", [])
                if cids:
                    cid = cids[0]
                    # 获取 SMILES
                    purl = f'{base}/compound/cid/{cid}/property/CanonicalSMILES,IsomericSMILES,MolecularFormula/JSON'
                    r2 = requests.get(purl, timeout=10)
                    if r2.status_code == 200:
                        props = r2.json()["PropertyTable"]["Properties"][0]
                        sm = props.get("CanonicalSMILES") or props.get("IsomericSMILES", "")
                        mf = props.get("MolecularFormula", "")
                        if sm and not p.smiles:
                            p.smiles = sm
                            p.save(update_fields=['smiles'])
                            found += 1
                            print(f'[{p.id}] {p.name}: CID={cid} SMILES={sm[:60]}...')
                        elif sm:
                            print(f'[{p.id}] {p.name}: CID={cid} 已有 SMILES')
                        else:
                            print(f'[{p.id}] {p.name}: CID={cid} 无 SMILES')
                    break
        except Exception:
            pass
        time.sleep(0.3)
    else:
        print(f'[{p.id}] {p.name}: ❌ 所有名称均未找到')

print(f'\n补全: {found} 个产品新增了 SMILES')
