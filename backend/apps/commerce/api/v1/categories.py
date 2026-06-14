"""Product categories endpoint — returns the PIT category tree with product counts."""
from django.db.models import Count, Q
from rest_framework.views import APIView
from rest_framework.response import Response
from apps.commerce.models import Product

CATEGORIES = {
    'nucleotides_nucleosides': {
        'label': 'Nucleotides & Nucleosides',
        'children': [
            'Modified Nucleotides', 'Nucleoside Analogues', 'dNTPs & NTPs',
            'ddNTPs', 'Labeled Nucleotides', 'Cap Analogs',
            'Nucleotide Sugars', 'Cyclic Nucleotides',
            'Nucleotide Libraries', 'Click Chemistry Nucleotides',
            'Phosphoramidites',
        ],
    },
    'click_chemistry': {
        'label': 'Click Chemistry',
        'children': [
            'Azides', 'Alkynes', 'BCN', 'DBCO', 'TCO/Tetrazine',
            'Linkers', 'Bifunctional Crosslinkers',
        ],
    },
    'molecular_biology': {
        'label': 'Molecular Biology',
        'children': [
            'DNA Ladders', 'RNA Ladders', 'Restriction Enzymes',
            'DNA Polymerases', 'Reverse Transcriptases', 'Ligases',
            'Phosphatases', 'Nucleases',
        ],
    },
    'proteins': {
        'label': 'Proteins',
        'children': [
            'Antibodies', 'Enzymes', 'Recombinant Proteins',
            'Protein Markers', 'Protein Labeling Kits', 'Streptavidin',
        ],
    },
    'probes_epigenetics': {
        'label': 'Probes & Epigenetics',
        'children': [
            'Fluorescent Probes', 'Biotin Probes', 'Digoxigenin Probes',
            'methylcytidine Antibodies', 'DNA/RNA Modifications',
            'Epigenetics Kits', 'ISH Probes',
        ],
    },
    'rna_technologies': {
        'label': 'RNA Technologies',
        'children': [
            'siRNA', 'miRNA', 'mRNA', 'RNA Extraction Kits',
        ],
    },
    'antibodies_antigens': {
        'label': 'Antibodies & Antigens',
        'children': [
            'Primary Antibodies', 'Secondary Antibodies',
            'Isotype Controls', 'Antigens',
        ],
    },
    'crystallography_cryoem': {
        'label': 'Crystallography & Cryo-EM',
        'children': [
            'Cryo-EM Grids', 'Crystallography Screens',
            'Cryo-EM Accessories', 'Mounting Loops',
            'Grid Boxes', 'Cryogenic Tools',
        ],
    },
    'custom_synthesis': {
        'label': 'Custom Synthesis',
        'children': [
            'Oligonucleotide Synthesis', 'Peptide Synthesis',
            'Small Molecule Synthesis', 'Bioconjugation Services',
        ],
    },
}


class CategoryTreeView(APIView):
    """GET /api/v1/categories — Returns the full category tree with product counts."""

    def get(self, request):
        # Build ProductClass lookup: L1 slug → L1 ProductClass ID and all descendant IDs
        from apps.commerce.models import ProductClass as PC

        l1_slug_map = {
            'nucleotides_nucleosides': 'nucleotides_nucleosides',
            'click_chemistry': 'click_chemistry',
            'molecular_biology': 'molecular_biology',
            'proteins': 'proteins',
            'probes_epigenetics': 'probes_epigenetics',
            'rna_technologies': 'rna_technologies',
            'antibodies_antigens': 'antibodies_antigens',
            'crystallography_cryoem': 'crystallography_cryoem',
            'custom_synthesis': 'custom_synthesis',
        }

        # Get all descendant IDs for each L1
        l1_counts = {}
        for cat_key, l1_slug in l1_slug_map.items():
            try:
                l1_pc = PC.objects.get(slug=l1_slug, parent__isnull=True)
                # Get all descendant IDs (L1 + L2 + L3)
                descendant_ids = [l1_pc.id]
                children = PC.objects.filter(parent=l1_pc)
                for child in children:
                    descendant_ids.append(child.id)
                    grandchildren = PC.objects.filter(parent=child)
                    descendant_ids.extend(grandchildren.values_list('id', flat=True))
                count = Product.objects.filter(product_class_id__in=descendant_ids).count()
                l1_counts[cat_key] = count
            except PC.DoesNotExist:
                l1_counts[cat_key] = 0

        # Also get L2 counts with IDs
        l2_counts = {}
        for cat_key, l1_slug in l1_slug_map.items():
            try:
                l1_pc = PC.objects.get(slug=l1_slug, parent__isnull=True)
                children = PC.objects.filter(parent=l1_pc)
                l2_counts[cat_key] = {}
                for child in children:
                    cnt = Product.objects.filter(product_class=child).count()
                    if cnt > 0:
                        l2_counts[cat_key][child.name] = {
                            'count': cnt,
                            'id': child.id,
                        }
            except PC.DoesNotExist:
                pass

        result = {}
        for key, data in CATEGORIES.items():
            result[key] = {
                'label': data['label'],
                'children': data['children'],
                'count': l1_counts.get(key, 0),
                'l2_counts': l2_counts.get(key, {}),
            }

        return Response(result)
