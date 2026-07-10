"""
Agent read-only resource layer.
Reserved for future MCP integration (Phase 5 of roadmap).

These functions provide stable, versioned read models
that can be consumed by AI agents without exposing write paths.
"""


def get_product_read_model(product):
    """Return a stable read model for agent consumption.

    Args:
        product: Product model instance.

    Returns:
        dict: Read-only representation of the product for agent consumption.
    """
    return {
        'type': 'product',
        'id': product.id,
        'slug': product.slug,
        'name': product.name,
        'cas': product.cas,
        'smiles': product.smiles,
        'inchi': product.inchi,
        'synonyms': product.synonyms,
        'purity': product.purity,
        'storage': product.storage,
        'status': product.status,
        'research_use_only': product.research_use_only,
    }


def get_method_read_model(method):
    """Return a stable read model for agent consumption.

    Args:
        method: Method model instance.

    Returns:
        dict: Read-only representation of the method for agent consumption.
    """
    return {
        'type': 'method',
        'id': method.id,
        'slug': method.slug,
        'name': method.name,
        'summary': method.summary,
        'purpose': method.purpose,
        'advantages': method.advantages,
        'limitations': method.limitations,
        'cost_band': method.cost_band,
        'timeline': method.timeline,
        'status': method.status,
    }


def get_protocol_read_model(protocol):
    """Return a stable read model for agent consumption.

    Args:
        protocol: Protocol model instance.

    Returns:
        dict: Read-only representation of the protocol for agent consumption.
    """
    return {
        'type': 'protocol',
        'id': protocol.id,
        'slug': protocol.slug,
        'name': protocol.name,
        'version': protocol.version,
        'objective': protocol.objective,
        'principle': protocol.principle,
        'materials': protocol.materials,
        'reagents': protocol.reagents,
        'equipment': protocol.equipment,
        'steps': [
            {
                'step_no': s.step_no,
                'title': s.title,
                'body': s.body,
            }
            for s in protocol.steps.all()
        ],
        'status': protocol.status,
    }
