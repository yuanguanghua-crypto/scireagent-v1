"""Genesis-109 Step 2: Generate AI content for all products."""
import os, sys
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.development'
import django; django.setup()

from apps.commerce.models import Product
from apps.bridges.models import ProductMethod
from apps.knowledge.models import Method, Application

# Build lookup: product -> methods -> applications
def get_product_context(product):
    """Get method and application context for a product."""
    pm_links = ProductMethod.objects.filter(product=product).select_related('method__application')
    methods = []
    applications = []
    for pm in pm_links:
        if pm.method:
            methods.append(pm.method)
            if pm.method.application and pm.method.application not in applications:
                applications.append(pm.method.application)
    return methods, applications

def generate_overview(product, methods, applications):
    """Generate product overview based on context."""
    name = product.name
    cas = product.cas or 'N/A'
    formula = product.formula or ''
    mw = product.molecular_weight or ''
    purity = product.purity or ''
    cat = product.category_l1 or 'nucleotides'

    # Method names
    method_names = [m.name for m in methods[:3]]
    app_names = [a.name for a in applications[:3]]

    # Build overview
    parts = []

    # Opening sentence
    if 'azido' in name.lower():
        parts.append(f"{name} is a modified nucleotide analog featuring an azide group, enabling bioorthogonal click chemistry conjugation reactions.")
    elif 'amino' in name.lower():
        parts.append(f"{name} is a modified nucleotide analog with a primary amine group, suitable for NHS-ester conjugation and crosslinking applications.")
    elif 'fluoro' in name.lower():
        parts.append(f"{name} is a fluorine-modified nucleotide analog that provides enhanced nuclease resistance and can serve as a building block for modified nucleic acids.")
    elif 'propargyl' in name.lower():
        parts.append(f"{name} is an alkyne-functionalized nucleotide analog designed for copper-catalyzed azide-alkyne cycloaddition (CuAAC) click chemistry.")
    elif 'thio' in name.lower():
        parts.append(f"{name} is a thiol-modified nucleotide analog that can be used for thiol-disulfide exchange reactions and metal coordination chemistry.")
    elif 'ddntp' in name.lower() or 'dd' in name.lower().split('-')[0:2]:
        parts.append(f"{name} is a dideoxynucleotide triphosphate used as a chain terminator in Sanger DNA sequencing.")
    elif 'cy3' in name.lower() or 'cy5' in name.lower() or 'fam' in name.lower():
        parts.append(f"{name} is a fluorescently labeled nucleotide ready for direct detection in hybridization, labeling, and imaging applications.")
    elif 'biotin' in name.lower():
        parts.append(f"{name} is a biotinylated nucleotide analog for streptavidin-based detection and capture applications.")
    else:
        parts.append(f"{name} is a modified nucleotide analog for molecular biology research applications.")

    # Applications
    if app_names:
        parts.append(f"It is commonly used in {', '.join(app_names).lower()} workflows.")

    # Methods
    if method_names:
        parts.append(f"Compatible methods include {', '.join(method_names).lower()}.")

    # Technical details
    tech = []
    if formula:
        tech.append(f"Molecular formula: {formula}")
    if mw:
        tech.append(f"Molecular weight: {mw}")
    if purity and purity != 'N/A':
        tech.append(f"Purity: {purity}")
    if tech:
        parts.append(' '.join(tech))

    # Storage
    if product.storage:
        parts.append(f"Store at {product.storage}.")

    return ' '.join(parts)

def generate_seo_title(product, methods, applications):
    """Generate SEO title."""
    name = product.name
    app_names = [a.name for a in applications[:2]]
    if app_names:
        return f"{name} for {', '.join(app_names)} | SciReagent"
    return f"{name} — Modified Nucleotide | SciReagent"

def generate_seo_description(product, methods, applications):
    """Generate SEO description."""
    name = product.name
    app_names = [a.name for a in applications[:2]]
    method_names = [m.name for m in methods[:2]]
    cat = product.category_l1 or 'modified nucleotides'

    desc = f"{name}"
    if app_names:
        desc += f" for {', '.join(app_names).lower()}"
    if method_names:
        desc += f" via {', '.join(method_names).lower()}"
    desc += f". High purity {cat.replace('_', ' ')} for research use."
    if product.cas:
        desc += f" CAS: {product.cas}."
    desc += " Order from SciReagent."
    return desc[:160]  # SEO max length

# === Main ===
print('Genesis-109 Step 2: Generating AI content...')
products = Product.objects.filter(status='published').order_by('catalog_no')
updated = 0

for p in products:
    methods, applications = get_product_context(p)

    overview = generate_overview(p, methods, applications)
    seo_title = generate_seo_title(p, methods, applications)
    seo_desc = generate_seo_description(p, methods, applications)

    p.overview = overview
    p.seo_title = seo_title
    p.seo_description = seo_desc
    p.save(update_fields=['overview', 'seo_title', 'seo_description'])
    updated += 1

    if updated % 20 == 0:
        print(f'  Processed {updated}/{products.count()}...')

print(f'\nDone! Updated {updated} products with overview + SEO metadata.')
print(f'\nSample (SC8047):')
sample = Product.objects.get(catalog_no='SC8047')
print(f'  Overview: {sample.overview[:120]}...')
print(f'  SEO Title: {sample.seo_title}')
print(f'  SEO Desc: {sample.seo_description[:100]}...')
