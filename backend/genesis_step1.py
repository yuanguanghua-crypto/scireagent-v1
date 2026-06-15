"""Genesis-109 Cold Start Simulation — Step 1: Create Knowledge Entities + Relationships"""
import os, sys
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.development'
import django; django.setup()

from apps.knowledge.models import ResearchGoal, Application, Method, Protocol
from apps.commerce.models import Product, ProductClass
from apps.bridges.models import ProductMethod, MethodProtocol

# === STEP 1: Clean up ===
print('Step 1: Cleaning up...')
ResearchGoal.objects.all().delete()
Application.objects.all().delete()
Method.objects.all().delete()
Protocol.objects.all().delete()
ProductMethod.objects.all().delete()
MethodProtocol.objects.all().delete()
print('  Done.')

# === STEP 2: Research Goals ===
print('\nStep 2: Research Goals...')
goals = {}
for name, summary in [
    ('RNA Analysis', 'Studying RNA structure, function, and expression through labeling, quantification, and imaging.'),
    ('DNA Sequencing', 'Determining DNA sequences using Sanger and next-generation sequencing technologies.'),
    ('Click Chemistry', 'Bioorthogonal reactions for specific labeling and conjugation of biomolecules.'),
    ('Protein Engineering', 'Modifying proteins for improved function, labeling, or detection.'),
]:
    rg = ResearchGoal.objects.create(name=name, slug=name.lower().replace(' ', '-'), summary=summary, status='active', priority=0)
    goals[name] = rg
    print(f'  {name} (id={rg.id})')

# === STEP 3: Applications ===
print('\nStep 3: Applications...')
apps = {}
for name, summary, goal in [
    ('RNA Fluorescent Labeling', 'Attach fluorescent dyes to RNA for visualization in cells, gels, and hybridization assays.', 'RNA Analysis'),
    ('RNA Biotin Labeling', 'Conjugate biotin to RNA for pull-down and streptavidin-based detection.', 'RNA Analysis'),
    ('RNA Quantification', 'Measure RNA concentration using fluorescent dyes and enzymatic methods.', 'RNA Analysis'),
    ('Sanger Sequencing', 'Determine DNA sequences using chain-terminating dideoxynucleotides.', 'DNA Sequencing'),
    ('NGS Library Preparation', 'Prepare DNA libraries for next-generation sequencing platforms.', 'DNA Sequencing'),
    ('CuAAC Bioconjugation', 'Copper-catalyzed azide-alkyne cycloaddition for biomolecule labeling.', 'Click Chemistry'),
    ('Protein Fluorescent Labeling', 'Attach fluorescent dyes to proteins for imaging and FRET studies.', 'Protein Engineering'),
]:
    a = Application.objects.create(name=name, slug=name.lower().replace(' ', '-'), summary=summary, research_goal=goals[goal], status='active')
    apps[name] = a
    print(f'  {name} (id={a.id})')

# === STEP 4: Methods ===
print('\nStep 4: Methods...')
methods = {}
method_defs = [
    ('CuAAC Click Chemistry',
     'Copper(I)-catalyzed azide-alkyne cycloaddition forms stable triazole linkage.',
     'High specificity; Bioorthogonal; Aqueous compatible',
     'Copper toxicity to live cells; Needs modified substrates',
     'CuAAC Bioconjugation'),
    ('NHS-Ester Conjugation',
     'NHS esters react with primary amines to form stable amide bonds.',
     'Simple protocol; No catalyst; Well-established',
     'Non-specific with multiple amines; Hydrolyzes in water',
     'RNA Fluorescent Labeling'),
    ('Enzymatic Incorporation',
     'Polymerases incorporate modified nucleotides during transcription or PCR.',
     'Site-specific; No post-synthetic modification; Scalable',
     'Efficiency varies by enzyme; May affect fidelity',
     'RNA Fluorescent Labeling'),
    ('BigDye Terminator Sequencing',
     'Sanger sequencing with fluorescent ddNTP terminators.',
     'Gold standard; High accuracy; Well-automated',
     'Limited read length; Higher cost per base than NGS',
     'Sanger Sequencing'),
    ('Nextera DNA Library Prep',
     'Tn5 transposase-based tagmentation for Illumina library prep.',
     'Fast (~2h); Low input; Automation-compatible',
     'Insert size variability; PCR bias possible',
     'NGS Library Preparation'),
    ('RiboGreen Quantification',
     'Fluorescent dye-based RNA quantification in plate assay.',
     'pg sensitivity; Broad dynamic range; High-throughput',
     'Not RNA-specific; Requires standard curve',
     'RNA Quantification'),
    ('SPAAC Click Chemistry',
     'Strain-promoted azide-alkyne cycloaddition without copper.',
     'No copper needed; Safe for live cells; Fast kinetics',
     'More expensive reagents; Less specific than CuAAC',
     'CuAAC Bioconjugation'),
    ('Cy3/Cy5 Protein Labeling',
     'Cyanine dye conjugation to proteins for fluorescence imaging.',
     'Bright dyes; Well-established; Multiple colors',
     'May affect protein function; Needs purification',
     'Protein Fluorescent Labeling'),
]
for name, principle, adv, lim, app_name in method_defs:
    m = Method.objects.create(name=name, slug=name.lower().replace(' ', '-'), summary=principle, purpose=principle,
                              advantages=adv, limitations=lim,
                              application=apps[app_name], status='active')
    methods[name] = m
    print(f'  {name} (id={m.id})')

