"""PubMed 搜索测试：查询产品在文献中的应用"""
import sys, os, json, time
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'E:\scireagent-tencent\backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
os.environ['DB_ENGINE'] = 'sqlite'
import django; django.setup()
from apps.commerce.models import Product
import requests

PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

def search_pubmed(query: str, max_results: int = 10):
    """搜索 PubMed 并返回文章列表"""
    # 1. ESearch - 搜索
    search_url = f"{PUBMED_BASE}/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
        "sort": "relevance",
    }
    r = requests.get(search_url, params=params, timeout=15)
    data = r.json()
    id_list = data.get("esearchresult", {}).get("idlist", [])

    if not id_list:
        return []

    # 2. ESummary - 获取摘要
    summary_url = f"{PUBMED_BASE}/esummary.fcgi"
    params = {
        "db": "pubmed",
        "id": ",".join(id_list),
        "retmode": "json",
    }
    r = requests.get(summary_url, params=params, timeout=15)
    data = r.json()

    results = []
    for uid in id_list:
        entry = data.get("result", {}).get(uid, {})
        results.append({
            "pmid": uid,
            "title": entry.get("title", ""),
            "source": entry.get("source", ""),
            "pubdate": entry.get("pubdate", ""),
            "authors": [a.get("name", "") for a in entry.get("authors", [])[:3]],
            "elocationid": entry.get("elocationid", ""),
        })
    return results

# 测试产品列表
test_products = [
    {"name": "5-Ethynyl-dUTP", "query": "(5-Ethynyl-dUTP OR EdU) AND click chemistry"},
    {"name": "2'-Azido-dATP", "query": "(2-Azido-dATP OR azido-ATP) AND click chemistry"},
    {"name": "5-Propargylamino-CTP", "query": "(Propargylamino-CTP OR propargylamino nucleotide) AND labeling"},
    {"name": "Biotin-11-UTP", "query": "Biotin-UTP RNA labeling"},
    {"name": "Cy5-dUTP", "query": "Cy5-dUTP DNA labeling"},
]

print('=' * 70)
print('  PubMed 文献搜索测试')
print('=' * 70)

for tp in test_products:
    print()
    print(f'  产品: {tp["name"]}')
    print(f'  搜索词: {tp["query"]}')
    try:
        results = search_pubmed(tp["query"], max_results=5)
        print(f'  结果: {len(results)} 篇文献')
        for r in results:
            title = r["title"]
            if len(title) > 70:
                title = title[:67] + "..."
            print(f'    PMID {r["pmid"]} | {r["pubdate"]} | {title}')
            if r["authors"]:
                print(f'    作者: {", ".join(r["authors"][:2])} et al.')
        if len(results) == 0:
            print('    (空)')
    except Exception as e:
        print(f'  错误: {e}')
    time.sleep(0.5)  # NCBI 限速

print()
print('=' * 70)
print('  搜索完成')
print('=' * 70)
