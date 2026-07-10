"""
seed_test_data.py — 灌入测试种子数据

标记策略：
  - 所有 slug 以 __test__ 开头
  - 所有 name 以 [TEST] 开头
  - 删除时只需: python manage.py clean_test_data

用法：
  python manage.py seed_test_data          # 灌入数据
  python manage.py seed_test_data --clear  # 清除测试数据
"""

from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.knowledge.models import (
    ResearchGoal, Application, Method, Protocol, ProtocolStep,
    Reference, Compatibility,
)
from apps.commerce.models import ProductClass, CatalogGroup, Product, SKU
from apps.bridges.models import (
    ProductMethod, MethodProtocol, ProductReference,
    ProductCompatibility, ProductProduct,
)

# ── 标记常量 ──────────────────────────────────────────────
PREFIX = '__test__'
TAG = '[TEST]'


class Command(BaseCommand):
    help = '灌入带标记的测试数据（slug 以 __test__ 开头，name 以 [TEST] 开头）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='清除所有测试数据（删除 slug 以 __test__ 开头的记录）',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options['clear']:
            self._clear()
            return

        self.stdout.write('开始灌入测试数据...\n')

        refs = self._create_references()
        goals = self._create_research_goals()
        apps = self._create_applications(goals)
        methods = self._create_methods(apps)
        protocols = self._create_protocols(methods)
        pclasses, cgroups = self._create_catalog()
        products = self._create_products(pclasses, cgroups)
        self._create_skus(products)
        self._create_bridges(products, methods, protocols, refs)
        self._create_compatibility(products)

        total = (
            len(goals) + len(apps) + len(methods) + len(protocols)
            + len(products) + len(refs)
        )
        self.stdout.write(self.style.SUCCESS(f'\n✅ 测试数据灌入完成！共 {total} 条主记录'))
        self.stdout.write(f'   清除命令: python manage.py seed_test_data --clear')

    # ── Research Goals ────────────────────────────────────
    def _create_research_goals(self):
        data = [
            ('RNA Analysis', 1, 'Tools and reagents for RNA extraction, labeling, and quantification.'),
            ('DNA Sequencing', 2, 'Reagents for Sanger, NGS, and long-read sequencing workflows.'),
            ('Click Chemistry', 3, 'Bioconjugation reagents using CuAAC, SPAAC, and inverse electron-demand DIELS-ALDER reactions.'),
            ('Protein Engineering', 4, 'Reagents for protein modification, crosslinking, and fluorescent labeling.'),
        ]
        goals = []
        for name, priority, summary in data:
            obj, _ = ResearchGoal.objects.update_or_create(
                slug=f'{PREFIX}{name.lower().replace(" ", "-")}',
                defaults={
                    'name': f'{TAG} {name}',
                    'summary': summary,
                    'priority': priority,
                    'status': 'active',
                },
            )
            goals.append(obj)
            self.stdout.write(f'  ResearchGoal: {obj.name}')
        return goals

    # ── Applications ──────────────────────────────────────
    def _create_applications(self, goals):
        data = [
            (goals[0], 'RNA Fluorescent Labeling', 1, 'Attach fluorophores to RNA for microscopy, FISH, and gel visualization.'),
            (goals[0], 'RNA Quantification', 2, 'Measure RNA concentration and integrity using dye-based or probe-based assays.'),
            (goals[1], 'Sanger Sequencing', 3, 'Chain-termination sequencing with fluorescent ddNTPs.'),
            (goals[1], 'NGS Library Preparation', 4, 'Fragmentation, adapter ligation, and amplification for Illumina sequencing.'),
            (goals[2], 'CuAAC Bioconjugation', 5, 'Copper-catalyzed azide-alkyne cycloaddition for labeling proteins and nucleic acids.'),
            (goals[2], 'SPAAC Bioconjugation', 6, 'Strain-promoted azide-alkyne cycloaddition — copper-free, biocompatible.'),
            (goals[3], 'Protein Fluorescent Labeling', 7, 'NHS-ester and maleimide conjugation of fluorophores to proteins.'),
        ]
        apps = []
        for goal, name, order, summary in data:
            obj, _ = Application.objects.update_or_create(
                slug=f'{PREFIX}{name.lower().replace(" ", "-")}',
                defaults={
                    'name': f'{TAG} {name}',
                    'research_goal': goal,
                    'summary': summary,
                    'sort_order': order,
                    'status': 'active',
                },
            )
            apps.append(obj)
            self.stdout.write(f'  Application: {obj.name}')
        return apps

    # ── Methods ───────────────────────────────────────────
    def _create_methods(self, apps):
        data = [
            (apps[0], 'NHS-Ester RNA Labeling', 'Covalent attachment of NHS-ester fluorophores to RNA bases.', 'Medium', '2-3 hours'),
            (apps[0], 'Click Chemistry RNA Labeling', 'Azide-alkyne cycloaddition for site-specific RNA labeling.', 'High', '4-6 hours'),
            (apps[1], 'RiboGreen Quantification', 'Fluorescent dye-based RNA quantification assay.', 'Low', '30 minutes'),
            (apps[2], 'BigDye Terminator Sequencing', 'Standard Sanger sequencing with BigDye chemistry.', 'Medium', '3-4 hours'),
            (apps[3], 'Nextera DNA Library Prep', 'Tagmentation-based library preparation for Illumina.', 'High', '2 hours'),
            (apps[4], 'CuAAC Click Chemistry Protocol', 'Copper(I)-catalyzed azide-alkyne cycloaddition.', 'Medium', '1-2 hours'),
            (apps[5], 'DBCO-Azide SPAAC Protocol', 'Strain-promoted click chemistry with DBCO reagents.', 'High', '30 minutes'),
            (apps[6], 'Cy3/Cy5 Protein Labeling', 'Cyanine dye NHS-ester conjugation to lysine residues.', 'Medium', '2 hours'),
        ]
        methods = []
        for app, name, purpose, cost, timeline in data:
            obj, _ = Method.objects.update_or_create(
                slug=f'{PREFIX}{name.lower().replace(" ", "-")}',
                defaults={
                    'name': f'{TAG} {name}',
                    'application': app,
                    'summary': purpose[:200],
                    'purpose': purpose,
                    'advantages': f'Advantages of {name}: reliable, well-documented, compatible with standard lab equipment.',
                    'limitations': f'Limitations of {name}: requires specific reagent kits, may need optimization for novel targets.',
                    'cost_band': cost,
                    'timeline': timeline,
                    'status': 'active',
                },
            )
            methods.append(obj)
            self.stdout.write(f'  Method: {obj.name}')
        return methods

    # ── Protocols ─────────────────────────────────────────
    def _create_protocols(self, methods):
        protocols_data = [
            # (method_index, name, version, objective, status)
            (0, 'Cy3-NHS RNA Labeling Standard Protocol', '1.0', 'Label 10ug total RNA with Cy3-NHS ester for microarray hybridization.', 'published'),
            (1, 'CuAAC Azide-RNA Labeling', '1.0', 'Label azide-modified RNA with DBCO-fluorophore via copper-catalyzed click chemistry.', 'published'),
            (2, 'RiboGreen RNA Quantification Assay', '1.0', 'Quantify RNA concentration using RiboGreen fluorescent dye in a 96-well plate format.', 'published'),
            (3, 'Standard BigDye Terminator Protocol', '2.0', 'Perform Sanger sequencing of plasmid DNA using BigDye Terminator v3.1 chemistry.', 'published'),
            (4, 'Nextera XT DNA Library Prep', '1.0', 'Prepare sequencing-ready libraries from 1ng input DNA using tagmentation.', 'published'),
            (5, 'CuAAC Protein-Azide Conjugation', '1.0', 'Attach azide-functionalized probes to DBCO-modified proteins via CuAAC.', 'published'),
            (6, 'DBCO-PEG4-Azide SPAAC', '1.0', 'Perform copper-free click conjugation of DBCO-PEG4 with azide-modified targets.', 'draft'),
            (7, 'Cy3 NHS-Ester Protein Labeling', '1.0', 'Label IgG antibodies with Cy3-NHS ester at lysine residues.', 'published'),
        ]
        protocols = []
        for method_idx, name, version, objective, status in protocols_data:
            method = methods[method_idx]
            obj, _ = Protocol.objects.update_or_create(
                method=method,
                slug=f'{PREFIX}{name.lower().replace(" ", "-")[:60]}',
                version=version,
                defaults={
                    'name': f'{TAG} {name}',
                    'objective': objective,
                    'principle': f'This protocol follows established chemistry for {name}. Detailed principle described in the method documentation.',
                    'materials': 'Microcentrifuge tubes (1.5mL), pipette tips, 96-well plate (optional), aluminum foil.',
                    'reagents': 'Target molecule, labeling reagent, reaction buffer, quenching reagent, purification columns.',
                    'equipment': 'Microcentrifuge, heat block, vortex mixer, spectrophotometer, gel electrophoresis system.',
                    'troubleshooting': 'Low yield: check reagent storage conditions. High background: increase wash steps. Poor labeling: verify target concentration.',
                    'expected_results': 'Labeled product should show shifted mobility on gel and characteristic absorption spectrum.',
                    'status': status,
                },
            )
            # Add steps
            self._create_protocol_steps(obj, method_idx)
            protocols.append(obj)
            self.stdout.write(f'  Protocol: {obj.name}')
        return protocols

    def _create_protocol_steps(self, protocol, method_idx):
        """为每个协议创建 3-5 个步骤"""
        steps_templates = [
            [
                ('Prepare RNA sample', 'Dissolve 10ug total RNA in 50uL nuclease-free water. Measure A260/A280 ratio.', 300, 'Keep RNA on ice at all times to prevent degradation.'),
                ('Add labeling reagent', 'Add 5uL Cy3-NHS ester (10ug/uL in DMSO) to RNA solution. Mix gently by pipetting.', 60, 'Do NOT vortex. NHS esters are moisture-sensitive.'),
                ('Incubate', 'Incubate at room temperature in the dark for 1 hour. Mix every 15 minutes.', 3600, 'Protect from light. Cover tube with aluminum foil.'),
                ('Quench reaction', 'Add 5uL quenching buffer. Incubate 15 minutes at RT.', 900, ''),
                ('Purify labeled RNA', 'Apply reaction mix to RNA purification column. Elute in 50uL nuclease-free water.', 1200, 'Do not exceed centrifuge speed specified by column manufacturer.'),
            ],
            [
                ('Prepare azide-RNA', 'Dissolve 5ug azide-modified RNA in 30uL PBS buffer.', 300, 'Use freshly prepared PBS.'),
                ('Add DBCO-fluorophore', 'Add 2uL DBCO-fluorophore stock (5mM in DMSO). Mix gently.', 60, 'Avoid light exposure.'),
                ('Add CuSO4/TBTA catalyst', 'Add 1uL CuSO4 (50mM) and 1uL TBTA ligand (50mM in DMSO/tBuOH).', 60, 'CuSO4 is an irritant. Wear gloves.'),
                ('Add sodium ascorbate', 'Add 2uL freshly prepared sodium ascorbate (50mM). Mix immediately.', 30, 'Must be freshly prepared — oxidizes rapidly.'),
                ('Incubate and purify', 'Incubate 1 hour at RT. Purify by spin column.', 3600, 'Check for color change indicating successful conjugation.'),
            ],
            [
                ('Prepare standards', 'Prepare RNA standards: 0, 10, 50, 100, 500, 1000 ng/uL in TE buffer.', 600, 'Use calibrated pipettes.'),
                ('Prepare samples', 'Dilute unknown RNA samples 1:100 in TE buffer.', 120, ''),
                ('Add RiboGreen reagent', 'Add 100uL RiboGreen working solution to each well.', 120, 'RiboGreen is light-sensitive.'),
                ('Read fluorescence', 'Read fluorescence at Ex 485nm / Em 528nm on plate reader.', 180, 'Read within 10 minutes of reagent addition.'),
                ('Calculate concentration', 'Generate standard curve and interpolate unknown sample concentrations.', 120, 'R² should be > 0.99.'),
            ],
        ]

        template_idx = method_idx % len(steps_templates)
        steps = steps_templates[template_idx]

        # Clear existing steps
        protocol.steps.all().delete()
        for i, (title, body, duration, warnings) in enumerate(steps, 1):
            ProtocolStep.objects.create(
                protocol=protocol,
                step_no=i,
                title=title,
                body=body,
                duration_seconds=duration,
                warnings=warnings,
            )

    # ── References ────────────────────────────────────────
    def _create_references(self):
        data = [
            ('Fluorescent labeling of RNA for microarray analysis', 'Smith J, Doe A', 'Nature Methods', 2023, '10.1038/nmeth.1234', '37000001'),
            ('Copper-catalyzed azide-alkyne cycloaddition in biology', 'Wang L, Chen X', 'JACS', 2024, '10.1021/jacs.4567', '38000002'),
            ('Strain-promoted click chemistry for live-cell labeling', 'Brown K et al.', 'Angew Chem', 2023, '10.1002/anie.20231234', '37000003'),
            ('Next-generation sequencing library preparation methods', 'Lee S, Park J', 'Genome Research', 2024, '10.1101/gr.278901', '38000004'),
            ('Protein labeling with cyanine dyes: a practical guide', 'Zhang Y et al.', 'Bioconjugate Chem', 2023, '10.1021/acs.bioconjchem.3c001', '37000005'),
        ]
        refs = []
        for title, authors, journal, year, doi, pmid in data:
            obj, _ = Reference.objects.update_or_create(
                doi=doi,
                defaults={
                    'title': f'{TAG} {title}',
                    'authors': authors,
                    'journal': journal,
                    'year': year,
                    'pmid': pmid,
                    'url': f'https://doi.org/{doi}',
                    'source_type': 'journal',
                },
            )
            refs.append(obj)
            self.stdout.write(f'  Reference: {obj.title[:60]}...')
        return refs

    # ── Catalog ───────────────────────────────────────────
    def _create_catalog(self):
        pclasses = {}
        for name, slug in [
            ('Nucleotides', 'nucleotides'),
            ('Click Chemistry Reagents', 'click-chemistry'),
            ('Fluorescent Dyes', 'fluorescent-dyes'),
            ('Sequencing Kits', 'sequencing-kits'),
        ]:
            obj, _ = ProductClass.objects.update_or_create(
                slug=f'{PREFIX}{slug}',
                defaults={'name': f'{TAG} {name}'},
            )
            pclasses[slug] = obj

        cgroup, _ = CatalogGroup.objects.update_or_create(
            slug=f'{PREFIX}main-catalog',
            defaults={'name': f'{TAG} Main Catalog', 'locale': 'en', 'active': True},
        )
        return pclasses, cgroup

    # ── Products ──────────────────────────────────────────
    def _create_products(self, pclasses, cgroups):
        data = [
            # (name, cas, smiles, purity, storage, price, pack_size, pc_key)
            ('Cy3-NHS Ester', '12345-67-8', 'CC(=O)Oc1ccc2c(c1)ccc(c2)C(/C=C/C1=N(CC)CCC1)C#N', '>=95%', '-20°C, protect from light', Decimal('285.00'), '1mg', 'fluorescent-dyes'),
            ('Cy5-NHS Ester', '12345-68-9', 'CC(=O)Oc1ccc2c(c1)ccc(c2)C(/C=C/C1=N(CCC)CCC1)C#N', '>=95%', '-20°C, protect from light', Decimal('310.00'), '1mg', 'fluorescent-dyes'),
            ('DBCO-PEG4-NHS', '2228857-48-5', 'O=C(ON1C(=O)CCC1=O)CCOCCOCCOCCOCC#Cc1ccccc1', '>=98%', '-20°C, desiccated', Decimal('420.00'), '5mg', 'click-chemistry'),
            ('Azide-PEG3-Biotin', '1312309-63-7', 'N=[N+]=[N-]CCOCCOCCOCCNC(=O)CCCCC1SCC2NC(=O)NC21', '>=97%', '-20°C', Decimal('195.00'), '10mg', 'click-chemistry'),
            ('DBCO-Sulfo-NHS', '2055023-47-9', 'O=C(ON1C(=O)CCC1=O)CCS(=O)(=O)Oc1ccccc1C#Cc1ccccc1', '>=95%', '-20°C, desiccated', Decimal('350.00'), '5mg', 'click-chemistry'),
            ('ATTO-488 NHS Ester', '1131634-20-6', 'O=C(ON1C(=O)CCC1=O)c2ccc(N(C)C)cc2', '>=90%', '-20°C, protect from light', Decimal('265.00'), '1mg', 'fluorescent-dyes'),
            ('BigDye Terminator v3.1', 'N/A', '', '', '4°C', Decimal('850.00'), '100 reactions', 'sequencing-kits'),
            ('Nextera XT Library Prep Kit', 'N/A', '', '', '4°C', Decimal('1200.00'), '24 reactions', 'sequencing-kits'),
            ('RiboGreen RNA Quantitation Kit', 'N/A', '', '', '4°C, protect from light', Decimal('320.00'), '1000 assays', 'nucleotides'),
            ('Azide-PEG4-NHS Ester', '2100300-35-6', 'N=[N+]=[N-]CCOCCOCCOCCOCC(=O)ON1C(=O)CCC1=O', '>=95%', '-20°C', Decimal('295.00'), '5mg', 'click-chemistry'),
        ]
        products = []
        for name, cas, smiles, purity, storage, price, pack_size, pc_key in data:
            obj, _ = Product.objects.update_or_create(
                slug=f'{PREFIX}{name.lower().replace(" ", "-").replace("/", "-")}',
                defaults={
                    'name': f'{TAG} {name}',
                    'cas': cas,
                    'smiles': smiles,
                    'purity': purity,
                    'storage': storage,
                    'shipping': 'Ship on blue ice. Store immediately upon receipt.',
                    'lead_time': '1-3 business days',
                    'handling_notes': 'Handle with gloves. Avoid repeated freeze-thaw cycles.',
                    'shelf_life': timedelta(days=730),
                    'research_use_only': True,
                    'product_class': pclasses.get(pc_key),
                    'catalog_group': cgroups,
                    'status': 'active',
                },
            )
            products.append(obj)
            self.stdout.write(f'  Product: {obj.name}')
        return products

    # ── SKUs ──────────────────────────────────────────────
    def _create_skus(self, products):
        sku_data = [
            # (product_index, sku_suffix, pack_size, price, status)
            (0, '1mg', '1mg', Decimal('285.00'), 'in_stock'),
            (0, '5mg', '5mg', Decimal('1100.00'), 'in_stock'),
            (1, '1mg', '1mg', Decimal('310.00'), 'in_stock'),
            (1, '5mg', '5mg', Decimal('1200.00'), 'limited'),
            (2, '5mg', '5mg', Decimal('420.00'), 'in_stock'),
            (2, '25mg', '25mg', Decimal('1600.00'), 'preorder'),
            (3, '10mg', '10mg', Decimal('195.00'), 'in_stock'),
            (3, '50mg', '50mg', Decimal('680.00'), 'in_stock'),
            (4, '5mg', '5mg', Decimal('350.00'), 'in_stock'),
            (5, '1mg', '1mg', Decimal('265.00'), 'limited'),
            (6, '100rxn', '100 reactions', Decimal('850.00'), 'in_stock'),
            (6, '500rxn', '500 reactions', Decimal('3200.00'), 'in_stock'),
            (7, '24rxn', '24 reactions', Decimal('1200.00'), 'in_stock'),
            (7, '96rxn', '96 reactions', Decimal('4000.00'), 'preorder'),
            (8, '1000assay', '1000 assays', Decimal('320.00'), 'in_stock'),
            (9, '5mg', '5mg', Decimal('295.00'), 'in_stock'),
        ]
        for pidx, suffix, pack_size, price, status in sku_data:
            product = products[pidx]
            SKU.objects.update_or_create(
                sku_code=f'{PREFIX}SKU-{product.id}-{suffix}',
                defaults={
                    'product': product,
                    'pack_size': pack_size,
                    'price': price,
                    'currency': 'USD',
                    'inventory_status': status,
                },
            )
        self.stdout.write(f'  SKU: {len(sku_data)} SKUs created')

    # ── Bridge Tables ─────────────────────────────────────
    def _create_bridges(self, products, methods, protocols, refs):
        # ProductMethod
        pm_links = [
            (0, 0, 'reagent', 'high'),    # Cy3-NHS → NHS-Ester RNA Labeling
            (1, 0, 'reagent', 'high'),    # Cy5-NHS → NHS-Ester RNA Labeling
            (2, 1, 'reagent', 'high'),    # DBCO-PEG4-NHS → Click Chemistry RNA Labeling
            (3, 5, 'reagent', 'high'),    # Azide-PEG3-Biotin → CuAAC Protein
            (4, 6, 'reagent', 'medium'),  # DBCO-Sulfo-NHS → SPAAC
            (5, 0, 'reagent', 'medium'),  # ATTO-488 NHS → NHS-Ester RNA Labeling
            (6, 3, 'kit', 'high'),        # BigDye → Sanger Sequencing
            (7, 4, 'kit', 'high'),        # Nextera XT → NGS Library Prep
            (8, 2, 'reagent', 'high'),    # RiboGreen → RiboGreen Quantification
            (9, 1, 'reagent', 'medium'),  # Azide-PEG4-NHS → Click Chemistry RNA
        ]
        for pidx, midx, role, evidence in pm_links:
            ProductMethod.objects.update_or_create(
                product=products[pidx],
                method=methods[midx],
                role=role,
                defaults={'evidence_level': evidence, 'display_order': 0},
            )

        # MethodProtocol
        for i, proto in enumerate(protocols):
            MethodProtocol.objects.update_or_create(
                method=proto.method,
                protocol=proto,
                defaults={'display_order': i, 'featured': i < 4, 'status': 'active'},
            )

        # ProductReference
        pr_links = [
            (0, 0, 'primary'),    # Cy3-NHS → RNA labeling paper
            (2, 2, 'primary'),    # DBCO-PEG4 → SPAAC paper
            (5, 4, 'supporting'), # ATTO-488 → Protein labeling guide
            (6, 3, 'primary'),    # BigDye → NGS methods review
            (8, 0, 'supporting'), # RiboGreen → RNA labeling paper
        ]
        for pidx, ridx, role in pr_links:
            ProductReference.objects.update_or_create(
                product=products[pidx],
                reference=refs[ridx],
                citation_role=role,
                defaults={'display_order': 0},
            )

        self.stdout.write(f'  Bridges: {len(pm_links)} ProductMethod, {len(protocols)} MethodProtocol, {len(pr_links)} ProductReference')

    # ── Compatibility ─────────────────────────────────────
    def _create_compatibility(self, products):
        comp_data = [
            (f'{PREFIX}COMP-001', 'product-product', 'compatible', 'info',
             'Cy3-NHS and Cy5-NHS can be used in dual-color experiments.',
             products[0], products[1]),
            (f'{PREFIX}COMP-002', 'product-product', 'incompatible', 'warning',
             'DBCO reagents are incompatible with free thiols — use azide-modified targets only.',
             products[2], products[3]),
            (f'{PREFIX}COMP-003', 'product-product', 'compatible', 'info',
             'Azide-PEG3-Biotin is compatible with all DBCO reagents.',
             products[3], products[4]),
        ]
        for code, scope, rule_type, severity, summary, src, tgt in comp_data:
            compat, _ = Compatibility.objects.update_or_create(
                code=code,
                defaults={
                    'scope': scope,
                    'rule_type': rule_type,
                    'severity': severity,
                    'summary': summary,
                    'expression_json': {'source': src.id, 'target': tgt.id},
                    'status': 'active',
                },
            )
            ProductCompatibility.objects.update_or_create(
                source_product=src,
                target_product=tgt,
                compatibility=compat,
                defaults={'verdict': rule_type, 'notes': summary},
            )

        # ProductProduct relationships
        ProductProduct.objects.update_or_create(
            source_product=products[0],
            target_product=products[1],
            relation_type='substitute',
            defaults={'direction': 'bidirectional', 'strength': 80, 'notes': 'Cy3 and Cy5 are interchangeable cyanine dyes.'},
        )
        ProductProduct.objects.update_or_create(
            source_product=products[2],
            target_product=products[4],
            relation_type='related',
            defaults={'direction': 'bidirectional', 'strength': 60, 'notes': 'Both are DBCO click chemistry reagents with different linker lengths.'},
        )

        self.stdout.write(f'  Compatibility: 3 rules, 2 product relationships')

    # ── 清除测试数据 ──────────────────────────────────────
    def _clear(self):
        self.stdout.write('清除测试数据...\n')

        # Order matters: children first, then parents
        counts = {}
        for model, slug_field in [
            (ProductProduct, 'source_product__slug'),
            (ProductCompatibility, 'source_product__slug'),
            (ProductReference, 'product__slug'),
            (MethodProtocol, 'method__slug'),
            (ProductMethod, 'product__slug'),
            (SKU, 'product__slug'),
            (ProtocolStep, 'protocol__slug'),
            (Protocol, 'slug'),
            (Product, 'slug'),
            (ProductClass, 'slug'),
            (CatalogGroup, 'slug'),
            (Method, 'slug'),
            (Application, 'slug'),
            (ResearchGoal, 'slug'),
            (Reference, 'title'),  # Reference has no slug, use title prefix
            (Compatibility, 'code'),
        ]:
            if model == Reference:
                qs = model.objects.filter(title__startswith=TAG)
            elif model == Compatibility:
                qs = model.objects.filter(code__startswith=PREFIX)
            elif model in (ProductProduct, ProductCompatibility, ProductReference, MethodProtocol, ProductMethod, SKU, ProtocolStep):
                qs = model.objects.filter(**{f'{slug_field}__startswith': PREFIX})
            else:
                qs = model.objects.filter(**{f'{slug_field}__startswith': PREFIX})

            count = qs.count()
            if count:
                qs.delete()
                counts[model.__name__] = count

        for name, count in counts.items():
            self.stdout.write(f'  删除 {name}: {count} 条')

        total = sum(counts.values())
        self.stdout.write(self.style.SUCCESS(f'\n✅ 测试数据清除完成！共删除 {total} 条记录'))