# === STEP 5: Protocols ===
print('\nStep 5: Protocols...')
protocol_defs = [
    ('CuAAC RNA Fluorescent Labeling', 'CuAAC Click Chemistry', '1.2',
     'Label azide-modified RNA with alkyne-dyes via CuAAC.',
     'CuSO4, THPTA, sodium ascorbate, alkyne-dye, Tris pH 7.5',
     '1. Prepare azide-RNA 10-50uM. 2. Click mix: 1mM CuSO4, 2mM THPTA, 5mM ascorbate. 3. Add alkyne-dye 1.5x excess. 4. Incubate 30min 25C dark. 5. Quench with 10mM EDTA. 6. Purify by gel filtration. 7. Verify by UV-Vis.',
     'Use degassed buffer. Fresh ascorbate. Protect from light.'),
    ('NHS-Ester RNA Labeling', 'NHS-Ester Conjugation', '1.0',
     'Conjugate NHS-ester dyes to amino-modified RNA.',
     'NHS-ester dye, amino-RNA, NaHCO3 pH 8.3, DMSO',
     '1. Dissolve dye in DMSO 10mg/mL. 2. RNA at 50-100uM in NaHCO3. 3. Add 10x dye excess. 4. Incubate 2h RT dark. 5. Purify by gel filtration. 6. Calculate DOL by UV-Vis.',
     'Work quickly. NHS hydrolyzes in water. Use anhydrous DMSO.'),
    ('Enzymatic RNA Incorporation', 'Enzymatic Incorporation', '1.0',
     'Incorporate modified NTPs into RNA via T7 transcription.',
     'Modified NTPs, T7 RNAP, template DNA, NTP mix, buffer',
     '1. Linearize template 1ug. 2. Mix with NTPs (20-50% modified). 3. Add T7 RNAP. 4. Incubate 4-6h 37C. 5. DNase I treatment. 6. Purify RNA. 7. Verify by MS or gel.',
     'Start with 20% replacement. Higher ratio reduces yield.'),
    ('BigDye Terminator Protocol', 'BigDye Terminator Sequencing', '3.1',
     'Standard Sanger sequencing with BigDye v3.1.',
     'BigDye v3.1, template, primer, buffer, Hi-Di formamide',
     '1. Mix 200-500ng template, 3.2pmol primer, 2uL BigDye. 2. PCR: 96C 1min, 25x(96C 10s, 50C 5s, 60C 4min). 3. Ethanol precipitate. 4. Resuspend in Hi-Di. 5. Denature 95C 2min. 6. Run on ABI 3730xl.',
     'Fresh BigDye. No freeze-thaw. Template quality critical.'),
    ('Nextera XT Library Prep', 'Nextera DNA Library Prep', '1.0',
     'Illumina library prep via tagmentation.',
     'Nextera XT TD, ATM, NPM, index primers, beads',
     '1. 1ng gDNA + TD + ATM, 55C 5min. 2. Add NT buffer. 3. Amplify 12 cycles. 4. Bead cleanup 0.6x. 5. Qubit quantification. 6. Pool and sequence.',
     'Exactly 1ng input. Bead ratio affects insert size.'),
    ('RiboGreen RNA Quantification', 'RiboGreen Quantification', '1.0',
     'Quantify RNA with RiboGreen fluorescent dye.',
     'RiboGreen, TE buffer, RNA samples, standards',
     '1. Standards 0-1000ng/mL. 2. Dilute RiboGreen 1:200. 3. 100uL dye + 100uL sample per well. 4. 5min RT dark. 5. Read Ex480/Em520. 6. Standard curve calculation.',
     'Protect from light. RNase-free consumables.'),
    ('DBCO-Azide SPAAC Labeling', 'SPAAC Click Chemistry', '1.0',
     'Copper-free click labeling with DBCO reagents.',
     'DBCO-dye, azide-substrate, PBS',
     '1. Azide-substrate 10-100uM in PBS. 2. Add DBCO 1.5-3x excess. 3. Incubate 1-4h RT. 4. Purify by gel filtration. 5. Verify by MS.',
     'Light-sensitive. Slower than CuAAC at low concentration.'),
    ('Cy3 NHS-Ester Protein Labeling', 'Cy3/Cy5 Protein Labeling', '1.0',
     'Label proteins with Cy3/Cy5 NHS-ester dyes.',
     'Cy3-NHS, protein, NaHCO3 pH 8.3, desalting column',
     '1. Buffer exchange protein to NaHCO3. 2. Cy3-NHS in DMSO 10mg/mL. 3. 5-10x dye excess. 4. 1h RT dark. 5. Desalt. 6. Calculate DOL.',
     'No Tris/glycine in buffer. DOL 2-4 optimal.'),
]
for name, method_name, version, objective, materials, steps, troubleshooting in protocol_defs:
    p = Protocol.objects.create(
        name=name, slug=name.lower().replace(' ', '-'), method=methods[method_name], version=version,
        objective=objective, reagents=materials,
        troubleshooting=troubleshooting, status='published'
    )
    MethodProtocol.objects.create(method=methods[method_name], protocol=p)
    print(f'  {name} (id={p.id})')

