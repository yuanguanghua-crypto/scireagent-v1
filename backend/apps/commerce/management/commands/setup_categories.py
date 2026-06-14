"""
Import PIT category tree into ProductClass table (3 levels).
Links existing products to their ProductClass based on category_l1.

Usage: python manage.py setup_categories
"""
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from apps.commerce.models import ProductClass, Product


# PIT category tree: L1 → L2 → L3
CATEGORY_TREE = {
    'nucleotides_nucleosides': {
        'label': 'Nucleotides & Nucleosides',
        'children': {
            'Modified Nucleotides': ['5-Formyl', '5-Hydroxymethyl', '5-Carboxy', '5-Propargylamino', '2-Amino', '2-Fluoro', '2-Methoxy', 'N6-Methyl', 'Pseudouridine'],
            'Nucleoside Analogues': [],
            'dNTPs & NTPs': [],
            'ddNTPs': [],
            'Labeled Nucleotides': [],
            'Cap Analogs': [],
            'Nucleotide Sugars': [],
            'Cyclic Nucleotides': [],
            'Nucleotide Libraries': [],
            'Click Chemistry Nucleotides': [],
            'Phosphoramidites': [],
        },
    },
    'click_chemistry': {
        'label': 'Click Chemistry',
        'children': {
            'Azides': [],
            'Alkynes': [],
            'BCN': [],
            'DBCO': [],
            'TCO/Tetrazine': [],
            'Linkers': [],
            'Bifunctional Crosslinkers': [],
        },
    },
    'molecular_biology': {
        'label': 'Molecular Biology',
        'children': {
            'DNA Ladders': [],
            'RNA Ladders': [],
            'Restriction Enzymes': [],
            'DNA Polymerases': [],
            'Reverse Transcriptases': [],
            'Ligases': [],
            'Phosphatases': [],
            'Nucleases': [],
        },
    },
    'proteins': {
        'label': 'Proteins',
        'children': {
            'Antibodies': [],
            'Enzymes': [],
            'Recombinant Proteins': [],
            'Protein Markers': [],
            'Protein Labeling Kits': [],
            'Streptavidin': [],
        },
    },
    'probes_epigenetics': {
        'label': 'Probes & Epigenetics',
        'children': {
            'Fluorescent Probes': [],
            'Biotin Probes': [],
            'Digoxigenin Probes': [],
            'methylcytidine Antibodies': [],
            'DNA/RNA Modifications': [],
            'Epigenetics Kits': [],
            'ISH Probes': [],
        },
    },
    'rna_technologies': {
        'label': 'RNA Technologies',
        'children': {
            'siRNA': [],
            'miRNA': [],
            'mRNA': [],
            'RNA Extraction Kits': [],
        },
    },
    'antibodies_antigens': {
        'label': 'Antibodies & Antigens',
        'children': {
            'Primary Antibodies': [],
            'Secondary Antibodies': [],
            'Isotype Controls': [],
            'Antigens': [],
        },
    },
    'crystallography_cryoem': {
        'label': 'Crystallography & Cryo-EM',
        'children': {
            'Cryo-EM Grids': [],
            'Crystallography Screens': [],
            'Cryo-EM Accessories': [],
            'Mounting Loops': [],
            'Grid Boxes': [],
            'Cryogenic Tools': [],
        },
    },
    'custom_synthesis': {
        'label': 'Custom Synthesis',
        'children': {
            'Oligonucleotide Synthesis': [],
            'Peptide Synthesis': [],
            'Small Molecule Synthesis': [],
            'Bioconjugation Services': [],
        },
    },
}

# Map category_l1 string → ProductClass L1 name
L1_MAP = {k: v['label'] for k, v in CATEGORY_TREE.items()}


class Command(BaseCommand):
    help = 'Import PIT category tree into ProductClass and link products'

    def handle(self, *args, **options):
        # Clear existing test categories
        deleted, _ = ProductClass.objects.filter(slug__startswith='test-').delete()
        self.stdout.write(f'Cleared {deleted} test categories')

        created_count = 0
        sort_order = 0

        for l1_key, l1_data in CATEGORY_TREE.items():
            sort_order += 1
            l1_name = l1_data['label']
            l1_slug = slugify(l1_key)

            l1_obj, created = ProductClass.objects.update_or_create(
                slug=l1_slug,
                defaults={
                    'name': l1_name,
                    'parent': None,
                    'sort_order': sort_order,
                }
            )
            if created:
                created_count += 1
                self.stdout.write(f'  L1: {l1_name}')
            else:
                self.stdout.write(f'  L1: {l1_name} (exists)')

            # L2 children
            l2_sort = 0
            for l2_name, l3_list in l1_data['children'].items():
                l2_sort += 1
                l2_slug = slugify(f'{l1_key}-{l2_name}')

                l2_obj, created = ProductClass.objects.update_or_create(
                    slug=l2_slug,
                    defaults={
                        'name': l2_name,
                        'parent': l1_obj,
                        'sort_order': l2_sort,
                    }
                )
                if created:
                    created_count += 1
                    self.stdout.write(f'    L2: {l2_name}')

                # L3 children (if any)
                l3_sort = 0
                for l3_name in l3_list:
                    l3_sort += 1
                    l3_slug = slugify(f'{l1_key}-{l2_name}-{l3_name}')

                    _, created = ProductClass.objects.update_or_create(
                        slug=l3_slug,
                        defaults={
                            'name': l3_name,
                            'parent': l2_obj,
                            'sort_order': l3_sort,
                        }
                    )
                    if created:
                        created_count += 1

        self.stdout.write(self.style.SUCCESS(f'\nCreated {created_count} categories'))

        # Link products to ProductClass based on category_l1
        linked = 0
        for product in Product.objects.exclude(category_l1=''):
            l1_name = L1_MAP.get(product.category_l1)
            if l1_name:
                try:
                    pc = ProductClass.objects.get(name=l1_name, parent__isnull=True)
                    product.product_class = pc
                    product.save(update_fields=['product_class'])
                    linked += 1
                except ProductClass.DoesNotExist:
                    self.stdout.write(f'  WARN: No ProductClass for {product.category_l1}')

        self.stdout.write(self.style.SUCCESS(f'Linked {linked} products to ProductClass'))
