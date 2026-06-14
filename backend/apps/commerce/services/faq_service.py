"""
FAQ Service — Generate FAQ list from existing product data.
Runtime generation, no database storage.
"""
from apps.bridges.models import ProductMethod, MethodProtocol
from apps.knowledge.models import Method, Protocol


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
    methods = Method.objects.filter(id__in=method_ids, status='active')

    # Get applications via methods
    from apps.knowledge.models import Application
    applications = Application.objects.filter(
        methods__id__in=method_ids, status='active'
    ).distinct()

    # Get protocols via MethodProtocol bridge
    protocol_ids = list(
        MethodProtocol.objects.filter(method_id__in=method_ids).values_list('protocol_id', flat=True)
    )
    protocols = Protocol.objects.filter(id__in=protocol_ids, status='published')

    # Q1: What is X used for?
    if applications:
        faq.append({
            'question': f'What is {product.name} used for?',
            'answer': ', '.join(app.name for app in applications),
        })

    # Q2: Which methods use X?
    if methods:
        faq.append({
            'question': f'Which methods use {product.name}?',
            'answer': ', '.join(m.name for m in methods),
        })

    # Q3: How should X be stored?
    if product.storage:
        faq.append({
            'question': f'How should {product.name} be stored?',
            'answer': product.storage,
        })

    # Q4: Which protocols use X?
    if protocols:
        faq.append({
            'question': f'Which protocols use {product.name}?',
            'answer': ', '.join(p.name for p in protocols),
        })

    return faq
