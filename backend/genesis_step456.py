"""
Genesis-109 Step 4-6: Use PubMed data to build relationships, enhance content, and create Evidence Registry.
"""
import os, sys, json, time
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.development'
import django; django.setup()

from apps.commerce.models import Product
from apps.knowledge.models import Method, Application, Protocol, Reference
from apps.bridges.models import ProductMethod, MethodProtocol
from apps.commerce.services.faq_service import generate_faq

# Load PubMed results
with open('E:/scireagent-tencent/docs/pubmed_results.json', encoding='utf-8') as f:
    pubmed_data = json.load(f)

print("=" * 60)
print("Step 4: Merge PubMed evidence with relationships")
print("=" * 60, flush=True)

# Get existing methods
methods_map = {m.name: m for m in Method.objects.all()}
apps_map = {a.name: a for a in Application.objects.all()}

# Track evidence
evidence_records = []
new_pm_links = 0

for catalog, data in pubmed_data.items():
    try:
        product = Product.objects.get(catalog_no=catalog)
    except Product.DoesNotExist:
        continue

    # Get methods from PubMed extraction
    pubmed_methods = data.get('methods', [])
    pubmed_apps = data.get('applications', [])

    # Add new ProductMethod links based on PubMed evidence
    for method_name in pubmed_methods:
        method = methods_map.get(method_name)
        if method:
            _, created = ProductMethod.objects.get_or_create(
                product=product, method=method
            )
            if created:
                new_pm_links += 1

    # Build evidence records
    for paper in data.get('papers', []):
        pmid = paper.get('pmid', '')
        if not pmid:
            continue
        evidence_records.append({
            'product': catalog,
            'product_name': product.name,
            'pmid': pmid,
            'doi': paper.get('doi', ''),
            'title': paper.get('title', ''),
            'journal': paper.get('journal', ''),
            'year': paper.get('year', ''),
            'methods': pubmed_methods,
            'applications': pubmed_apps,
        })

print(f"  New ProductMethod links from PubMed: {new_pm_links}")
print(f"  Evidence records: {len(evidence_records)}")

# Save evidence registry
with open('E:/scireagent-tencent/docs/evidence_registry.json', 'w', encoding='utf-8') as f:
    json.dump(evidence_records, f, indent=2, ensure_ascii=False)
print(f"  Saved to evidence_registry.json")

# === Step 5: Enhance product content ===
print(f"\n{'=' * 60}")
print("Step 5: Enhance product content with PubMed data")
print("=" * 60, flush=True)

updated = 0
for catalog, data in pubmed_data.items():
    try:
        product = Product.objects.get(catalog_no=catalog)
    except Product.DoesNotExist:
        continue

    papers = data.get('papers', [])
    if not papers:
        continue

    # Enhance overview with paper references
    existing_overview = product.overview or ''
    paper_titles = [p['title'] for p in papers[:2] if p.get('title')]
    if paper_titles:
        refs = '; '.join(paper_titles[:2])
        # Add literature reference to overview
        if 'literature' not in existing_overview.lower() and 'reference' not in existing_overview.lower():
            enhanced = existing_overview.rstrip('.') + f'. Referenced in: {refs}.'
            product.overview = enhanced[:500]

    # Enhance SEO description
    if papers and not product.seo_description:
        product.seo_description = f"{product.name} for research use. Referenced in {len(papers)} publication(s). CAS: {product.cas or 'N/A'}."

    product.save(update_fields=['overview', 'seo_description'])
    updated += 1

print(f"  Enhanced {updated} products with PubMed references")

# === Step 6: Create Reference records ===
print(f"\n{'=' * 60}")
print("Step 6: Create Reference records in database")
print("=" * 60, flush=True)

ref_created = 0
seen_pmids = set()

for record in evidence_records:
    pmid = record['pmid']
    if pmid in seen_pmids:
        continue
    seen_pmids.add(pmid)

    # Check if already exists
    if Reference.objects.filter(pmid=pmid).exists():
        continue

    try:
        Reference.objects.create(
            title=record['title'][:255] if record['title'] else 'Untitled',
            authors='',
            journal=record['journal'][:100] if record['journal'] else '',
            year=int(record['year']) if record['year'] and record['year'].isdigit() else None,
            doi=record['doi'][:100] if record['doi'] else '',
            pmid=pmid,
            source_type='pubmed',
        )
        ref_created += 1
    except Exception as e:
        pass

print(f"  Created {ref_created} Reference records")

# === Final Summary ===
print(f"\n{'=' * 60}")
print("FINAL SUMMARY")
print("=" * 60)

from apps.knowledge.models import ResearchGoal, Application, Method, Protocol
from apps.bridges.models import ProductMethod, MethodProtocol

print(f"ResearchGoals: {ResearchGoal.objects.count()}")
print(f"Applications: {Application.objects.count()}")
print(f"Methods: {Method.objects.count()}")
print(f"Protocols: {Protocol.objects.count()}")
print(f"Products: {Product.objects.filter(status='published').count()}")
print(f"ProductMethod: {ProductMethod.objects.count()}")
print(f"MethodProtocol: {MethodProtocol.objects.count()}")
print(f"References: {Reference.objects.count()}")
print(f"Evidence records: {len(evidence_records)}")

# Coverage stats
products_with_methods = ProductMethod.objects.values('product').distinct().count()
products_with_papers = len([d for d in pubmed_data.values() if d.get('pmids')])
print(f"\nCoverage:")
print(f"  Products with method links: {products_with_methods}/109")
print(f"  Products with papers: {products_with_papers}/109")
