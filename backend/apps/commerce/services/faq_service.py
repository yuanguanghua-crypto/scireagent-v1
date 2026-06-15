"""
FAQ Service — Generate FAQ list from existing product data.
Enhanced with knowledge-aware, informative answers.
Runtime generation, no database storage.
"""
from apps.bridges.models import ProductMethod, MethodProtocol
from apps.knowledge.models import Method, Protocol, Application


def generate_faq(product):
    """
    Generate FAQ list for a product from existing data.
    Returns: list of {"question": str, "answer": str}
    """
    faq = []

    # Get related methods via ProductMethod bridge
    method_ids = list(
        ProductMethod.objects.filter(product=product).values_list('method_id', flat=True)
    )
    methods = list(Method.objects.filter(id__in=method_ids, status='active'))

    # Get applications via methods
    applications = list(Application.objects.filter(
        methods__id__in=method_ids, status='active'
    ).distinct())

    # Get protocols via MethodProtocol bridge
    protocol_ids = list(
        MethodProtocol.objects.filter(method_id__in=method_ids).values_list('protocol_id', flat=True)
    )
    protocols = list(Protocol.objects.filter(id__in=protocol_ids, status='published'))

    # Q1: What is X used for?
    if applications:
        app_list = ', '.join(a.name for a in applications[:3])
        faq.append({
            'question': f'What is {product.name} used for?',
            'answer': (
                f'{product.name} is used in {app_list} applications. '
                f'It is a modified nucleotide analog suitable for research use in molecular biology workflows.'
            ),
        })

    # Q2: Which methods are compatible with X?
    if methods:
        method_details = []
        for m in methods[:3]:
            detail = m.name
            if m.purpose:
                detail += f' ({m.purpose[:60]}...)'
            method_details.append(detail)
        faq.append({
            'question': f'Which methods are compatible with {product.name}?',
            'answer': (
                f'{product.name} is compatible with the following methods: '
                + '; '.join(method_details) + '.'
            ),
        })

    # Q3: How should X be stored?
    if product.storage:
        faq.append({
            'question': f'How should {product.name} be stored?',
            'answer': (
                f'Store {product.name} at {product.storage}. '
                f'Avoid repeated freeze-thaw cycles. For long-term storage, aliquot into single-use portions.'
            ),
        })

    # Q4: What protocols use X?
    if protocols:
        proto_list = ', '.join(p.name for p in protocols[:3])
        faq.append({
            'question': f'What protocols use {product.name}?',
            'answer': (
                f'{product.name} is used in the following protocols: {proto_list}. '
                f'Refer to the protocol documentation for detailed step-by-step instructions.'
            ),
        })

    # Q5: What is the purity of X?
    if product.purity:
        faq.append({
            'question': f'What is the purity of {product.name}?',
            'answer': (
                f'{product.name} has a purity of {product.purity}, '
                f'determined by HPLC analysis. Certificate of Analysis is available upon request.'
            ),
        })

    # Q6: What is the molecular weight of X?
    if product.molecular_weight:
        faq.append({
            'question': f'What is the molecular weight of {product.name}?',
            'answer': (
                f'The molecular weight of {product.name} is {product.molecular_weight} g/mol.'
                + (f' Molecular formula: {product.formula}.' if product.formula else '')
            ),
        })

    # Q7: Can X be used in live cells?
    name_lower = product.name.lower()
    if 'azido' in name_lower or 'alkyn' in name_lower or 'propargyl' in name_lower:
        faq.append({
            'question': f'Can {product.name} be used in live cells?',
            'answer': (
                f'{product.name} contains a reactive handle for bioorthogonal chemistry. '
                f'For live cell applications, consider using copper-free alternatives (e.g., SPAAC) '
                f'to avoid copper toxicity. Compatibility should be experimentally validated.'
            ),
        })

    # Q8: Is X suitable for in vitro transcription?
    if product.product_class_id == 10:  # Modified NTPs
        faq.append({
            'question': f'Is {product.name} suitable for in vitro transcription?',
            'answer': (
                f'{product.name} can be incorporated during in vitro transcription using T7 RNA polymerase. '
                f'Optimize the ratio of modified to unmodified NTPs (typically 20-50% replacement) '
                f'for best results. Incorporation efficiency varies by modification type.'
            ),
        })

    return faq