# === STEP 6: Product-Method relationships ===
print('\nStep 6: Product-Method relationships...')

# Mapping rules based on ProductClass
CLASS_METHOD_MAP = {
    # 2'-Modified dNTPs (class 21) -> most use CuAAC or Enzymatic
    21: [
        ('CuAAC Click Chemistry', lambda p: 'azido' in (p.name or '').lower() or 'alkyn' in (p.name or '').lower()),
        ('NHS-Ester Conjugation', lambda p: 'amino' in (p.name or '').lower()),
        ('Enzymatic Incorporation', lambda p: True),  # all dNTPs can be enzymatically incorporated
    ],
    # Modified NTPs (class 10) -> Enzymatic + CuAAC/NHS based on modification
    10: [
        ('Enzymatic Incorporation', lambda p: True),
        ('CuAAC Click Chemistry', lambda p: 'azido' in (p.name or '').lower() or 'alkyn' in (p.name or '').lower() or 'propargyl' in (p.name or '').lower()),
        ('NHS-Ester Conjugation', lambda p: 'amino' in (p.name or '').lower() or 'nhs' in (p.name or '').lower()),
    ],
    # ddNTPs (class 22) -> BigDye Terminator
    22: [
        ('BigDye Terminator Sequencing', lambda p: True),
    ],
    # Labeled Nucleotides (class 23) -> ready to use, mostly for direct detection
    23: [
        ('Enzymatic Incorporation', lambda p: True),
        ('CuAAC Click Chemistry', lambda p: 'azido' in (p.name or '').lower() or 'alkyn' in (p.name or '').lower() or 'click' in (p.name or '').lower()),
        ('NHS-Ester Conjugation', lambda p: 'nhs' in (p.name or '').lower() or 'ester' in (p.name or '').lower()),
    ],
}

count = 0
for product in Product.objects.filter(status='published'):
    rules = CLASS_METHOD_MAP.get(product.product_class_id, [])
    for method_name, condition in rules:
        if condition(product):
            ProductMethod.objects.create(product=product, method=methods[method_name])
            count += 1
print(f'  Created {count} ProductMethod bridges')

# === STEP 7: Application-Method relationships ===
print('\nStep 7: Application-Method bridges...')
# These are already set via Method.application FK
print('  Done (via Method.application FK)')

print('\n=== FINAL SUMMARY ===')
print(f'ResearchGoals: {ResearchGoal.objects.count()}')
print(f'Applications: {Application.objects.count()}')
print(f'Methods: {Method.objects.count()}')
print(f'Protocols: {Protocol.objects.count()}')
print(f'Products: {Product.objects.filter(status="published").count()}')
print(f'ProductMethod: {ProductMethod.objects.count()}')
print(f'MethodProtocol: {MethodProtocol.objects.count()}')
