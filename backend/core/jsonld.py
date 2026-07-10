"""
JSON-LD structured data utilities for LabPro Global.
Based on Chapter 4 §10 and Chapter 9 AI Agent Integration Spec.
"""


def build_product_jsonld(product, request=None):
    """Build JSON-LD for a Product resource.

    Args:
        product: Product model instance.
        request: Optional Django HttpRequest for base URL extraction.

    Returns:
        dict: JSON-LD structured data for the product.
    """
    base_url = _get_base_url(request)
    return {
        '@context': ['https://schema.org', f'{base_url}/context'],
        '@id': f'{base_url}/products/{product.slug}',
        '@type': ['Product', 'ChemicalSubstance'],
        'name': product.name,
        'alternateName': product.synonyms if product.synonyms else [],
        'description': product.storage or '',
        'url': f'{base_url}/products/{product.slug}',
        'dateModified': product.updated_at.isoformat() if product.updated_at else None,
        'identifier': product.cas or product.inchi or '',
        'additionalProperty': _build_product_properties(product),
    }


def build_method_jsonld(method, request=None):
    """Build JSON-LD for a Method resource.

    Args:
        method: Method model instance.
        request: Optional Django HttpRequest for base URL extraction.

    Returns:
        dict: JSON-LD structured data for the method.
    """
    base_url = _get_base_url(request)
    return {
        '@context': ['https://schema.org', f'{base_url}/context'],
        '@id': f'{base_url}/methods/{method.slug}',
        '@type': ['HowTo', 'lab:Method'],
        'name': method.name,
        'description': method.summary or method.purpose or '',
        'url': f'{base_url}/methods/{method.slug}',
        'dateModified': method.updated_at.isoformat() if method.updated_at else None,
    }


def build_protocol_jsonld(protocol, steps=None, request=None):
    """Build JSON-LD for a Protocol resource.

    Args:
        protocol: Protocol model instance.
        steps: Optional queryset or list of ProtocolStep instances.
        request: Optional Django HttpRequest for base URL extraction.

    Returns:
        dict: JSON-LD structured data for the protocol.
    """
    base_url = _get_base_url(request)
    jsonld = {
        '@context': ['https://schema.org', f'{base_url}/context'],
        '@id': f'{base_url}/protocols/{protocol.slug}',
        '@type': ['HowTo', 'CreativeWork'],
        'name': f'{protocol.name} v{protocol.version}',
        'description': protocol.objective or '',
        'url': f'{base_url}/protocols/{protocol.slug}',
        'dateModified': protocol.updated_at.isoformat() if protocol.updated_at else None,
        'step': [],
    }
    if steps:
        jsonld['step'] = [
            {
                '@type': 'HowToStep',
                'position': step.step_no,
                'name': step.title,
                'text': step.body,
            }
            for step in steps
        ]
    return jsonld


def build_reference_jsonld(reference, request=None):
    """Build JSON-LD for a Reference resource.

    Args:
        reference: Reference model instance.
        request: Optional Django HttpRequest for base URL extraction.

    Returns:
        dict: JSON-LD structured data for the reference.
    """
    base_url = _get_base_url(request)
    return {
        '@context': ['https://schema.org', f'{base_url}/context'],
        '@id': f'{base_url}/references/{reference.id}',
        '@type': 'ScholarlyArticle',
        'name': reference.title,
        'author': reference.authors,
        'datePublished': str(reference.year) if reference.year else None,
        'url': reference.url or f'{base_url}/references/{reference.id}',
        'identifier': reference.doi or reference.pmid or '',
        'isPartOf': (
            {'@type': 'Periodical', 'name': reference.journal}
            if reference.journal else None
        ),
    }


def _build_product_properties(product):
    """Build additionalProperty array for a product.

    Args:
        product: Product model instance.

    Returns:
        list: Array of PropertyValue dicts.
    """
    props = []
    if product.cas:
        props.append({
            '@type': 'PropertyValue',
            'name': 'CAS',
            'value': product.cas,
        })
    if product.smiles:
        props.append({
            '@type': 'PropertyValue',
            'name': 'SMILES',
            'value': product.smiles,
        })
    if product.inchi:
        props.append({
            '@type': 'PropertyValue',
            'name': 'InChI',
            'value': product.inchi,
        })
    if product.purity:
        props.append({
            '@type': 'PropertyValue',
            'name': 'Purity',
            'value': product.purity,
        })
    if product.shelf_life:
        props.append({
            '@type': 'PropertyValue',
            'name': 'Shelf Life',
            'value': str(product.shelf_life),
        })
    return props


def _get_base_url(request):
    """Extract base URL from request.

    Args:
        request: Optional Django HttpRequest.

    Returns:
        str: Base URL string.
    """
    if request:
        return f'{request.scheme}://{request.get_host()}'
    return 'https://scireagent.example.com'
