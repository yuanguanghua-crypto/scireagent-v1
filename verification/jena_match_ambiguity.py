"""验使用链路：用真实 jena 数据量化 find_by_name 双向子串匹配的歧义/过松风险。

零依赖复刻：生产 jena_index.find_by_name (lines 174-187) 逻辑逐字一致：
    name_lower = name.strip().lower()
    exact, partial = [], []
    for r in self._records:
        pn = r.product_name.lower()
        if pn == name_lower: exact.append(r)
        elif name_lower in pn or pn in name_lower: partial.append(r)
    return exact + partial[:max(0, limit - len(exact))]
只读：从 jsonl 加载，不改任何数据/代码。
"""
import json, re

JSONL = r"C:/Users/yuankaifeng/WorkBuddy/2026-07-08-11-22-32/src_claude/backend/data/jena/jena_products_v2.jsonl"

# ---- 加载（复刻 JenaIndex 的 _records：product_name + catalog_no）----
records = []
with open(JSONL, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        pn = (d.get("product_name") or "").strip()
        cat = (d.get("jena_catalog_no") or "").strip()
        if pn:
            records.append((pn, cat))
N = len(records)
print("LOADED records:", N)


def find_by_name(name, limit=5):
    """逐字复刻 jena_index.find_by_name 的生产逻辑。"""
    if not name:
        return []
    name_lower = name.strip().lower()
    exact, partial = [], []
    for pn, cat in records:
        pn_l = pn.lower()
        if pn_l == name_lower:
            exact.append((pn, cat))
        elif name_lower in pn_l or pn_l in name_lower:
            partial.append((pn, cat))
    return exact + partial[:max(0, limit - len(exact))]


# 1) 歧义查询：短通用名（极容易作为子串命中多个产品）
queries = ["ATP","dATP","EDTA","Tris","UTP","GTP","CTP","Buffer","Water","Salt",
           "RNA","DNA","BSA","DTT","HEPES","PBS","Mg","PEG","Thiol","Oligo","dNTP"]
print("\n=== A. 歧义测试：find_by_name(limit=10) 对短通用名 ===")
for q in queries:
    res = find_by_name(q, limit=10)
    if res:
        print(f"Q={q!r}: {len(res)} 命中, 首条={res[0][0]!r}({res[0][1]})")
        if len(res) > 1:
            print("   全部候选:", [f"{pn}/{cat}" for pn, cat in res[:8]])

# 2) 系统性歧义：遍历所有 name，统计"查询自身名返回>1候选"的比例
multi = 0
examples = []
for pn, cat in records:
    res = find_by_name(pn, limit=5)
    if len(res) > 1:
        multi += 1
        if len(examples) < 15:
            others = [x[0] for x in res if x[0] != pn]
            examples.append((pn, others[:3]))
print(f"\n=== B. 遍历 {N} 条：查询自身名返回>1候选的有 {multi} 条 ({multi*100//N}%) ===")
for nm, others in examples:
    print(f"  {nm!r} 也会误命中: {others}")

# 3) 危险：单 query 命中多个不同 catalog（matcher 取首条=潜在错配）
print("\n=== C. 高风险：单 query 命中多 catalog 多产品（取首条=错配风险）===")
danger = []
for q in queries:
    res = find_by_name(q, limit=10)
    cats = {cat for _, cat in res}
    if len(cats) > 1:
        danger.append((q, res))
for q, lst in danger:
    print(f"  {q!r}: {[(pn, cat) for pn, cat in lst]}")

# 4) matcher 实际取首条（limit=1）在歧义时的脆弱性
print("\n=== D. matcher 实际取首条（limit=1）演示 ===")
for q in ["ATP","dATP","UTP","Buffer","EDTA","Salt","Water"]:
    res = find_by_name(q, limit=1)
    if res:
        print(f"  matcher 对 {q!r} 返回: {res[0][0]!r} ({res[0][1]})")
