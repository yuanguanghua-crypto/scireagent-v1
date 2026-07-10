"""
Genesis-109 Real Cold Start: PubMed + Crossref Data Pipeline
Step 1: Search PubMed for product-related papers
Step 2: Fetch abstracts
Step 3: Crossref DOI metadata
"""
import os, sys, json, time, re
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.development'
import django; django.setup()

from apps.commerce.models import Product
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

PUBMED_SEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
CROSSREF_WORKS = "https://api.crossref.org/works"

def pubmed_search(query, max_results=5):
    """Search PubMed and return PMIDs."""
    params = urllib.parse.urlencode({
        'db': 'pubmed',
        'term': query,
        'retmax': max_results,
        'retmode': 'json',
        'sort': 'relevance',
    })
    url = f"{PUBMED_SEARCH}?{params}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'SciReagent/1.0 (research@scireagent.com)'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            return data.get('esearchresult', {}).get('idlist', [])
    except Exception as e:
        print(f"    PubMed search error: {e}")
        return []

def pubmed_fetch_details(pmids):
    """Fetch article details for a list of PMIDs."""
    if not pmids:
        return []
    params = urllib.parse.urlencode({
        'db': 'pubmed',
        'id': ','.join(pmids),
        'retmode': 'xml',
    })
    url = f"{PUBMED_FETCH}?{params}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'SciReagent/1.0 (research@scireagent.com)'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            xml_data = resp.read()
            return parse_pubmed_xml(xml_data)
    except Exception as e:
        print(f"    PubMed fetch error: {e}")
        return []

def parse_pubmed_xml(xml_data):
    """Parse PubMed XML response into structured data."""
    articles = []
    try:
        root = ET.fromstring(xml_data)
        for article in root.findall('.//PubmedArticle'):
            pmid_el = article.find('.//PMID')
            title_el = article.find('.//ArticleTitle')
            abstract_el = article.find('.//AbstractText')
            journal_el = article.find('.//Journal/Title')
            year_el = article.find('.//PubDate/Year')
            doi_el = article.find('.//ArticleId[@IdType="doi"]')

            pmid = pmid_el.text if pmid_el is not None else ''
            title = title_el.text if title_el is not None else ''
            abstract = abstract_el.text if abstract_el is not None else ''
            journal = journal_el.text if journal_el is not None else ''
            year = year_el.text if year_el is not None else ''
            doi = doi_el.text if doi_el is not None else ''

            articles.append({
                'pmid': pmid,
                'title': title or '',
                'abstract': (abstract or '')[:500],
                'journal': journal or '',
                'year': year or '',
                'doi': doi or '',
            })
    except Exception as e:
        print(f"    XML parse error: {e}")
    return articles

def extract_methods_from_abstract(abstract):
    """Extract method keywords from abstract text."""
    methods = []
    abstract_lower = abstract.lower()

    method_keywords = {
        'CuAAC Click Chemistry': ['cuaac', 'cu(i)', 'copper-catalyzed', 'azide-alkyne cycloaddition', 'copper(i)', 'click chemistry'],
        'SPAAC Click Chemistry': ['spaac', 'strain-promoted', 'cyclooctyne', 'dibenzocyclooctyne', 'dbco'],
        'NHS-Ester Conjugation': ['nhs ester', 'nhs-ester', 'n-hydroxysuccinimide', 'succinimidyl'],
        'Enzymatic Incorporation': ['in vitro transcription', 'polymerase', 'reverse transcriptase', 't7 rna polymerase', 'incorporation'],
        'BigDye Terminator Sequencing': ['sanger sequencing', 'dideoxy', 'chain termination', 'bigdye', 'capillary electrophoresis'],
        'Nextera DNA Library Prep': ['nextera', 'tagmentation', 'tn5 transposase', 'library prep'],
        'RiboGreen Quantification': ['ribogreen', 'rna quantification', 'fluorescence quantification'],
        'Cy3/Cy5 Protein Labeling': ['cy3', 'cy5', 'cyanine', 'fluorescent labeling', 'fluorescent dye'],
    }

    for method_name, keywords in method_keywords.items():
        for kw in keywords:
            if kw in abstract_lower:
                methods.append(method_name)
                break

    return list(set(methods))

