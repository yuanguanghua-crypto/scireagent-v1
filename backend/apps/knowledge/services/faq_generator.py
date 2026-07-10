"""
FAQ Generator Service
Generates FAQ questions dynamically from product entity relationships.
"""
from apps.commerce.models import Product


def generate_faq(product: Product) -> list[dict]:
    """
    Generate FAQ for a product from its entity relationships.
    Returns at least 4 questions.
    """
    faqs = []

    # Q1: What is this product used for?
    methods = set()
    for pm in product.product_methods.select_related('method').all()[:5]:
        methods.add(pm.method.name)
    if methods:
        method_list = ', '.join(sorted(methods))
        faqs.append({
            'question': f'What is {product.name} used for?',
            'answer': f'{product.name} is used in {method_list}. {product.overview or ""}'.strip(),
        })
    else:
        faqs.append({
            'question': f'What is {product.name} used for?',
            'answer': product.overview or f'{product.name} is a research reagent for molecular biology applications.',
        })

    # Q2: How should it be stored?
    if product.storage:
        faqs.append({
            'question': f'How should {product.name} be stored?',
            'answer': f'Store {product.name} at {product.storage}.',
        })

    # Q3: What is the purity?
    if product.purity:
        faqs.append({
            'question': f'What is the purity of {product.name}?',
            'answer': f'{product.name} has a purity of {product.purity}.',
        })

    # Q4: Which methods use this product?
    if methods:
        method_list = ', '.join(sorted(methods))
        faqs.append({
            'question': f'Which methods use {product.name}?',
            'answer': f'{product.name} is used in the following methods: {method_list}.',
        })
    else:
        faqs.append({
            'question': f'What concentration is {product.name} supplied at?',
            'answer': f'{product.name} is supplied at {product.concentration or "100 mM"}.',
        })

    # Q5: What is the molecular formula?
    if product.formula:
        faqs.append({
            'question': f'What is the molecular formula of {product.name}?',
            'answer': f'The molecular formula of {product.name} is {product.formula}.',
        })

    # Q6: What is the CAS number?
    if product.cas:
        faqs.append({
            'question': f'What is the CAS number of {product.name}?',
            'answer': f'The CAS number of {product.name} is {product.cas}.',
        })

    return faqs[:6]


def generate_faq_json_ld(product: Product, faqs: list[dict]) -> dict:
    """Generate FAQPage JSON-LD structured data."""
    return {
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        'mainEntity': [
            {
                '@type': 'Question',
                'name': faq['question'],
                'acceptedAnswer': {
                    '@type': 'Answer',
                    'text': faq['answer'],
                },
            }
            for faq in faqs
        ],
    }
