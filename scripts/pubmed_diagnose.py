"""PubMed 搜索策略诊断"""
import sys, requests, json
sys.stdout.reconfigure(encoding='utf-8')
base = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils'

tests = [
    ("名称精确搜索", {'db': 'pubmed', 'term': '"5-Ethynyl-dUTP"', 'retmax': 5, 'retmode': 'json'}),
    ("名称宽泛搜索", {'db': 'pubmed', 'term': '5-Ethynyl-dUTP', 'retmax': 5, 'retmode': 'json'}),
    ("EdU 搜索", {'db': 'pubmed', 'term': 'EdU click chemistry', 'retmax': 5, 'retmode': 'json'}),
    ("名称+CAS", {'db': 'pubmed', 'term': '5-Ethynyl-dUTP AND 111289-87-3', 'retmax': 5, 'retmode': 'json'}),
    ("Azido 搜索", {'db': 'pubmed', 'term': '2-Azido-dUTP', 'retmax': 5, 'retmode': 'json'}),
    ("Propargylamino", {'db': 'pubmed', 'term': 'Propargylamino-CTP', 'retmax': 5, 'retmode': 'json'}),
    ("Biotin-UTP", {'db': 'pubmed', 'term': 'Biotin-UTP labeling', 'retmax': 5, 'retmode': 'json'}),
]

for label, params in tests:
    r = requests.get(f'{base}/esearch.fcgi', params=params, timeout=15)
    data = r.json()
    ids = data.get('esearchresult', {}).get('idlist', [])
    total = data.get('esearchresult', {}).get('count', '0')
    print(f'{label}: {len(ids)} 结果 (共 {total})')
    if ids:
        rs = requests.get(f'{base}/esummary.fcgi',
            params={'db': 'pubmed', 'id': ','.join(ids[:3]), 'retmode': 'json'},
            timeout=15)
        for uid in ids[:3]:
            e = rs.json().get('result', {}).get(uid, {})
            title = e.get('title', '')[:80]
            print(f'  {uid}: {title}')
    print()
