"""
Genesis-109: PubMed + PubChem Real Data Pipeline
"""
import os, sys, json, time, re
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.development'
import django; django.setup()

from apps.commerce.models import Product
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

def pubmed_search(query, max_results=5):
    params = urllib.parse.urlencode({'db': 'pubmed', 'term': query, 'retmax': max_results, 'retmode': 'json', 'sort': 'relevance'})
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{params}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'SciReagent/1.0'})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
            return data.get('esearchresult', {}).get('idlist', [])
    except Exception as e:
        return []

def pubmed_fetch(pmids):
    if not pmids: return []
    params = urllib.parse.urlencode({'db': 'pubmed', 'id': ','.join(pmids), 'retmode': 'xml'})
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?{params}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'SciReagent/1.0'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            xml_data = resp.read()
            articles = []
            root = ET.fromstring(xml_data)
            for article in root.findall('.//PubmedArticle'):
                pmid = (article.findtext('.//PMID') or '')
                title = (article.findtext('.//ArticleTitle') or '')
                abstract = (article.findtext('.//AbstractText') or '')[:500]
                journal = (article.findtext('.//Journal/Title') or '')
                year = ''
                pd = article.find('.//PubDate')
                if pd is not None:
                    year = pd.findtext('Year') or ''
                doi_el = article.find('.//ArticleId[@IdType="doi"]')
                doi = doi_el.text if doi_el is not None else ''
                articles.append({'pmid': pmid, 'title': title, 'abstract': abstract, 'journal': journal, 'year': year, 'doi': doi})
            return articles
    except:
        return []

def extract_methods(text):
    text_lower = text.lower()
    found = []
    kw = {
        'CuAAC Click Chemistry': ['cuaac', 'copper-catalyzed', 'azide-alkyne cycloaddition', 'click chemistry'],
        'SPAAC Click Chemistry': ['spaac', 'strain-promoted', 'cyclooctyne', 'dbco'],
        'NHS-Ester Conjugation': ['nhs ester', 'n-hydroxysuccinimide', 'succinimidyl'],
        'Enzymatic Incorporation': ['in vitro transcription', 't7 rna polymerase', 'polymerase incorporation', 'reverse transcriptase'],
        'BigDye Terminator Sequencing': ['sanger sequencing', 'dideoxy', 'chain termination', 'bigdye'],
        'Nextera DNA Library Prep': ['nextera', 'tagmentation', 'tn5 transposase'],
        'RiboGreen Quantification': ['ribogreen', 'rna quantification'],
        'Cy3/Cy5 Protein Labeling': ['cy3', 'cy5', 'cyanine dye', 'fluorescent labeling'],
    }
    for name, keywords in kw.items():
        for k in keywords:
            if k in text_lower:
                found.append(name)
                break
    return list(set(found))

def extract_apps(text):
    text_lower = text.lower()
    found = []
    kw = {
        'RNA Fluorescent Labeling': ['rna labeling', 'rna fluorescent', 'fluorescent rna', 'rna detection', 'rna imaging'],
        'RNA Biotin Labeling': ['biotinylated rna', 'biotin-rna', 'rna pull-down'],
        'RNA Quantification': ['rna quantification', 'rna concentration'],
        'Sanger Sequencing': ['sanger sequencing', 'dna sequencing', 'sequence analysis'],
        'NGS Library Preparation': ['next-generation sequencing', 'ngs', 'library preparation'],
        'CuAAC Bioconjugation': ['bioconjugation', 'click chemistry', 'biomolecule labeling'],
        'Protein Fluorescent Labeling': ['protein labeling', 'antibody labeling', 'immunofluorescence'],
    }
    for name, keywords in kw.items():
        for k in keywords:
            if k in text_lower:
                found.append(name)
                break
    return list(set(found))

# === Main ===
print("=" * 60)
print("Genesis-109: PubMed Real Data Pipeline")
print("=" * 60, flush=True)

products = list(Product.objects.filter(status='published').order_by('catalog_no'))
print(f"\nProcessing {len(products)} products...", flush=True)

results = {}
total_papers = 0
total_with_papers = 0

for i, product in enumerate(products):
    catalog = product.catalog_no or ''
    name = product.name
    cas = product.cas or ''

    # Build search query
    queries = []
    if cas:
        queries.append(cas)
    # Simplify name for search
    simple = re.sub(r'[^a-zA-Z0-9\s-]', ' ', name).strip()
    queries.append(f'"{simple}"')

    all_pmids = set()
    for q in queries:
        pmids = pubmed_search(q, max_results=3)
        all_pmids.update(pmids)
        time.sleep(0.4)

    # Fetch details
    papers = pubmed_fetch(list(all_pmids)[:5]) if all_pmids else []
    time.sleep(0.4)

    # Extract
    all_methods = set()
    all_apps = set()
    for p in papers:
        text = p['title'] + ' ' + p['abstract']
        all_methods.update(extract_methods(text))
        all_apps.update(extract_apps(text))

    results[catalog] = {
        'pmids': [p['pmid'] for p in papers],
        'papers': papers,
        'methods': list(all_methods),
        'applications': list(all_apps),
    }

    total_papers += len(papers)
    if papers:
        total_with_papers += 1

    if (i + 1) % 10 == 0 or i == len(products) - 1:
        print(f"  [{i+1}/{len(products)}] {catalog} {name[:30]} -> {len(papers)} papers, {len(all_methods)} methods", flush=True)

# Save
with open('E:/scireagent-tencent/docs/pubmed_results.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"\n{'=' * 60}")
print(f"SUMMARY")
print(f"{'=' * 60}")
print(f"Products: {len(products)}")
print(f"With papers: {total_with_papers}")
print(f"Total papers: {total_papers}")

sorted_r = sorted(results.items(), key=lambda x: len(x[1]['pmids']), reverse=True)
print(f"\nTop 10:")
for cat, d in sorted_r[:10]:
    m = ', '.join(d['methods'][:2]) or 'none'
    print(f"  {cat}: {len(d['pmids'])} papers, methods=[{m}]")