def extract_applications_from_abstract(abstract):
    """Extract application keywords from abstract text."""
    apps = []
    abstract_lower = abstract.lower()

    app_keywords = {
        'RNA Fluorescent Labeling': ['rna labeling', 'rna fluorescent', 'fluorescent rna', 'rna detection', 'rna imaging'],
        'RNA Biotin Labeling': ['biotinylated rna', 'biotin-rna', 'rna pull-down', 'rna capture'],
        'RNA Quantification': ['rna quantification', 'rna concentration', 'rna measurement', 'ribogreen'],
        'Sanger Sequencing': ['sanger sequencing', 'dna sequencing', 'sequence analysis', 'chain termination'],
        'NGS Library Preparation': ['next-generation sequencing', 'ngs', 'library preparation', 'whole genome sequencing'],
        'CuAAC Bioconjugation': ['bioconjugation', 'click chemistry', 'protein labeling', 'biomolecule labeling'],
        'Protein Fluorescent Labeling': ['protein labeling', 'protein fluorescent', 'antibody labeling', 'immunofluorescence'],
    }

    for app_name, keywords in app_keywords.items():
        for kw in keywords:
            if kw in abstract_lower:
                apps.append(app_name)
                break

    return list(set(apps))

# === Main Pipeline ===
print("=" * 60)
print("Genesis-109: PubMed + Crossref Data Pipeline")
print("=" * 60)

products = list(Product.objects.filter(status='published').order_by('catalog_no'))
print(f"\nProcessing {len(products)} products...")

# Results storage
results = {}
total_papers = 0
total_with_abstract = 0

for i, product in enumerate(products):
    catalog = product.catalog_no or ''
    name = product.name
    cas = product.cas or ''

    # Build search query
    # Try CAS first (most specific), then product name
    queries = []
    if cas:
        queries.append(f'"{cas}"[Title/Abstract]')
    queries.append(f'"{name}"[Title/Abstract]')
    # Also try simplified name (remove special chars)
    simple_name = re.sub(r'[^a-zA-Z0-9\s-]', '', name)
    if simple_name != name:
        queries.append(f'"{simple_name}"[Title/Abstract]')

    all_pmids = set()
    for q in queries:
        pmids = pubmed_search(q, max_results=3)
        all_pmids.update(pmids)
        time.sleep(0.35)  # Rate limit: 3 req/sec

    if not all_pmids:
        results[catalog] = {'pmids': [], 'papers': [], 'methods': [], 'applications': []}
        continue

    # Fetch details
    papers = pubmed_fetch_details(list(all_pmids)[:5])
    time.sleep(0.35)

    # Extract methods and applications from abstracts
    all_methods = set()
    all_apps = set()
    for paper in papers:
        methods = extract_methods_from_abstract(paper['abstract'])
        apps = extract_applications_from_abstract(paper['abstract'])
        all_methods.update(methods)
        all_apps.update(apps)

    results[catalog] = {
        'pmids': [p['pmid'] for p in papers],
        'papers': papers,
        'methods': list(all_methods),
        'applications': list(all_apps),
    }

    total_papers += len(papers)
    if papers:
        total_with_abstract += 1

    # Progress
    if (i + 1) % 10 == 0 or i == len(products) - 1:
        print(f"  [{i+1}/{len(products)}] {catalog} {name[:30]} -> {len(papers)} papers, {len(all_methods)} methods, {len(all_apps)} apps")

# Save results
output_path = 'E:/scireagent-tencent/docs/pubmed_results.json'
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

# Summary
print(f"\n{'=' * 60}")
print(f"SUMMARY")
print(f"{'=' * 60}")
print(f"Products processed: {len(products)}")
print(f"Products with papers: {total_with_abstract}")
print(f"Total papers found: {total_papers}")

# Show top results
print(f"\nTop products by paper count:")
sorted_results = sorted(results.items(), key=lambda x: len(x[1]['pmids']), reverse=True)
for catalog, data in sorted_results[:10]:
    methods = ', '.join(data['methods'][:2]) if data['methods'] else 'none'
    print(f"  {catalog}: {len(data['pmids'])} papers, methods=[{methods}]")
