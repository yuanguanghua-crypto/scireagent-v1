"""
Genesis-109: Crossref Data Pipeline (PubMed blocked in China)
Uses Crossref API for paper search + DOI metadata.
"""
import os, sys, json, time, re
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.development'
import django; django.setup()

from apps.commerce.models import Product
import urllib.request
import urllib.parse

CROSSREF_WORKS = "https://api.crossref.org/works"

def crossref_search(query, rows=5):
    """Search Crossref and return works."""
    params = urllib.parse.urlencode({
        'query': query,
        'rows': rows,
        'sort': 'relevance',
    })
    url = f"{CROSSREF_WORKS}?{params}"
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'SciReagent/1.0 (mailto:research@scireagent.com)',
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            items = data.get('message', {}).get('items', [])
            results = []
            for item in items:
                doi = item.get('DOI', '')
                title_list = item.get('title', [])
                title = title_list[0] if title_list else ''
                journal_list = item.get('container-title', [])
                journal = journal_list[0] if journal_list else ''
                year = ''
                pub_date = item.get('published-online', item.get('published', {}))
                if pub_date and 'date-parts' in pub_date:
                    parts = pub_date['date-parts'][0]
                    if parts:
                        year = str(parts[0])
                results.append({
                    'doi': doi,
                    'title': title,
                    'journal': journal,
                    'year': year,
                    'score': item.get('score', 0),
                })
            return results
    except Exception as e:
        print(f"    Crossref error: {e}")
        return []

def extract_methods_from_text(text):
    """Extract method keywords from title."""
    text_lower = text.lower()
    methods = []
    method_keywords = {
        'CuAAC Click Chemistry': ['cuaac', 'copper-catalyzed', 'azide-alkyne', 'click chemistry', 'triazole'],
        'SPAAC Click Chemistry': ['spaac', 'strain-promoted', 'cyclooctyne', 'dbco'],
        'NHS-Ester Conjugation': ['nhs ester', 'nhs-ester', 'n-hydroxysuccinimide', 'succinimidyl'],
        'Enzymatic Incorporation': ['in vitro transcription', 'polymerase', 'reverse transcriptase', 't7 rna', 'incorporation'],
        'BigDye Terminator Sequencing': ['sanger', 'dideoxy', 'chain termination', 'bigdye'],
        'Nextera DNA Library Prep': ['nextera', 'tagmentation', 'tn5', 'library prep'],
        'RiboGreen Quantification': ['ribogreen', 'rna quantification'],
        'Cy3/Cy5 Protein Labeling': ['cy3', 'cy5', 'cyanine', 'fluorescent label'],
    }
    for method_name, keywords in method_keywords.items():
        for kw in keywords:
            if kw in text_lower:
                methods.append(method_name)
                break
    return list(set(methods))

def extract_applications_from_text(text):
    """Extract application keywords from title."""
    text_lower = text.lower()
    apps = []
    app_keywords = {
        'RNA Fluorescent Labeling': ['rna label', 'rna fluorescent', 'fluorescent rna', 'rna detection', 'rna imaging', 'rna probe'],
        'RNA Biotin Labeling': ['biotinylated rna', 'biotin-rna', 'rna pull-down'],
        'RNA Quantification': ['rna quantification', 'rna concentration'],
        'Sanger Sequencing': ['sanger sequencing', 'dna sequencing', 'sequence analysis'],
        'NGS Library Preparation': ['next-generation sequencing', 'ngs', 'library preparation'],
        'CuAAC Bioconjugation': ['bioconjugation', 'click chemistry', 'biomolecule labeling'],
        'Protein Fluorescent Labeling': ['protein labeling', 'protein fluorescent', 'antibody labeling'],
    }
    for app_name, keywords in app_keywords.items():
        for kw in keywords:
            if kw in text_lower:
                apps.append(app_name)
                break
    return list(set(apps))

# === Main ===
print("=" * 60)
print("Genesis-109: Crossref Data Pipeline")
print("=" * 60)

products = list(Product.objects.filter(status='published').order_by('catalog_no'))
print(f"\nProcessing {len(products)} products via Crossref...")

results = {}
total_papers = 0
total_with_papers = 0

for i, product in enumerate(products):
    catalog = product.catalog_no or ''
    name = product.name
    cas = product.cas or ''

    # Search Crossref
    queries = []
    if cas:
        queries.append(f'{cas}')
    queries.append(f'{name}')

    all_works = []
    for q in queries:
        works = crossref_search(q, rows=3)
        all_works.extend(works)
        time.sleep(0.5)  # Rate limit: be polite

    # Deduplicate by DOI
    seen_dois = set()
    unique_works = []
    for w in all_works:
        if w['doi'] and w['doi'] not in seen_dois:
            seen_dois.add(w['doi'])
            unique_works.append(w)
    all_works = unique_works[:5]

    # Extract methods and applications
    all_methods = set()
    all_apps = set()
    for work in all_works:
        text = work['title'] + ' ' + work.get('journal', '')
        all_methods.update(extract_methods_from_text(text))
        all_apps.update(extract_applications_from_text(text))

    results[catalog] = {
        'dois': [w['doi'] for w in all_works],
        'papers': all_works,
        'methods': list(all_methods),
        'applications': list(all_apps),
    }

    total_papers += len(all_works)
    if all_works:
        total_with_papers += 1

    if (i + 1) % 10 == 0 or i == len(products) - 1:
        print(f"  [{i+1}/{len(products)}] {catalog} {name[:30]} -> {len(all_works)} papers")

# Save
output_path = 'E:/scireagent-tencent/docs/crossref_results.json'
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"\n{'=' * 60}")
print(f"SUMMARY")
print(f"{'=' * 60}")
print(f"Products processed: {len(products)}")
print(f"Products with papers: {total_with_papers}")
print(f"Total papers found: {total_papers}")

print(f"\nTop products by paper count:")
sorted_results = sorted(results.items(), key=lambda x: len(x[1]['dois']), reverse=True)
for catalog, data in sorted_results[:10]:
    methods = ', '.join(data['methods'][:2]) if data['methods'] else 'none'
    print(f"  {catalog}: {len(data['dois'])} papers, methods=[{methods}]")
